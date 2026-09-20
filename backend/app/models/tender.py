"""Recherche et collecte des appels d'offres : profils de recherche, sources, opportunités
(`tenders`), liens de provenance et pièces jointes. La colonne `embedding` de `tenders` sert à la
déduplication sémantique (Phase 4) ; score, décisions et historique sont dans `models/scoring`."""

import enum
import uuid
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin
from app.models.document import ExtractionStatus

if TYPE_CHECKING:
    from app.models.analysis import TenderAnalysis, TenderCriterion
    from app.models.requirement import TenderRequirement
    from app.models.scoring import TenderDecision, TenderScore, TenderStatusHistory


class TenderStatus(enum.StrEnum):
    """Cycle de vie d'une opportunité (cahier des charges §statuts)."""

    NOUVEAU = "NOUVEAU"
    A_ANALYSER = "A_ANALYSER"
    GO = "GO"
    NO_GO = "NO_GO"
    PREPARATION = "PREPARATION"
    VALIDATION = "VALIDATION"
    PRET = "PRET"
    SOUMIS = "SOUMIS"
    GAGNE = "GAGNE"
    PERDU = "PERDU"
    ARCHIVE = "ARCHIVE"


class Urgency(enum.StrEnum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class SourceKind(enum.StrEnum):
    search_engine = "search_engine"
    rss = "rss"
    portal = "portal"
    website = "website"
    api = "api"


class DownloadStatus(enum.StrEnum):
    pending = "pending"
    done = "done"
    failed = "failed"
    skipped = "skipped"


class SearchProfile(UUIDMixin, TimestampMixin, Base):
    """Critères de veille : ce que l'on cherche (mots-clés, secteurs, pays, budget, échéances…)."""

    __tablename__ = "search_profiles"

    name: Mapped[str] = mapped_column(String(255))
    countries: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    regions: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    sectors: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    domains: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    keywords: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    budget_min: Mapped[float | None] = mapped_column(Numeric(14, 2))
    budget_max: Mapped[float | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    organization_types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    market_types: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    technologies: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    certifications: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    experience_level: Mapped[str | None] = mapped_column(String(32))
    deadline_min_days: Mapped[int | None] = mapped_column(Integer)
    deadline_max_days: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TenderSource(UUIDMixin, TimestampMixin, Base):
    """Où l'on cherche : moteur (Tavily), flux RSS, portail, site, API. `config` dépend du type :
    `search_engine` → {include_domains, max_results} ; `portal`/`website` → {listing_paths, link_pattern,
    render_js, max_links} ; `rss` → {}."""

    __tablename__ = "tender_sources"

    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[SourceKind] = mapped_column(String(16), index=True)
    base_url: Mapped[str | None] = mapped_column(String(1024))
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)  # plus petit = interrogée en premier
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[str | None] = mapped_column(String(16))  # ok | error | skipped
    last_error: Mapped[str | None] = mapped_column(Text)


EMBEDDING_DIMENSIONS = 1536  # text-embedding-3-small


class Tender(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "tenders"
    __table_args__ = (
        # Recherche des voisins sémantiques (déduplication RB-001, recherche interne) en distance cosinus.
        Index(
            "ix_tenders_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    reference: Mapped[str | None] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512))
    organization: Mapped[str | None] = mapped_column(String(255))
    organization_type: Mapped[str | None] = mapped_column(String(64))
    country: Mapped[str | None] = mapped_column(String(2), index=True)
    region: Mapped[str | None] = mapped_column(String(128))
    sector: Mapped[str | None] = mapped_column(String(128), index=True)
    market_type: Mapped[str | None] = mapped_column(String(64))
    budget_min: Mapped[float | None] = mapped_column(Numeric(16, 2))
    budget_max: Mapped[float | None] = mapped_column(Numeric(16, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    published_at: Mapped[date | None] = mapped_column(Date)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    questions_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    description: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str | None] = mapped_column(String(40), index=True)  # RB-001 (Phase 4)
    # Formes comparables (services/normalize) : règles « référence + organisme » et « titre proche ».
    norm_title: Mapped[str | None] = mapped_column(String(512))
    norm_org: Mapped[str | None] = mapped_column(String(255), index=True)
    norm_reference: Mapped[str | None] = mapped_column(String(128), index=True)
    status: Mapped[TenderStatus] = mapped_column(String(16), default=TenderStatus.NOUVEAU, index=True)
    urgency: Mapped[Urgency] = mapped_column(String(16), default=Urgency.none)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)  # RB-002
    search_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="SET NULL"), index=True
    )
    raw: Mapped[dict | None] = mapped_column(JSON)  # sortie brute de l'extracteur
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIMENSIONS))  # titre + description

    source_links: Mapped[list["TenderSourceLink"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan", passive_deletes=True
    )
    documents: Mapped[list["TenderDocument"]] = relationship(
        back_populates="tender", cascade="all, delete-orphan", passive_deletes=True
    )
    # Phase 5 (models/scoring) : un score unique, des décisions et un historique de statuts.
    score: Mapped["TenderScore | None"] = relationship(
        back_populates="tender", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )
    decisions: Mapped[list["TenderDecision"]] = relationship(
        back_populates="tender",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TenderDecision.decided_at",
    )
    status_history: Mapped[list["TenderStatusHistory"]] = relationship(
        back_populates="tender",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TenderStatusHistory.changed_at",
    )
    # Phase 6 (models/analysis) : une analyse du dossier et ses critères d'évaluation.
    analysis: Mapped["TenderAnalysis | None"] = relationship(
        back_populates="tender", cascade="all, delete-orphan", passive_deletes=True, uselist=False
    )
    criteria: Mapped[list["TenderCriterion"]] = relationship(
        back_populates="tender",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TenderCriterion.position",
    )
    # Phase 7 (models/requirement) : les exigences du dossier, triées par code.
    requirements: Mapped[list["TenderRequirement"]] = relationship(
        back_populates="tender",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TenderRequirement.code",
    )

    @property
    def days_left(self) -> int | None:
        return None if self.deadline_at is None else (self.deadline_at.date() - date.today()).days

    # Compteurs exposés par l'API : charger `source_links` / `documents` avec selectinload en liste.
    @property
    def source_count(self) -> int:
        return len(self.source_links)

    @property
    def document_count(self) -> int:
        return len(self.documents)

    @property
    def score_total(self) -> float | None:
        return float(self.score.total) if self.score is not None else None


class TenderSourceLink(UUIDMixin, Base):
    """Provenance d'une opportunité : une ligne par URL collectée. L'unicité de `url` empêche de
    réimporter la même page (RB-001) et rend la collecte idempotente."""

    __tablename__ = "tender_source_links"

    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("tender_sources.id", ondelete="SET NULL"), index=True
    )
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    title_seen: Mapped[str | None] = mapped_column(String(512))
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(tz=UTC)
    )
    raw: Mapped[dict | None] = mapped_column(JSON)

    tender: Mapped[Tender] = relationship(back_populates="source_links")
    source: Mapped[TenderSource | None] = relationship()

    @property
    def source_name(self) -> str | None:
        return self.source.name if self.source is not None else None


class TenderDocument(UUIDMixin, TimestampMixin, Base):
    """Pièce d'un appel d'offres (DCE, règlement, annexes). Le téléchargement et l'extraction du
    texte sont faits par les tâches de la Phase 6 ; ici : lien, état et métadonnées."""

    __tablename__ = "tender_documents"

    tender_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenders.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    storage_key: Mapped[str | None] = mapped_column(String(512))
    mime_type: Mapped[str | None] = mapped_column(String(128))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    download_status: Mapped[DownloadStatus] = mapped_column(String(16), default=DownloadStatus.pending)
    extraction_status: Mapped[ExtractionStatus] = mapped_column(String(16), default=ExtractionStatus.pending)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)

    tender: Mapped[Tender] = relationship(back_populates="documents")
