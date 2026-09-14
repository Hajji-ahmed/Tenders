# Importer ici CHAQUE modèle pour qu'Alembic les voie lors de l'autogénération.
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.company import (
    Certification,
    CertificationCategory,
    Company,
    CompanyProfile,
    Expert,
    Project,
    Reference,
    Skill,
    SkillCategory,
    Technology,
    TechnologyCategory,
)
from app.models.document import (
    CompanyDocument,
    DocumentCategory,
    DocumentKind,
    DocumentStatus,
    DocumentVersion,
    ExtractionStatus,
)
from app.models.job import Job, JobStatus
from app.models.tender import (
    DownloadStatus,
    SearchProfile,
    SourceKind,
    Tender,
    TenderDocument,
    TenderSource,
    TenderSourceLink,
    TenderStatus,
    Urgency,
)
from app.models.user import User

__all__ = [
    "AuditLog",
    "Base",
    "Certification",
    "CertificationCategory",
    "Company",
    "CompanyDocument",
    "CompanyProfile",
    "DocumentCategory",
    "DocumentKind",
    "DocumentStatus",
    "DocumentVersion",
    "DownloadStatus",
    "Expert",
    "ExtractionStatus",
    "Job",
    "JobStatus",
    "Project",
    "Reference",
    "SearchProfile",
    "Skill",
    "SkillCategory",
    "SourceKind",
    "Technology",
    "TechnologyCategory",
    "Tender",
    "TenderDocument",
    "TenderSource",
    "TenderSourceLink",
    "TenderStatus",
    "Urgency",
    "User",
]
