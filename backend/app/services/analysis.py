"""Analyse IA structurée d'un dossier (CdC §35) : corpus des pièces extraites avec marqueurs de page
— pièces réglementaires (RC, CCTP, CCAP, règlement, cahier) d'abord, plafond de 120 000 caractères —,
lecture par le modèle, persistance de l'analyse (une par fiche, écrasée) et de ses critères,
enrichissement de la fiche (résumé, échéance manquante, référence, pièces demandées), audit."""

import re

from sqlalchemy.orm import Session

from app.ai.llm import LLMProvider
from app.ai.outputs import DatedItem, TenderAnalysisOutput
from app.ai.prompts import tender_analysis
from app.core import deps
from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import get_logger
from app.models import ExtractionStatus, Tender, TenderAnalysis, TenderCriterion, TenderDocument
from app.services.dedup import end_of_day
from app.services.indexing import PAGE_SEPARATOR
from app.services.normalize import LIMITS, clip

log = get_logger("analysis")

MAX_CORPUS_CHARS = 120_000
TRUNCATED_MARK = "\n[… texte tronqué …]"
_PRIORITY = re.compile(r"\b(RC|CCTP|CCAP|r[eè]glement|cahier)\b", re.IGNORECASE)
_DEADLINE = re.compile(r"limite|remise|d[ée]p[oô]t|soumission|deadline", re.IGNORECASE)


def _is_priority(doc: TenderDocument) -> bool:
    return bool(_PRIORITY.search(doc.name))


def build_corpus(documents: list[TenderDocument], max_chars: int = MAX_CORPUS_CHARS) -> str:
    """Texte des pièces extraites, une section `=== fichier — page n ===` par page, pièces
    réglementaires en tête ; au-delà du plafond, la section en cours est coupée et le reste ignoré."""
    usable = [d for d in documents if d.extraction_status == ExtractionStatus.done and d.extracted_text]
    ordered = [d for d in usable if _is_priority(d)] + [d for d in usable if not _is_priority(d)]
    parts: list[str] = []
    used = 0
    for doc in ordered:
        for number, text in enumerate((doc.extracted_text or "").split(PAGE_SEPARATOR), start=1):
            if not text.strip():
                continue
            section = f"=== {doc.name} — page {number} ===\n{text.strip()}"
            remaining = max_chars - used
            if remaining <= 0:
                return "\n\n".join(parts) + TRUNCATED_MARK
            if len(section) > remaining:
                parts.append(section[:remaining] + TRUNCATED_MARK)
                return "\n\n".join(parts)
            parts.append(section)
            used += len(section) + 2
    return "\n\n".join(parts)


def deadline_from(key_dates: list[DatedItem]) -> DatedItem | None:
    return next((d for d in key_dates if d.date and _DEADLINE.search(d.label)), None)


class AnalysisService:
    def __init__(self, db: Session, llm: LLMProvider | None = None):
        self.db = db
        self.llm = llm or deps.get_llm()

    def analyze(self, tender: Tender) -> TenderAnalysis:
        corpus = build_corpus(tender.documents)
        if not corpus:
            raise AppError(
                "Aucun document exploitable : téléchargez ou déposez les pièces du dossier",
                code="no_documents",
                status_code=422,
            )
        output = self.llm.structured(
            system=tender_analysis.SYSTEM,
            user=tender_analysis.user_prompt(tender, corpus),
            output=TenderAnalysisOutput,
            tier="fast",
        )
        analysis = self._persist(tender, output)
        self._enrich_tender(tender, output)
        record_audit(
            self.db,
            action="tender.analyzed",
            entity_kind="tender",
            entity_id=tender.id,
            payload={"criteria": len(output.evaluation_criteria), "corpus_chars": len(corpus)},
        )
        self.db.flush()
        log.info(
            "analysis.done",
            tender_id=str(tender.id),
            criteria=len(output.evaluation_criteria),
            corpus_chars=len(corpus),
        )
        return analysis

    def _persist(self, tender: Tender, output: TenderAnalysisOutput) -> TenderAnalysis:
        analysis = tender.analysis or TenderAnalysis(tender_id=tender.id)
        analysis.object = output.object
        analysis.organization = clip(output.organization, 255)
        analysis.reference = clip(output.reference, 128)
        analysis.budget = clip(output.budget, 255)
        analysis.duration = clip(output.duration, 255)
        analysis.location = clip(output.location, 255)
        analysis.key_dates = [d.model_dump(mode="json") for d in output.key_dates]
        analysis.deliverables = list(output.deliverables)
        analysis.requested_documents = [d.model_dump(mode="json") for d in output.requested_documents]
        analysis.eligibility_conditions = list(output.eligibility_conditions)
        analysis.summary = output.summary
        analysis.model = get_settings().openai_model_fast
        analysis.prompt_version = tender_analysis.PROMPT_VERSION
        tender.analysis = analysis
        tender.criteria = [
            TenderCriterion(
                position=index,
                name=clip(c.name, 255) or "Critère",
                weight=c.weight,
                description=c.description,
                source_page=c.source_page,
            )
            for index, c in enumerate(output.evaluation_criteria)
        ]
        return analysis

    def _enrich_tender(self, tender: Tender, output: TenderAnalysisOutput) -> None:
        """Complète la fiche sans jamais écraser une valeur déjà connue."""
        tender.summary = output.summary
        if tender.deadline_at is None and (found := deadline_from(output.key_dates)):
            tender.deadline_at = end_of_day(found.date)
        if not tender.reference and output.reference:
            tender.reference = clip(output.reference, LIMITS["reference"])
        if not tender.organization and output.organization:
            tender.organization = clip(output.organization, LIMITS["organization"])
        extra = dict(tender.extra or {})
        extra["requested_documents"] = [d.model_dump(mode="json") for d in output.requested_documents]
        tender.extra = extra  # nouvel objet : SQLAlchemy détecte le changement de la colonne JSON
