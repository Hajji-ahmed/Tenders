"""Domaine entreprise : identité, profil, compétences, technologies, certifications, experts,
projets et références. Une seule entreprise dans la base (mono-client) — `company_id` reste
explicite pour garder le modèle propre et les cascades simples."""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import ARRAY, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class SkillCategory(enum.StrEnum):
    expertise = "expertise"
    service = "service"
    savoir_faire = "savoir_faire"


class TechnologyCategory(enum.StrEnum):
    language = "language"
    framework = "framework"
    database = "database"
    cloud = "cloud"
    tool = "tool"
    other = "other"


class CertificationCategory(enum.StrEnum):
    technique = "technique"
    qualite = "qualite"
    securite = "securite"
    autre = "autre"


class Company(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    legal_name: Mapped[str] = mapped_column(String(255))
    trade_name: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str | None] = mapped_column(String(2))
    city: Mapped[str | None] = mapped_column(String(128))
    address: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    sectors: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    profile: Mapped["CompanyProfile | None"] = relationship(
        back_populates="company", uselist=False, cascade="all, delete-orphan"
    )
    skills: Mapped[list["Skill"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    technologies: Mapped[list["Technology"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    certifications: Mapped[list["Certification"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    experts: Mapped[list["Expert"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    projects: Mapped[list["Project"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)
    references: Mapped[list["Reference"]] = relationship(cascade="all, delete-orphan", passive_deletes=True)


class CompanyProfile(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "company_profiles"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), unique=True)
    positioning: Mapped[str | None] = mapped_column(Text)
    ai_summary: Mapped[str | None] = mapped_column(Text)
    ai_summary_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    company: Mapped[Company] = relationship(back_populates="profile")


class Skill(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "skills"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[SkillCategory] = mapped_column(String(32), default=SkillCategory.expertise)
    level: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)


class Technology(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "technologies"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[TechnologyCategory] = mapped_column(String(32), default=TechnologyCategory.other)
    level: Mapped[str | None] = mapped_column(String(64))
    years_experience: Mapped[int | None] = mapped_column(Integer)


class Certification(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "certifications"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    issuer: Mapped[str | None] = mapped_column(String(255))
    category: Mapped[CertificationCategory] = mapped_column(String(32), default=CertificationCategory.autre)
    issued_at: Mapped[date | None] = mapped_column(Date)
    expires_at: Mapped[date | None] = mapped_column(Date)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company_documents.id", ondelete="SET NULL")
    )

    @property
    def is_valid(self) -> bool:
        return self.expires_at is None or self.expires_at >= date.today()


class Expert(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "experts"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255))
    years_experience: Mapped[int | None] = mapped_column(Integer)
    skills: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    bio: Mapped[str | None] = mapped_column(Text)
    cv_document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company_documents.id", ondelete="SET NULL")
    )


class Project(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    client: Mapped[str | None] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(128))
    country: Mapped[str | None] = mapped_column(String(2))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str | None] = mapped_column(String(3))
    technologies: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    description: Mapped[str | None] = mapped_column(Text)
    results: Mapped[str | None] = mapped_column(Text)
    is_reference: Mapped[bool] = mapped_column(default=False)


class Reference(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "references"

    company_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("projects.id", ondelete="SET NULL"))
    client_name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("company_documents.id", ondelete="SET NULL")
    )

    project: Mapped[Project | None] = relationship()
