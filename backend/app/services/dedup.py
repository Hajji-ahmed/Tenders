"""Déduplication des appels d'offres (RB-001) : cinq règles appliquées dans l'ordre, de la plus sûre
à la plus souple, puis fusion d'un candidat dans une fiche existante sans jamais écraser ce qui est
déjà renseigné. La règle retenue est journalisée (audit `tender.merged`, rapport d'ingestion)."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from urllib.parse import unquote, urlparse
from uuid import UUID

from rapidfuzz import fuzz
from sqlalchemy import cast, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.types import Date

from app.ai.embeddings import EmbeddingProvider
from app.core.audit import record_audit
from app.core.logging import get_logger
from app.models import Tender, TenderDocument, TenderSourceLink
from app.services.normalize import NormalizedTender, embedding_text

log = get_logger("dedup")

# Champs de la fiche complétés depuis le candidat quand ils sont vides (jamais écrasés).
FILLABLE = (
    "reference", "organization", "organization_type", "country", "region", "sector", "market_type",
    "budget_min", "budget_max", "currency", "published_at", "description",
    "norm_title", "norm_org", "norm_reference", "fingerprint",
)  # fmt: skip
SEMANTIC_WINDOW_DAYS = 3


@dataclass
class DuplicateMatch:
    tender: Tender
    rule: str  # url | reference | fingerprint | fuzzy_title | semantic


def end_of_day(d: date | None) -> datetime | None:
    return None if d is None else datetime.combine(d, time(23, 59, 59), tzinfo=UTC)


def document_name(url: str) -> str:
    last = unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]).strip()
    return last[:255] or "document"


def same_organization(a: str | None, b: str | None) -> bool:
    """Deux formes normalisées désignent le même organisme si l'une contient tous les mots de l'autre."""
    if not a or not b:
        return False
    words_a, words_b = set(a.split()), set(b.split())
    return words_a <= words_b or words_b <= words_a


class Deduplicator:
    def __init__(
        self,
        db: Session,
        embeddings: EmbeddingProvider,
        *,
        fuzzy_threshold: int = 90,
        semantic_threshold: float = 0.92,
    ):
        self.db = db
        self.embeddings = embeddings
        self.fuzzy_threshold = fuzzy_threshold
        self.semantic_threshold = semantic_threshold

    # --- détection -------------------------------------------------------------------------------

    def find_duplicate(
        self, n: NormalizedTender, *, embedding: list[float] | None = None
    ) -> DuplicateMatch | None:
        for rule, finder in (
            ("url", self._by_url),
            ("reference", self._by_reference),
            ("fingerprint", self._by_fingerprint),
            ("fuzzy_title", self._by_fuzzy_title),
        ):
            tender = finder(n)
            if tender is not None:
                log.info("dedup.match", rule=rule, tender_id=str(tender.id), url=n.source_url)
                return DuplicateMatch(tender, rule)
        tender = self._by_embedding(n, embedding)
        if tender is not None:
            log.info("dedup.match", rule="semantic", tender_id=str(tender.id), url=n.source_url)
            return DuplicateMatch(tender, "semantic")
        return None

    def _by_url(self, n: NormalizedTender) -> Tender | None:
        if not n.source_url:
            return None
        link = self.db.scalar(select(TenderSourceLink).where(TenderSourceLink.url == n.source_url))
        return link.tender if link is not None else None

    def _by_reference(self, n: NormalizedTender) -> Tender | None:
        """Même référence et même acheteur. Les sources nomment l'acheteur avec plus ou moins de
        précision (« Commune de Salé » / « Commune de Salé (Maroc), Direction des services
        techniques ») : un organisme dont tous les mots figurent dans l'autre est le même."""
        if not n.norm_reference or not n.norm_org:
            return None
        candidates = self.db.scalars(
            select(Tender).where(Tender.norm_reference == n.norm_reference).order_by(Tender.created_at)
        ).all()
        return next((t for t in candidates if same_organization(n.norm_org, t.norm_org)), None)

    def _by_fingerprint(self, n: NormalizedTender) -> Tender | None:
        return self.db.scalar(
            select(Tender).where(Tender.fingerprint == n.fingerprint).order_by(Tender.created_at)
        )

    def _by_fuzzy_title(self, n: NormalizedTender) -> Tender | None:
        """Même organisme OU même date d'échéance, et titres quasi identiques (token_set_ratio)."""
        if not n.norm_title:
            return None
        conditions = []
        if n.norm_org:
            conditions.append(Tender.norm_org == n.norm_org)
        if n.deadline_at:
            conditions.append(cast(Tender.deadline_at, Date) == n.deadline_at)
        if not conditions:
            return None
        candidates = self.db.scalars(
            select(Tender).where(Tender.is_active.is_(True), Tender.norm_title.isnot(None), or_(*conditions))
        ).all()
        best: tuple[int, Tender] | None = None
        for t in candidates:
            score = int(fuzz.token_set_ratio(n.norm_title, t.norm_title or ""))
            if score >= self.fuzzy_threshold and (best is None or score > best[0]):
                best = (score, t)
        return best[1] if best else None

    def _by_embedding(self, n: NormalizedTender, embedding: list[float] | None) -> Tender | None:
        """Voisin sémantique le plus proche (cosinus ≥ seuil) parmi les fiches actives dont l'échéance est
        à ± 3 jours de celle du candidat (ou absente)."""
        vec = embedding if embedding is not None else self.embeddings.embed([embedding_text(n)])[0]
        distance = Tender.embedding.cosine_distance(vec)
        stmt = select(Tender, distance).where(Tender.is_active.is_(True), Tender.embedding.isnot(None))
        if n.deadline_at:
            lo = end_of_day(n.deadline_at - timedelta(days=SEMANTIC_WINDOW_DAYS + 1))
            hi = end_of_day(n.deadline_at + timedelta(days=SEMANTIC_WINDOW_DAYS))
            stmt = stmt.where(or_(Tender.deadline_at.is_(None), Tender.deadline_at.between(lo, hi)))
        for tender, dist in self.db.execute(stmt.order_by(distance).limit(3)).all():
            if 1 - float(dist) >= self.semantic_threshold:
                return tender
        return None

    # --- fusion ----------------------------------------------------------------------------------

    def merge_into(
        self,
        tender: Tender,
        n: NormalizedTender,
        *,
        source_id: UUID | None,
        title_seen: str | None,
        rule: str,
        raw: dict | None = None,
    ) -> Tender:
        """Ajoute la provenance et complète la fiche existante ; ne remplace jamais une valeur présente."""
        known_urls = {link.url for link in tender.source_links}
        if n.source_url and n.source_url not in known_urls:
            tender.source_links.append(
                TenderSourceLink(source_id=source_id, url=n.source_url, title_seen=title_seen, raw=raw)
            )
        for field in FILLABLE:
            incoming = getattr(n, field)
            if incoming in (None, "", []):
                continue
            if getattr(tender, field) in (None, "", []):
                setattr(tender, field, incoming)
        if tender.deadline_at is None and n.deadline_at:
            tender.deadline_at = end_of_day(n.deadline_at)
        if tender.questions_deadline_at is None and n.questions_deadline_at:
            tender.questions_deadline_at = end_of_day(n.questions_deadline_at)

        extra = dict(tender.extra or {})
        doc_urls = list(dict.fromkeys([*extra.get("document_urls", []), *n.document_urls]))
        extra["document_urls"] = doc_urls
        for key in ("technologies", "required_certifications"):
            extra[key] = list(dict.fromkeys([*extra.get(key, []), *getattr(n, key)]))
        tender.extra = extra  # nouvel objet : SQLAlchemy détecte le changement de la colonne JSON

        known_docs = {d.source_url for d in tender.documents}
        for url in n.document_urls:
            if url not in known_docs:
                tender.documents.append(TenderDocument(name=document_name(url), source_url=url))
                known_docs.add(url)

        record_audit(
            self.db,
            action="tender.merged",
            entity_kind="tender",
            entity_id=tender.id,
            payload={"rule": rule, "url": n.source_url, "source_id": str(source_id) if source_id else None},
        )
        return tender
