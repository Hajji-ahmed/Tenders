"""Recherche interne (Module 18) : une seule requête traverse les opportunités, la base documentaire
et le profil (projets, experts, références, certifications). Deux lectures se complètent — le texte
(`ILIKE`, ce que l'utilisateur a écrit) et, à la demande, le sens (morceaux indexés et fiches proches
par vecteur). Chaque résultat porte l'adresse de la page où l'ouvrir : la recherche sert à naviguer."""

from collections.abc import Callable, Iterable
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider
from app.models import (
    Certification,
    Company,
    CompanyDocument,
    Expert,
    Project,
    Reference,
    Tender,
    TenderDocument,
)
from app.services.company import CompanyService
from app.services.knowledge import KBHit, KnowledgeBase

MIN_QUERY = 3  # en deçà, « ILIKE %a% » ramènerait la moitié de la base
DEFAULT_LIMIT = 10
SEMANTIC_K = 10
TEXT_SCORE = 1.0  # le mot demandé est littéralement là : rien n'est plus sûr qu'une correspondance exacte
# Plancher de proximité : le cosinus le plus proche n'est pas forcément proche. Constaté en réel —
# « qui peut assurer la maintenance de la télégestion » remontait dix opportunités entre 34 % et 38 %,
# gardiennage en tête. Mieux vaut ne rien proposer que proposer au hasard.
MIN_SEMANTIC_SCORE = 0.40

KIND_LABELS: dict[str, str] = {
    "tenders": "Opportunités",
    "documents": "Documents",
    "projects": "Projets",
    "experts": "Experts",
    "references": "Références",
    "certifications": "Certifications",
}
KINDS = tuple(KIND_LABELS)


class SearchItem(BaseModel):
    id: str
    kind: str
    title: str
    subtitle: str | None = None
    url: str  # route du frontend (/tenders/{id}, /documents?open={id}, /company?tab=…&id=…)
    score: float
    excerpt: str | None = None  # passage retenu par la recherche sémantique


class SearchGroup(BaseModel):
    kind: str
    label: str
    items: list[SearchItem] = Field(default_factory=list)


class SearchResults(BaseModel):
    query: str
    semantic: bool
    groups: list[SearchGroup] = Field(default_factory=list)
    total: int = 0


def _join(*parts: Any, separator: str = " · ") -> str | None:
    values = [str(p) for p in parts if p not in (None, "")]
    return separator.join(values) if values else None


def _state(doc: CompanyDocument) -> str:
    """Pourquoi un document n'est pas utilisable, en un mot (RB-007)."""
    if doc.is_expired:
        return "expiré"
    return {"draft": "brouillon", "archived": "archivé", "expired": "expiré"}.get(
        str(doc.status), "à vérifier"
    )


def _years(expert: Expert) -> str | None:
    n = expert.years_experience
    return f"{n} an{'s' if n and n > 1 else ''} d'expérience" if n else None


