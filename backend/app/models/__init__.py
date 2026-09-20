# Importer ici CHAQUE modèle pour qu'Alembic les voie lors de l'autogénération.
from app.models.analysis import TenderAnalysis, TenderCriterion
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.chunk import ChunkOwnerKind, DocumentChunk
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
from app.models.requirement import (
    CODE_PREFIX,
    Priority,
    RequirementCategory,
    RequirementStatus,
    TenderRequirement,
)
from app.models.scoring import DecisionKind, TenderDecision, TenderScore, TenderStatusHistory
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
    "CODE_PREFIX",
    "AuditLog",
    "Base",
    "Certification",
    "CertificationCategory",
    "ChunkOwnerKind",
    "Company",
    "CompanyDocument",
    "CompanyProfile",
    "DecisionKind",
    "DocumentCategory",
    "DocumentChunk",
    "DocumentKind",
    "DocumentStatus",
    "DocumentVersion",
    "DownloadStatus",
    "Expert",
    "ExtractionStatus",
    "Job",
    "JobStatus",
    "Priority",
    "Project",
    "Reference",
    "RequirementCategory",
    "RequirementStatus",
    "SearchProfile",
    "Skill",
    "SkillCategory",
    "SourceKind",
    "Technology",
    "TechnologyCategory",
    "Tender",
    "TenderAnalysis",
    "TenderCriterion",
    "TenderDecision",
    "TenderDocument",
    "TenderRequirement",
    "TenderScore",
    "TenderSource",
    "TenderSourceLink",
    "TenderStatus",
    "TenderStatusHistory",
    "Urgency",
    "User",
]
