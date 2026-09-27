"""Dossier de candidature (Phase 9) : sa création depuis une fiche, les documents qu'on y ajoute et
leur export.

Un dossier ne se prépare que sur une opportunité décidée : `GO` (ou déjà en préparation). La
création fait passer la fiche en `PREPARATION` — le cycle de vie de l'opportunité et l'avancement du
dossier ne doivent pas raconter deux histoires différentes."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.storage.base import StorageProvider
from app.core.audit import record_audit
from app.core.errors import ForbiddenTransition, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models import (
    AppDocStatus,
    Application,
    ApplicationDocument,
    ApplicationStatus,
    Template,
    Tender,
    TenderStatus,
    User,
)
from app.services.company_facts import company_facts
from app.services.docx_export import export_docx, export_key
from app.services.tender_status import transition

log = get_logger("applications")

TITLE_MAX_TENDER = 60
ALLOWED_TENDER_STATUSES = (TenderStatus.GO, TenderStatus.PREPARATION, TenderStatus.VALIDATION)


class ApplicationService:
    def __init__(self, db: Session):
        self.db = db

    def create_for_tender(self, tender: Tender, user: User | None = None) -> Application:
        """Ouvre le dossier d'une opportunité décidée. Idempotent : un second appel rend le dossier
        existant plutôt qu'une erreur — l'utilisateur veut y entrer, pas savoir qui l'a ouvert."""
        if tender.application is not None:
            return tender.application
        if TenderStatus(tender.status) not in ALLOWED_TENDER_STATUSES:
            raise ForbiddenTransition(
                f"Un dossier ne se prépare qu'après la décision GO (statut actuel : {tender.status})"
            )
        application = Application(tender_id=tender.id)
        self.db.add(application)
        tender.application = application
        self.db.flush()
        if TenderStatus(tender.status) == TenderStatus.GO:
            transition(
                self.db, tender, TenderStatus.PREPARATION, comment="Dossier de candidature ouvert", user=user
            )
        record_audit(
            self.db,
            action="application.created",
            entity_kind="application",
            entity_id=application.id,
            payload={"tender": tender.title},
            user_id=user.id if user else None,
        )
        self.db.flush()
        log.info("application.created", tender_id=str(tender.id))
        return application

    def add_documents(
        self, application: Application, template_ids: list[UUID], user: User | None = None
    ) -> list[ApplicationDocument]:
        """Ajoute un document par modèle demandé. Un modèle déjà présent n'est pas redoublé : on
        régénère un document, on n'en empile pas deux du même type."""
        templates = list(self.db.scalars(select(Template).where(Template.id.in_(template_ids))))
        missing = set(template_ids) - {t.id for t in templates}
        if missing:
            raise NotFoundError(f"Modèle introuvable : {', '.join(str(m) for m in sorted(missing))}")
        known = {d.template_id for d in application.documents}
        tender = application.tender
        created: list[ApplicationDocument] = []
        for template in sorted(templates, key=lambda t: template_ids.index(t.id)):
            if template.id in known:
                continue
            document = ApplicationDocument(
                document_type=template.document_type,
                title=f"{template.name} — {tender.title[:TITLE_MAX_TENDER]}",
                template=template,
            )
            application.documents.append(document)
            self.db.add(document)
            created.append(document)
        self.db.flush()
        if created:
            record_audit(
                self.db,
                action="application.documents_added",
                entity_kind="application",
                entity_id=application.id,
                payload={"documents": [d.title for d in created]},
                user_id=user.id if user else None,
            )
            self.db.flush()
        return created

    def export(self, storage: StorageProvider, doc: ApplicationDocument) -> ApplicationDocument:
        """Fabrique le DOCX de la version courante et le range dans le stockage."""
        if doc.current_version == 0:
            raise ValidationError("Document non encore généré", code="not_generated")
        facts = company_facts(self.db)
        content = export_docx(doc, facts, tender_title=doc.application.tender.title)
        key = export_key(doc)
        storage.put(key, content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        doc.export_storage_key = key
        self.db.flush()
        record_audit(
            self.db,
            action="application_document.exported",
            entity_kind="application_document",
            entity_id=doc.id,
            payload={"key": key, "version": doc.current_version},
        )
        self.db.flush()
        log.info("application.exported", document=doc.title, key=key)
        return doc

    @staticmethod
    def documents_to_generate(
        application: Application, document_ids: list[UUID] | None
    ) -> list[ApplicationDocument]:
        if document_ids is None:
            return list(application.documents)
        wanted = set(document_ids)
        chosen = [d for d in application.documents if d.id in wanted]
        missing = wanted - {d.id for d in chosen}
        if missing:
            raise NotFoundError(f"Document introuvable dans le dossier : {sorted(str(m) for m in missing)}")
        return chosen

    def set_status_after_generation(self, application: Application) -> ApplicationStatus:
        """Tant qu'un document reste à écrire, le dossier est en préparation ; dès qu'il y a de quoi
        lire, il passe en relecture (RB-006 : rien ne part sans validation humaine)."""
        statuses = {d.status for d in application.documents}
        if AppDocStatus.draft in statuses or AppDocStatus.validated in statuses:
            application.status = ApplicationStatus.review
        elif statuses == {AppDocStatus.failed}:
            application.status = ApplicationStatus.draft
        self.db.flush()
        return ApplicationStatus(application.status)
