from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import AppDocStatus, ApplicationStatus, DocumentType, SectionStatus
from app.schemas.tender import EvidenceOut


class SectionOut(BaseModel):
    id: UUID
    key: str
    title: str
    position: int
    content_md: str | None
    status: SectionStatus
    sources: list[EvidenceOut]
    missing_info: list[str]
    comment: str | None
    prompt_version: str | None
    model: str | None
    generated_at: datetime | None

    model_config = {"from_attributes": True}


class ApplicationDocumentOut(BaseModel):
    id: UUID
    application_id: UUID
    template_id: UUID | None
    document_type: DocumentType
    title: str
    status: AppDocStatus
    current_version: int
    warnings: list[str]
    error: str | None
    has_export: bool = False
    sections: list[SectionOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def of(cls, doc) -> "ApplicationDocumentOut":
        out = cls.model_validate(doc)
        out.has_export = bool(doc.export_storage_key)
        return out


class ApplicationOut(BaseModel):
    id: UUID
    tender_id: UUID
    tender_title: str
    status: ApplicationStatus
    submitted_at: datetime | None
    documents: list[ApplicationDocumentOut] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @classmethod
    def of(cls, application) -> "ApplicationOut":
        return cls(
            id=application.id,
            tender_id=application.tender_id,
            tender_title=application.tender.title,
            status=ApplicationStatus(application.status),
            submitted_at=application.submitted_at,
            documents=[ApplicationDocumentOut.of(d) for d in application.documents],
            created_at=application.created_at,
            updated_at=application.updated_at,
        )


class AddDocumentsIn(BaseModel):
    template_ids: list[UUID] = Field(min_length=1)


class GenerateIn(BaseModel):
    document_ids: list[UUID] | None = Field(
        None, description="Documents à rédiger ; tous ceux du dossier si absent"
    )
