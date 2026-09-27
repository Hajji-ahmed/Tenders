"""Génération des sections d'un document de candidature (Phase 9).

Une section à la fois : on rassemble ce qu'elle a le droit de lire (`generation_context`), le modèle
rédige, puis on garde trace de ce sur quoi il s'est appuyé (`sources`) et de ce qui lui a manqué
(`missing_info`). Une section qui échoue n'arrête pas le document — elle est écrite en clair comme
échouée, et la suite continue : un dossier à moitié rédigé se relit, un job perdu ne se relit pas.

Le texte produit passe ensuite par `FactGuard`, dont les avertissements restent attachés au document
jusqu'à la validation humaine (RB-005)."""

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.ai.llm import LLMProvider
from app.ai.outputs import SectionOutput
from app.ai.prompts import section_generate
from app.core import deps
from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import (
    AppDocStatus,
    ApplicationDocument,
    ApplicationSection,
    SectionStatus,
    Tender,
)
from app.services.company_facts import company_facts
from app.services.fact_guard import FactGuard
from app.services.generation_context import GenerationContext, build_context
from app.services.knowledge import KnowledgeBase

log = get_logger("generation")

FAILED_PREFIX = "[Génération échouée"
Progress = Callable[[int, str], None]


def failure_text(title: str, error: Exception) -> str:
    return f"{FAILED_PREFIX} pour « {title} » : {type(error).__name__}]"


