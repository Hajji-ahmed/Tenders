"""Documents de l'entreprise : dépôt multipart, filtres, versions, téléchargement, archivage (RB-007).

Le stockage est résolu à chaque requête par `deps.get_storage()` (remplaçable par les tests via
`deps._storage_override`) et injecté dans `DocumentService`.
"""

import re
import unicodedata
from datetime import date
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.pagination import PageParams, page_params
from app.core import deps
from app.core.audit import record_audit
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.errors import ConflictError, NotFoundError
from app.models import User
from app.models.document import CompanyDocument, DocumentCategory, DocumentStatus
from app.schemas.common import Page
from app.schemas.document import DocumentOut, DocumentUpdate, DocumentVersionOut, clean_tags
from app.services.company import CompanyService
from app.services.documents import ALLOWED_MIMES, DocumentService

router = APIRouter(prefix="/documents", tags=["documents"], dependencies=[Depends(get_current_user)])


def _service(db: Session, user: User) -> DocumentService:
    return DocumentService(db, deps.get_storage(), user_id=user.id)


def _get_document(db: Session, document_id: UUID) -> CompanyDocument:
    doc = db.get(CompanyDocument, document_id)
    if doc is None:
        raise NotFoundError("Document introuvable")
    return doc


def _read_upload(file: UploadFile) -> tuple[str, bytes, str]:
    """(nom de fichier, octets, type MIME) d'un champ multipart ; le type est validé par le service."""
    return file.filename or "document", file.file.read(), file.content_type or "application/octet-stream"


def sync_expiry_status(doc: CompanyDocument) -> None:
    """RB-007 sans attendre la tâche nocturne : le statut suit la date d'expiration (valid ⇄ expired)."""
    if doc.status == DocumentStatus.valid and doc.is_expired:
        doc.status = DocumentStatus.expired
    elif doc.status == DocumentStatus.expired and not doc.is_expired:
        doc.status = DocumentStatus.valid


def download_name(doc: CompanyDocument) -> str:
    """Nom de fichier proposé au navigateur : le nom d'affichage + l'extension du type MIME si absente."""
    ext = ALLOWED_MIMES.get(doc.mime_type, "")
    return doc.name if doc.name.lower().endswith(ext) else f"{doc.name}{ext}"


def content_disposition(filename: str) -> str:
    """Valeur `Content-Disposition` sûre : nom ASCII entre guillemets, variante UTF-8 (RFC 5987) si besoin."""
    ascii_name = unicodedata.normalize("NFKD", filename).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"[^A-Za-z0-9._ -]+", "_", ascii_name).strip() or "document"
    quoted = quote(filename, safe="")
    if quoted == filename:
        return f'attachment; filename="{filename}"'
    return f"attachment; filename=\"{ascii_name}\"; filename*=utf-8''{quoted}"


@router.post("", response_model=DocumentOut, status_code=201)
def upload_document(
    file: UploadFile = File(...),
    category: DocumentCategory = Form(...),
    name: str | None = Form(None, max_length=255),
    description: str | None = Form(None),
    issued_at: date | None = Form(None),
    expires_at: date | None = Form(None),
    tags: str | None = Form(None, description="Étiquettes séparées par des virgules"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    filename, data, content_type = _read_upload(file)
    meta: dict = {
        "description": description,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "tags": clean_tags(tags.split(",")) if tags else [],
    }
    if name and name.strip():
        meta["name"] = name.strip()
    svc = _service(db, user)
    doc = svc.upload(filename=filename, data=data, content_type=content_type, category=category, **meta)
    db.flush()  # applique les défauts (status=valid) avant la règle d'expiration
    sync_expiry_status(doc)
    db.flush()
    return doc


@router.get("", response_model=Page[DocumentOut])
def list_documents(
    category: DocumentCategory | None = None,
    status: DocumentStatus | None = None,
    tag: str | None = Query(None, max_length=64),
    q: str | None = Query(None, max_length=200, description="Recherche dans le nom et la description"),
    usable_only: bool = False,
    p: PageParams = Depends(page_params),
    db: Session = Depends(get_db),
):
    company = CompanyService.get_or_create(db)
    stmt = select(CompanyDocument).where(CompanyDocument.company_id == company.id)
    if category is not None:
        stmt = stmt.where(CompanyDocument.category == category)
    if status is not None:
        stmt = stmt.where(CompanyDocument.status == status)
    if tag:
        stmt = stmt.where(CompanyDocument.tags.any(tag))
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(CompanyDocument.name.ilike(pattern), CompanyDocument.description.ilike(pattern))
        )
    if usable_only:  # RB-007 : statut `valid` ET date non dépassée (même avant la tâche nocturne)
        stmt = stmt.where(
            CompanyDocument.status == DocumentStatus.valid,
            or_(CompanyDocument.expires_at.is_(None), CompanyDocument.expires_at >= date.today()),
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    # Tri secondaire sur le nom : ordre stable quand plusieurs documents partagent le même instant.
    ordered = stmt.order_by(CompanyDocument.created_at.desc(), CompanyDocument.name)
    rows = db.scalars(ordered.offset((p.page - 1) * p.size).limit(p.size)).all()
    items = [DocumentOut.model_validate(d) for d in rows]
    return Page[DocumentOut](items=items, total=total, page=p.page, size=p.size)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: UUID, db: Session = Depends(get_db)):
    return _get_document(db, document_id)


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: UUID,
    body: DocumentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = _get_document(db, document_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("name") is None:
        data.pop("name", None)  # le nom ne peut pas être vidé
    if "tags" in data and data["tags"] is None:
        data["tags"] = []  # colonne non nulle : `null` = aucune étiquette
    for key, value in data.items():
        setattr(doc, key, value)
    sync_expiry_status(doc)
    db.flush()
    record_audit(
        db,
        action="document.updated",
        entity_kind="company_document",
        entity_id=doc.id,
        payload={"fields": sorted(data)},
        user_id=user.id,
    )
    return doc


@router.post("/{document_id}/versions", response_model=DocumentOut, status_code=201)
def add_version(
    document_id: UUID,
    file: UploadFile = File(...),
    changelog: str | None = Form(None, max_length=2000),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    doc = _get_document(db, document_id)
    if doc.status == DocumentStatus.archived:
        raise ConflictError("Document archivé : impossible d'ajouter une version")
    filename, data, content_type = _read_upload(file)
    svc = _service(db, user)
    doc = svc.new_version(doc, filename=filename, data=data, content_type=content_type, changelog=changelog)
    db.flush()
    return doc


@router.get("/{document_id}/versions", response_model=list[DocumentVersionOut])
def list_versions(document_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    doc = _get_document(db, document_id)
    return _service(db, user).versions(doc)


@router.get("/{document_id}/download")
def download_document(document_id: UUID, db: Session = Depends(get_db)) -> Response:
    doc = _get_document(db, document_id)
    content = deps.get_storage().get(doc.storage_key)
    return Response(
        content=content,
        media_type=doc.mime_type,
        headers={"Content-Disposition": content_disposition(download_name(doc))},
    )


@router.delete("/{document_id}", status_code=204)
def archive_document(
    document_id: UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)
) -> Response:
    """Suppression logique : le document passe `archived` (historique et versions conservés)."""
    doc = _get_document(db, document_id)
    _service(db, user).archive(doc)
    db.flush()
    return Response(status_code=204)
