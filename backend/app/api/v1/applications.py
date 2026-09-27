"""Dossier de candidature : ouverture depuis une fiche, ajout de documents, rédaction (job),
lecture, export DOCX et téléchargement."""

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.v1.documents import content_disposition
from app.core import deps
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.models import Application, ApplicationDocument, Tender, User
from app.schemas.application import AddDocumentsIn, ApplicationDocumentOut, ApplicationOut, GenerateIn
from app.schemas.job import JobOut
from app.services.applications import ApplicationService
from app.services.jobs import JobService

GENERATION_JOB = "generate_application_documents"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

router = APIRouter(tags=["applications"], dependencies=[Depends(get_current_user)])


def _application(db: Session, application_id: UUID) -> Application:
    application = db.get(Application, application_id)
    if application is None:
        raise NotFoundError("Dossier de candidature introuvable")
    return application


def _document(db: Session, application_id: UUID, document_id: UUID) -> ApplicationDocument:
    doc = db.get(ApplicationDocument, document_id)
    if doc is None or doc.application_id != application_id:
        raise NotFoundError("Document introuvable dans ce dossier")
    return doc


@router.post("/tenders/{tender_id}/application", response_model=ApplicationOut, status_code=201)
def open_application(tender_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Ouvre le dossier d'une opportunité décidée (GO) et passe la fiche en préparation."""
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise NotFoundError("Opportunité introuvable")
    application = ApplicationService(db).create_for_tender(tender, user=user)
    db.flush()
    return ApplicationOut.of(application)


@router.get("/tenders/{tender_id}/application", response_model=ApplicationOut)
def get_tender_application(tender_id: UUID, db: Session = Depends(get_db)):
    tender = db.get(Tender, tender_id)
    if tender is None:
        raise NotFoundError("Opportunité introuvable")
    if tender.application is None:
        raise NotFoundError("Dossier non ouvert", code="application_missing")
    return ApplicationOut.of(tender.application)


@router.get("/applications/{application_id}", response_model=ApplicationOut)
def get_application(application_id: UUID, db: Session = Depends(get_db)):
    return ApplicationOut.of(_application(db, application_id))


@router.post(
    "/applications/{application_id}/documents",
    response_model=list[ApplicationDocumentOut],
    status_code=201,
)
def add_documents(
    application_id: UUID,
    body: AddDocumentsIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    application = _application(db, application_id)
    created = ApplicationService(db).add_documents(application, body.template_ids, user=user)
    return [ApplicationDocumentOut.of(d) for d in created]


@router.post("/applications/{application_id}/generate", response_model=JobOut, status_code=202)
def generate(application_id: UUID, body: GenerateIn | None = None, db: Session = Depends(get_db)):
    application = _application(db, application_id)
    wanted = body.document_ids if body else None
    ApplicationService.documents_to_generate(application, wanted)  # 404 avant d'enfiler un job perdu
    return JobService.enqueue(
        db,
        GENERATION_JOB,
        entity_kind="application",
        entity_id=application.id,
        application_id=str(application.id),
        document_ids=[str(d) for d in wanted] if wanted else None,
    )


@router.get("/applications/{application_id}/documents/{document_id}", response_model=ApplicationDocumentOut)
def get_document(application_id: UUID, document_id: UUID, db: Session = Depends(get_db)):
    return ApplicationDocumentOut.of(_document(db, application_id, document_id))


@router.post(
    "/applications/{application_id}/documents/{document_id}/export",
    response_model=ApplicationDocumentOut,
)
def export_document(application_id: UUID, document_id: UUID, db: Session = Depends(get_db)):
    """Fabrique le DOCX de la version courante (le regénère si elle a changé)."""
    doc = _document(db, application_id, document_id)
    ApplicationService(db).export(deps.get_storage(), doc)
    return ApplicationDocumentOut.of(doc)


@router.get("/applications/{application_id}/documents/{document_id}/download")
def download_document(application_id: UUID, document_id: UUID, db: Session = Depends(get_db)) -> Response:
    doc = _document(db, application_id, document_id)
    if not doc.export_storage_key:
        ApplicationService(db).export(deps.get_storage(), doc)
    content = deps.get_storage().get(doc.export_storage_key or "")
    return Response(
        content=content,
        media_type=DOCX_MIME,
        headers={"Content-Disposition": content_disposition(f"{doc.title}.docx")},
    )
