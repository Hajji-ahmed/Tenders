"""Pièces d'un appel d'offres : liste, dépôt manuel (multipart), récupération des pièces découvertes
par un job, téléchargement d'une pièce déjà acquise."""

from uuid import UUID

from fastapi import APIRouter, Depends, File, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.documents import content_disposition
from app.core import deps
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.models import DownloadStatus, Tender, TenderDocument, User
from app.schemas.job import JobOut
from app.schemas.tender import TenderDocumentOut
from app.services.jobs import JobService
from app.services.tender_documents import TenderDocumentService

FETCH_JOB = "download_tender_documents"

router = APIRouter(prefix="/tenders", tags=["tender-documents"], dependencies=[Depends(get_current_user)])


def _tender_or_404(db: Session, tender_id: UUID) -> Tender:
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise NotFoundError("Opportunité introuvable")
    return tender


def _document_or_404(db: Session, tender_id: UUID, document_id: UUID) -> TenderDocument:
    doc = db.get(TenderDocument, document_id)
    if doc is None or doc.tender_id != tender_id:
        raise NotFoundError("Pièce introuvable")
    return doc


@router.get("/{tender_id}/documents", response_model=list[TenderDocumentOut])
def list_tender_documents(tender_id: UUID, db: Session = Depends(get_db)):
    tender = _tender_or_404(db, tender_id)
    return sorted(tender.documents, key=lambda d: (d.created_at, d.name))


@router.post("/{tender_id}/documents", response_model=TenderDocumentOut, status_code=201)
def upload_tender_document(
    tender_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tender = _tender_or_404(db, tender_id)
    service = TenderDocumentService(db, deps.get_storage(), deps.get_download_client())
    return service.upload_manual(
        tender,
        filename=file.filename or "document",
        data=file.file.read(),
        content_type=file.content_type or "application/octet-stream",
        user_id=user.id,
    )


@router.post("/{tender_id}/documents/fetch", response_model=JobOut, status_code=202)
def fetch_tender_documents(tender_id: UUID, db: Session = Depends(get_db)):
    """Enfile le téléchargement des pièces connues (URL de l'annonce + pièces en attente)."""
    tender = _tender_or_404(db, tender_id)
    return JobService.enqueue(
        db, FETCH_JOB, entity_kind="tender", entity_id=tender.id, tender_id=str(tender.id)
    )


@router.get("/{tender_id}/documents/{document_id}/download")
def download_tender_document(tender_id: UUID, document_id: UUID, db: Session = Depends(get_db)) -> Response:
    doc = _document_or_404(db, tender_id, document_id)
    if doc.download_status != DownloadStatus.done or not doc.storage_key:
        raise NotFoundError("Pièce non téléchargée", code="not_downloaded")
    return Response(
        content=deps.get_storage().get(doc.storage_key),
        media_type=doc.mime_type or "application/octet-stream",
        headers={"Content-Disposition": content_disposition(doc.name)},
    )
