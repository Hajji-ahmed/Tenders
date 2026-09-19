"""Morceaux de texte vectorisés (`document_chunks`) : le corpus interrogeable des pièces d'appels
d'offres et des documents d'entreprise (recherche sémantique, analyse, questions). Le propriétaire
est polymorphe (`owner_kind` + `owner_id`) ; `tender_id` / `company_document_id` portent les
cascades de suppression."""

import enum
import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDMixin
from app.models.tender import EMBEDDING_DIMENSIONS


class ChunkOwnerKind(enum.StrEnum):
    tender_document = "tender_document"
    company_document = "company_document"


class DocumentChunk(UUIDMixin, Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        Index("ix_document_chunks_owner", "owner_kind", "owner_id"),
        Index(
            "ix_document_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    owner_kind: Mapped[ChunkOwnerKind] = mapped_column(String(24))
    owner_id: Mapped[uuid.UUID]  # TenderDocument.id ou CompanyDocument.id (pas de clé étrangère)
    tender_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tenders.id", ondelete="CASCADE"), index=True
    )
    company_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company_documents.id", ondelete="CASCADE"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))
    token_count: Mapped[int | None] = mapped_column(Integer)
    # `metadata` est réservé par SQLAlchemy : l'attribut s'appelle `meta`, la colonne `metadata`.
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