class InternalSearch:
    def __init__(self, db: Session, embeddings: EmbeddingProvider | None = None):
        self.db = db
        self.embeddings = embeddings

    def run(
        self,
        query: str,
        *,
        kinds: Iterable[str] | None = None,
        semantic: bool = False,
        limit: int = DEFAULT_LIMIT,
    ) -> SearchResults:
        wanted = [k for k in (kinds or KINDS) if k in KIND_LABELS]
        text = query.strip()
        results = SearchResults(query=text, semantic=semantic)
        if len(text) < MIN_QUERY:
            return results

        found: dict[str, dict[str, SearchItem]] = {kind: {} for kind in wanted}
        for kind in wanted:
            for item in self._text_search(kind, text, limit):
                found[kind][item.id] = item
        if semantic and self.embeddings is not None:
            for item in self._semantic(text, wanted, limit):
                if item.score < MIN_SEMANTIC_SCORE:
                    continue
                bucket = found.setdefault(item.kind, {})
                known = bucket.get(item.id)
                if known is None:
                    bucket[item.id] = item
                elif item.excerpt and not known.excerpt:
                    known.excerpt = item.excerpt  # le passage éclaire un résultat déjà trouvé par le texte

        for kind in wanted:
            items = sorted(found.get(kind, {}).values(), key=lambda i: (-i.score, i.title))[:limit]
            if items:
                results.groups.append(SearchGroup(kind=kind, label=KIND_LABELS[kind], items=items))
        results.total = sum(len(g.items) for g in results.groups)
        return results

    # --- recherche textuelle -------------------------------------------------------------------

    def _text_search(self, kind: str, query: str, limit: int) -> list[SearchItem]:
        builder: Callable[[str, int], list[SearchItem]] = getattr(self, f"_search_{kind}")
        return builder(f"%{query}%", limit)

    def _company_rows(self, model: Any, pattern: str, columns: list, limit: int) -> list[Any]:
        """Lignes d'une sous-ressource du profil dont une colonne contient le texte cherché."""
        company: Company = CompanyService.get_or_create(self.db)
        stmt: Select = (
            select(model)
            .where(model.company_id == company.id)
            .where(or_(*[c.ilike(pattern) for c in columns]))
            .limit(limit)
        )
        return list(self.db.scalars(stmt))

    def _search_tenders(self, pattern: str, limit: int) -> list[SearchItem]:
        stmt = (
            select(Tender)
            .where(
                or_(
                    Tender.title.ilike(pattern),
                    Tender.organization.ilike(pattern),
                    Tender.reference.ilike(pattern),
                    Tender.description.ilike(pattern),
                    Tender.summary.ilike(pattern),
                )
            )
            .order_by(Tender.created_at.desc())
            .limit(limit)
        )
        return [self._tender_item(t, TEXT_SCORE) for t in self.db.scalars(stmt)]

    def _search_documents(self, pattern: str, limit: int) -> list[SearchItem]:
        rows = self._company_rows(
            CompanyDocument, pattern, [CompanyDocument.name, CompanyDocument.description], limit
        )
        # Un document inutilisable (expiré, archivé, brouillon) reste trouvable — on navigue ici, on ne
        # cite pas : RB-007 ne s'applique qu'aux extraits versés comme preuve (recherche sémantique).
        return [
            SearchItem(
                id=str(d.id),
                kind="documents",
                title=d.name,
                subtitle=_join(str(d.category), None if d.is_usable else _state(d)),
                url=f"/documents?open={d.id}",
                score=TEXT_SCORE,
            )
            for d in rows
        ]

    def _search_projects(self, pattern: str, limit: int) -> list[SearchItem]:
        rows = self._company_rows(
            Project, pattern, [Project.title, Project.client, Project.description, Project.results], limit
        )
        return [
            SearchItem(
                id=str(p.id),
                kind="projects",
                title=p.title,
                subtitle=_join(p.client, p.sector),
                url=f"/company?tab=projects&id={p.id}",
                score=TEXT_SCORE,
            )
            for p in rows
        ]

    def _search_experts(self, pattern: str, limit: int) -> list[SearchItem]:
        rows = self._company_rows(Expert, pattern, [Expert.full_name, Expert.role, Expert.bio], limit)
        return [
            SearchItem(
                id=str(e.id),
                kind="experts",
                title=e.full_name,
                subtitle=_join(e.role, _years(e)),
                url=f"/company?tab=experts&id={e.id}",
                score=TEXT_SCORE,
            )
            for e in rows
        ]

    def _search_references(self, pattern: str, limit: int) -> list[SearchItem]:
        rows = self._company_rows(
            Reference, pattern, [Reference.client_name, Reference.description, Reference.sector], limit
        )
        return [
            SearchItem(
                id=str(r.id),
                kind="references",
                title=r.client_name,
                subtitle=_join(r.sector, r.description),
                url=f"/company?tab=references&id={r.id}",
                score=TEXT_SCORE,
            )
            for r in rows
        ]

    def _search_certifications(self, pattern: str, limit: int) -> list[SearchItem]:
        rows = self._company_rows(Certification, pattern, [Certification.name, Certification.issuer], limit)
        return [
            SearchItem(
                id=str(c.id),
                kind="certifications",
                title=c.name,
                subtitle=_join(c.issuer, "valide" if c.is_valid else "expirée"),
                url=f"/company?tab=certifications&id={c.id}",
                score=TEXT_SCORE,
            )
            for c in rows
        ]

    # --- recherche sémantique ------------------------------------------------------------------

    def _semantic(self, query: str, wanted: list[str], limit: int) -> list[SearchItem]:
        assert self.embeddings is not None
        items: list[SearchItem] = []
        if "documents" in wanted:
            hits = KnowledgeBase(self.db, self.embeddings).search(query, k=SEMANTIC_K)
            items += self._from_chunks(hits)
        if "tenders" in wanted:
            items += self._similar_tenders(query, limit)
        return items

    def _from_chunks(self, hits: list[KBHit]) -> list[SearchItem]:
        """Un document par morceau retenu, au meilleur score ; une pièce d'AO renvoie vers sa fiche."""
        pieces = {
            d.id: d
            for d in self.db.scalars(
                select(TenderDocument).where(
                    TenderDocument.id.in_([h.owner_id for h in hits if h.owner_kind == "tender_document"])
                )
            )
        }
        best: dict[str, SearchItem] = {}
        for hit in hits:
            piece = pieces.get(hit.owner_id)
            url = (
                f"/tenders/{piece.tender_id}?tab=analysis"
                if piece is not None
                else f"/documents?open={hit.owner_id}"
            )
            key = str(hit.owner_id)
            current = best.get(key)
            if current is not None and current.score >= hit.score:
                continue
            best[key] = SearchItem(
                id=key,
                kind="documents",
                title=hit.document_name,
                subtitle=_join(hit.metadata.get("category"), f"p. {hit.page}" if hit.page else None),
                url=url,
                score=hit.score,
                excerpt=hit.content[:300],
            )
        return list(best.values())

    def _similar_tenders(self, query: str, limit: int) -> list[SearchItem]:
        """« Des opportunités comme celle-ci » : voisinage du vecteur de la fiche (titre + description)."""
        assert self.embeddings is not None
        vector = self.embeddings.embed([query])[0]
        distance = Tender.embedding.cosine_distance(vector)
        stmt = select(Tender, distance).where(Tender.embedding.isnot(None)).order_by(distance).limit(limit)
        return [
            self._tender_item(tender, round(1 - float(dist), 4))
            for tender, dist in self.db.execute(stmt).all()
        ]

    @staticmethod
    def _tender_item(tender: Tender, score: float) -> SearchItem:
        deadline = tender.deadline_at.date().isoformat() if tender.deadline_at else None
        return SearchItem(
            id=str(tender.id),
            kind="tenders",
            title=tender.title,
            subtitle=_join(tender.organization, tender.reference, deadline),
            url=f"/tenders/{tender.id}",
            score=score,
        )


def parse_kinds(raw: str | None) -> list[str] | None:
    """`kinds=tenders,experts` → liste validée ; `None` = tout. Lève `ValueError` sur un inconnu."""
    if raw is None or not raw.strip():
        return None
    asked = [k.strip() for k in raw.split(",") if k.strip()]
    unknown = [k for k in asked if k not in KIND_LABELS]
    if unknown:
        raise ValueError(f"Nature de résultat inconnue : {', '.join(unknown)}")
    return asked
