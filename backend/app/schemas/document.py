from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.models.document import DocumentCategory, DocumentStatus, ExtractionStatus


def clean_tags(values: list[str]) -> list[str]:
    """Étiquettes nettoyées : espaces retirés, vides ignorées, doublons supprimés, ordre conservé."""
    return list(dict.fromkeys(t.strip() for t in values if t and t.strip()))


class DocumentOut(BaseModel):
    """Métadonnées d'un document entreprise (jamais `storage_key` ni `extracted_text`)."""

    id: UUID
    company_id: UUID
    name: str
    category: DocumentCategory
    mime_type: str
    size_bytes: int
    sha256: str
    version: int
    status: DocumentStatus
    issued_at: date | None
    expires_at: date | None
    description: str | None
    tags: list[str]
    extraction_status: ExtractionStatus
    is_expired: bool  # date d'expiration dépassée (propriété du modèle)
    is_usable: bool  # RB-007 : statut `valid` ET non expiré — seul un tel document alimente les candidatures
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUpdate(BaseModel):
    """Métadonnées modifiables. Le fichier lui-même change via POST /documents/{id}/versions,
    le statut via DELETE (archivage) et la règle d'expiration (RB-007)."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: DocumentCategory | None = None
    description: str | None = None
    issued_at: date | None = None
    expires_at: date | None = None
    tags: list[str] | None = None

    @field_validator("tags")
    @classmethod
    def _clean(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else clean_tags(value)


class DocumentVersionOut(BaseModel):
    id: UUID
    document_id: UUID
    version_number: int
    sha256: str
    author: str | None
    changelog: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
