"""Enregistrement des candidats collectés (v2) : pour chaque candidat, `normalize` → validation →
`find_duplicate` (RB-001) → fusion dans la fiche existante ou création d'une nouvelle fiche avec son
lien de provenance, ses pièces et son vecteur sémantique. Une URL déjà liée est ignorée (`skipped`) ;
une fiche dont l'échéance est passée est créée inactive (RB-002 dès l'ingestion)."""

from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider
from app.ai.outputs import TenderCandidate
from app.core import deps
from app.core.audit import record_audit
from app.core.logging import get_logger
from app.models import SearchProfile, Tender, TenderDocument, TenderSourceLink, TenderStatus, Urgency
from app.services.collect import SourceReport
from app.services.deadlines import compute_urgency
from app.services.dedup import Deduplicator, document_name, end_of_day
from app.services.normalize import NormalizedTender, embedding_text, normalize

log = get_logger("ingest")

MIN_CONFIDENCE = 0.6


@dataclass
class IngestStats:
    created: int = 0
    merged: int = 0  # doublon rapproché par une règle autre que l'URL : provenance ajoutée à la fiche
    skipped: int = 0  # URL déjà liée à une fiche
    invalid: int = 0  # pas un appel d'offres, confiance insuffisante, titre ou URL vides
    # Une entrée par candidat : {url, action, rule, tender_id}. `rule` = règle de déduplication pour
    # merged / skipped, motif de rejet pour invalid, None pour created.
    details: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "merged": self.merged,
            "skipped": self.skipped,
            "invalid": self.invalid,
        }

    def add(self, other: "IngestStats") -> None:
        self.created += other.created
        self.merged += other.merged
        self.skipped += other.skipped
        self.invalid += other.invalid
        self.details.extend(other.details)

    def record(self, url: str, action: str, *, rule: str | None = None, tender: Tender | None = None) -> None:
        setattr(self, action, getattr(self, action) + 1)
        self.details.append(
            {"url": url, "action": action, "rule": rule, "tender_id": str(tender.id) if tender else None}
        )


def rejection_reason(c: TenderCandidate) -> str | None:
    if not c.is_tender:
        return "not_tender"
    if c.confidence < MIN_CONFIDENCE:
        return "low_confidence"
    if not c.title.strip():
        return "empty_title"
    if not c.source_url.strip():
        return "empty_url"
    return None


class IngestService:
    def __init__(
        self,
        db: Session,
        embeddings: EmbeddingProvider | None = None,
        dedup: Deduplicator | None = None,
    ):
        self.db = db
        self.embeddings = embeddings or deps.get_embeddings()
        self.dedup = dedup or Deduplicator(db, self.embeddings)

    def known_url(self, url: str) -> bool:
        return self.db.scalar(select(TenderSourceLink.id).where(TenderSourceLink.url == url)) is not None

    def ingest(self, report: SourceReport, profile: SearchProfile) -> IngestStats:
        stats = IngestStats()
        source_id = UUID(report.source_id) if report.source_id else None

        valid: list[tuple[TenderCandidate, NormalizedTender]] = []
        for candidate in report.candidates:
            reason = rejection_reason(candidate)
            if reason:
                stats.record(candidate.source_url.strip(), "invalid", rule=reason)
                continue
            valid.append((candidate, normalize(candidate)))
        # Un seul appel au fournisseur pour toute la passe (règle sémantique + colonne `embedding`).
        vectors = self.embeddings.embed([embedding_text(n) for _, n in valid]) if valid else []

        for (candidate, n), vector in zip(valid, vectors, strict=True):
            title_seen = report.titles.get(n.source_url)
            match = self.dedup.find_duplicate(n, embedding=vector)
            if match is None:
                tender = self._create(n, vector, source_id, profile, title_seen=title_seen, raw=candidate)
                stats.record(n.source_url, "created", tender=tender)
            elif match.rule == "url":
                stats.record(n.source_url, "skipped", rule="url", tender=match.tender)
            else:
                merged = self.dedup.merge_into(
                    match.tender, n, source_id=source_id, title_seen=title_seen, rule=match.rule
                )
                merged.urgency = compute_urgency(merged.days_left)  # la fusion peut apporter l'échéance
                stats.record(n.source_url, "merged", rule=match.rule, tender=merged)
            self.db.flush()  # la fiche devient visible pour les candidats suivants de la même passe
        return stats

    def _create(
        self,
        n: NormalizedTender,
        vector: list[float],
        source_id: UUID | None,
        profile: SearchProfile,
        *,
        title_seen: str | None,
        raw: TenderCandidate,
    ) -> Tender:
        # RB-002 dès l'ingestion : une échéance passée donne une fiche inactive, sans urgence.
        days_left = (n.deadline_at - date.today()).days if n.deadline_at else None
        is_active = days_left is None or days_left >= 0
        tender = Tender(
            title=n.title[:512],
            reference=n.reference,
            organization=n.organization,
            organization_type=n.organization_type,
            country=n.country,
            region=n.region,
            sector=n.sector,
            market_type=n.market_type,
            budget_min=n.budget_min,
            budget_max=n.budget_max,
            currency=n.currency,
            published_at=n.published_at,
            deadline_at=end_of_day(n.deadline_at),
            questions_deadline_at=end_of_day(n.questions_deadline_at),
            source_url=n.source_url,
            description=n.description or None,
            fingerprint=n.fingerprint,
            norm_title=n.norm_title[:512],
            norm_org=n.norm_org[:255] or None,
            norm_reference=n.norm_reference,
            status=TenderStatus.NOUVEAU,
            is_active=is_active,
            urgency=compute_urgency(days_left) if is_active else Urgency.none,
            search_profile_id=profile.id,
            raw=raw.model_dump(mode="json"),
            extra={
                "technologies": n.technologies,
                "required_certifications": n.required_certifications,
                "document_urls": list(n.document_urls),
            },
            embedding=vector,
        )
        tender.source_links.append(
            TenderSourceLink(source_id=source_id, url=n.source_url, title_seen=title_seen)
        )
        for doc_url in dict.fromkeys(n.document_urls):
            tender.documents.append(TenderDocument(name=document_name(doc_url), source_url=doc_url))
        self.db.add(tender)
        self.db.flush()  # id nécessaire pour l'audit
        record_audit(
            self.db,
            action="tender.created",
            entity_kind="tender",
            entity_id=tender.id,
            payload={"url": n.source_url, "source_id": str(source_id) if source_id else None},
        )
        log.info("ingest.created", tender_id=str(tender.id), url=n.source_url)
        return tender