class GenerationService:
    def __init__(self, db: Session, llm: LLMProvider | None = None, kb: KnowledgeBase | None = None):
        self.db = db
        self.llm = llm or deps.get_llm()
        self.kb = kb
        self.model = get_settings().openai_model_strong

    # --- une section ---------------------------------------------------------------------------

    def write_section(
        self,
        tender: Tender,
        spec: dict,
        *,
        repeat_item: dict | None = None,
        previous: str | None = None,
        instruction: str | None = None,
    ) -> tuple[SectionOutput, GenerationContext]:
        """Rédige une section. Lève si le modèle échoue : l'appelant décide quoi en faire."""
        context = build_context(self.db, self.kb, tender, spec, repeat_item=repeat_item)
        output = self.llm.structured(
            system=section_generate.SYSTEM,
            user=section_generate.user_prompt(context, previous=previous, instruction=instruction),
            output=SectionOutput,
            tier="strong",  # c'est le texte qui sera lu par l'acheteur
        )
        return output, context

    @staticmethod
    def cited_sources(output: SectionOutput, context: GenerationContext) -> list[dict]:
        """Les extraits réellement cités, dans la forme des preuves d'éligibilité (8.4) : un
        identifiant inventé par le modèle ne donne aucune source."""
        sources: list[dict] = []
        for ref in output.used_sources:
            digits = "".join(ch for ch in str(ref) if ch.isdigit())
            if not digits:
                continue
            index = int(digits)
            if 1 <= index <= len(context.kb_hits):
                hit = context.kb_hits[index - 1]
                source = {
                    "kind": "chunk",
                    "id": str(hit.chunk_id),
                    "label": hit.source,
                    "document_id": str(hit.owner_id),
                    "page": hit.page,
                }
                if source not in sources:
                    sources.append(source)
        return sources

    def _apply(self, section: ApplicationSection, output: SectionOutput, context: GenerationContext) -> None:
        section.content_md = output.content_md.strip()
        section.sources = self.cited_sources(output, context)
        section.missing_info = [m for m in output.missing_info if m and m.strip()]
        section.status = SectionStatus.generated
        section.prompt_version = section_generate.PROMPT_VERSION
        section.model = self.model
        section.generated_at = datetime.now(tz=UTC)

    # --- un document ---------------------------------------------------------------------------

    def generate_document(
        self, doc: ApplicationDocument, *, on_progress: Progress | None = None
    ) -> ApplicationDocument:
        """Rédige toutes les sections du modèle, dans l'ordre du plan. Le document finit `draft`
        même si des sections ont échoué : ce qui est écrit vaut d'être relu."""
        template = doc.template
        if template is None or not template.sections:
            raise ValueError(f"Document sans modèle de sections : {doc.title}")
        tender = doc.application.tender
        specs = list(template.sections)
        existing = {s.key: s for s in doc.sections}
        doc.status = AppDocStatus.generating
        doc.error = None
        self.db.flush()

        failures = 0
        for position, spec in enumerate(specs):
            title = spec.get("title", spec.get("key", ""))
            if on_progress is not None:
                on_progress(int(position * 100 / max(len(specs), 1)), f"{doc.title} — {title}")
            section = existing.get(spec["key"])
            if section is None:
                section = ApplicationSection(key=spec["key"], title=title, position=position)
                doc.sections.append(section)
                self.db.add(section)
            section.title, section.position = title, position
            try:
                output, context = self.write_section(tender, spec, repeat_item=self._subject(doc))
            except Exception as e:  # noqa: BLE001 — une section perdue n'emporte pas le document
                failures += 1
                log.warning(
                    "generation.section_failed", document=doc.title, section=spec["key"], error=str(e)
                )
                section.content_md = failure_text(title, e)
                section.sources, section.missing_info = [], [f"Section à reprendre : {title}"]
                section.status = SectionStatus.generated
                continue
            self._apply(section, output, context)

        doc.current_version += 1
        doc.status = AppDocStatus.draft
        doc.warnings = self.review(doc, tender)
        self.db.flush()
        record_audit(
            self.db,
            action="application_document.generated",
            entity_kind="application_document",
            entity_id=doc.id,
            payload={
                "title": doc.title,
                "sections": len(doc.sections),
                "failed": failures,
                "warnings": len(doc.warnings),
                "version": doc.current_version,
            },
        )
        self.db.flush()
        log.info(
            "generation.document_done",
            document=doc.title,
            sections=len(doc.sections),
            failed=failures,
            warnings=len(doc.warnings),
        )
        return doc

    def regenerate_section(
        self, section: ApplicationSection, instruction: str | None = None
    ) -> ApplicationSection:
        """Reprend une section : le modèle revoit son texte à la lumière de la demande de l'utilisateur."""
        doc = section.document
        template = doc.template
        spec = next((s for s in (template.sections if template else []) if s["key"] == section.key), None)
        if spec is None:  # le plan a changé depuis : on garde le titre et la consigne d'origine
            spec = {
                "key": section.key,
                "title": section.title,
                "instructions": "Reprendre cette section.",
                "max_words": 400,
                "requires": ["company_facts", "tender_analysis"],
            }
        tender = doc.application.tender
        output, context = self.write_section(
            tender,
            spec,
            repeat_item=self._subject(doc),
            previous=section.content_md,
            instruction=instruction,
        )
        self._apply(section, output, context)
        doc.warnings = self.review(doc, tender)
        self.db.flush()
        record_audit(
            self.db,
            action="application_section.regenerated",
            entity_kind="application_document",
            entity_id=doc.id,
            payload={"section": section.key, "instruction": instruction},
        )
        self.db.flush()
        return section

    # --- relecture automatique -----------------------------------------------------------------

    def review(self, doc: ApplicationDocument, tender: Tender) -> list[str]:
        """Avertissements du garde anti-invention sur l'ensemble du document (RB-005)."""
        facts = company_facts(self.db)
        allowed = [x for x in (tender.organization, tender.title) if x]
        guard = FactGuard(allowed_names=allowed)
        seen: list[str] = []
        for section in doc.sections:
            for warning in guard.check(section.content_md or "", facts):
                text = f"{section.title} — {warning}"
                if text not in seen:
                    seen.append(text)
        return seen

    @staticmethod
    def _subject(doc: ApplicationDocument) -> dict | None:
        """Le sujet d'un document répétable, tel qu'il a été fixé à la création (9.4)."""
        if not doc.subject_kind:
            return None
        return {"kind": doc.subject_kind, "label": doc.title, "data": {"id": str(doc.subject_id)}}
