"""Base de connaissances (Phase 8) : recherche sémantique sur les morceaux indexés — pièces d'appels
d'offres et documents d'entreprise — et fabrication du contexte cité passé aux modèles.

Deux garde-fous portés ici plutôt que chez les appelants : un document d'entreprise inutilisable
(brouillon, expiré, archivé — RB-007) n'est jamais renvoyé par défaut, et chaque extrait rendu porte
sa source (fichier, page) pour que ce qui en sera tiré reste vérifiable (RB-005)."""

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider
from app.models import CompanyDocument, DocumentChunk, TenderDocument
from app.models.document import DocumentStatus

DEFAULT_K = 8
MAX_CONTEXT_CHARS = 8_000


class KBHit(BaseModel):
    chunk_id: UUID
    owner_kind: str
    owner_id: UUID
    document_name: str
    page: int | None = None
    content: str
    score: float  # 1 - distance cosinus : 1 = identique, 0 = sans rapport
    metadata: dict = Field(default_factory=dict)

    @property
    def source(self) -> str:
        """« Kbis.pdf p. 2 » — ce qui est cité dans le contexte et repris dans les preuves."""
        return self.document_name + (f" p. {self.page}" if self.page else "")


class KnowledgeBase:
    def __init__(self, db: Session, embeddings: EmbeddingProvider):
        self.db = db
        self.embeddings = embeddings

    def search(
        self,
        query: str,
        *,
        owner_kind: str | None = None,
        tender_id: UUID | None = None,
        categories: list[str] | None = None,
        usable_only: bool = True,
        k: int = DEFAULT_K,
    ) -> list[KBHit]:
        """Les `k` morceaux les plus proches de `query`, du plus proche au plus lointain.

        `usable_only` ne concerne que les documents d'entreprise : une pièce d'appel d'offres est
        toujours lisible, c'est le dossier à traiter."""
        if k <= 0:
            return []
        vector = self.embeddings.embed([query])[0]
        distance = DocumentChunk.embedding.cosine_distance(vector)
        stmt = (
            select(DocumentChunk, distance, CompanyDocument.name, TenderDocument.name)
            .outerjoin(CompanyDocument, DocumentChunk.company_document_id == CompanyDocument.id)
            .outerjoin(
                TenderDocument,
                and_(
                    DocumentChunk.owner_kind == "tender_document",
                    DocumentChunk.owner_id == TenderDocument.id,
                ),
            )
            .where(DocumentChunk.embedding.isnot(None))
            .order_by(distance)
            .limit(k)
        )
        stmt = self._filter(
            stmt, owner_kind=owner_kind, tender_id=tender_id, categories=categories, usable_only=usable_only
        )
        hits: list[KBHit] = []
        for chunk, dist, company_name, tender_name in self.db.execute(stmt).all():
            meta = dict(chunk.meta or {})
            name = company_name or tender_name or meta.get("name") or "Document"
            hits.append(
                KBHit(
                    chunk_id=chunk.id,
                    owner_kind=str(chunk.owner_kind),
                    owner_id=chunk.owner_id,
                    document_name=meta.get("inner_filename") or name,
                    page=chunk.page,
                    content=chunk.content,
                    score=round(1 - float(dist), 4),
                    metadata=meta,
                )
            )
        return hits

    @staticmethod
    def _filter(
        stmt: Select,
        *,
        owner_kind: str | None,
        tender_id: UUID | None,
        categories: list[str] | None,
        usable_only: bool,
    ) -> Select:
        if owner_kind is not None:
            stmt = stmt.where(DocumentChunk.owner_kind == owner_kind)
        if tender_id is not None:
            stmt = stmt.where(DocumentChunk.tender_id == tender_id)
        if categories:
            stmt = stmt.where(CompanyDocument.category.in_(categories))
        if usable_only:  # RB-007, appliqué aux seuls documents d'entreprise
            stmt = stmt.where(
                or_(
                    DocumentChunk.company_document_id.is_(None),
                    and_(
                        CompanyDocument.status == DocumentStatus.valid,
                        or_(
                            CompanyDocument.expires_at.is_(None),
                            CompanyDocument.expires_at >= date.today(),
                        ),
                    ),
                )
            )
        return stmt

    @staticmethod
    def build_context(hits: list[KBHit], *, max_chars: int = MAX_CONTEXT_CHARS) -> str:
        """Extraits numérotés et sourcés : « [S1] (Kbis.pdf p. 2) … ». Le modèle cite `S1`, `S2`… et
        l'appelant retrouve le morceau ; au-delà de `max_chars`, les extraits suivants sont écartés
        (les mieux classés d'abord)."""
        parts: list[str] = []
        used = 0
        for index, hit in enumerate(hits, start=1):
            block = f"[S{index}] ({hit.source}) {hit.content.strip()}"
            extra = len(block) + (2 if parts else 0)
            if used + extra > max_chars:
                break
            parts.append(block)
            used += extra
        return "\n\n".join(parts)
