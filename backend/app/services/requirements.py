"""Exigences du dossier (CdC §35) : un appel LLM par pièce lisible, fusion et déduplication
(`token_set_ratio ≥ 92`), codes séquentiels par catégorie (`TECH-001`, `ADM-001`…), source résolue
par nom de fichier. Une ré-extraction rapproche les exigences existantes (description ≥ 95) pour
garder leur identifiant, leur code et — si posé à la main — leur statut ; les autres sont supprimées."""

import re

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.ai.llm import LLMProvider
from app.ai.outputs import RequirementOutput, RequirementsOutput
from app.ai.prompts import requirements_extract
from app.core import deps
from app.core.audit import record_audit
from app.core.logging import get_logger
from app.models import (
    CODE_PREFIX,
    RequirementCategory,
    RequirementStatus,
    Tender,
    TenderDocument,
    TenderRequirement,
)
from app.services.analysis import build_corpus
from app.services.normalize import norm_text

log = get_logger("requirements")

MAX_DOCUMENT_CHARS = 60_000
DUPLICATE_THRESHOLD = 92  # deux exigences lues dans deux pièces qui disent la même chose
MATCH_THRESHOLD = 95  # ré-extraction : même exigence qu'avant
_CODE = re.compile(r"^([A-Z]+)-(\d+)$")


def next_code(prefix: str, existing: list[str]) -> str:
    """Numéro suivant d'un préfixe d'après les codes attribués (`TECH-001`, `TECH-007` ⇒ `TECH-008`)."""
    numbers = [int(m.group(2)) for code in existing if (m := _CODE.match(code)) and m.group(1) == prefix]
    return f"{prefix}-{max(numbers, default=0) + 1:03d}"


def _similar(a: str, b: str, threshold: int) -> bool:
    return fuzz.token_set_ratio(norm_text(a), norm_text(b)) >= threshold


def merge_outputs(outputs: list[RequirementOutput]) -> list[RequirementOutput]:
    """Dédoublonne (première occurrence conservée) ; une version obligatoire l'emporte."""
    kept: list[RequirementOutput] = []
    for candidate in outputs:
        twin = next(
            (k for k in kept if _similar(k.description, candidate.description, DUPLICATE_THRESHOLD)), None
        )
        if twin is None:
            kept.append(candidate)
        elif candidate.is_mandatory and not twin.is_mandatory:
            twin.is_mandatory = True
    return kept


class RequirementsService:
    def __init__(self, db: Session, llm: LLMProvider | None = None):
        self.db = db
        self.llm = llm or deps.get_llm()

    def extract(self, tender: Tender) -> list[TenderRequirement]:
        outputs: list[RequirementOutput] = []
        documents = {d.name: d for d in tender.documents}
        for doc in tender.documents:
            corpus = build_corpus([doc], max_chars=MAX_DOCUMENT_CHARS)
            if not corpus:
                continue
            try:
                result = self.llm.structured(
                    system=requirements_extract.SYSTEM,
                    user=requirements_extract.user_prompt(tender, doc.name, corpus),
                    output=RequirementsOutput,
                    tier="fast",
                )
            except Exception as e:  # noqa: BLE001 — une pièce en échec n'empêche pas les autres
                log.warning(
                    "requirements.document_failed", document=doc.name, error=f"{type(e).__name__}: {e}"
                )
                continue
            for item in result.requirements:
                if not item.source_document or item.source_document not in documents:
                    item.source_document = doc.name  # la pièce interrogée fait foi
                outputs.append(item)
        merged = merge_outputs(outputs)
        rows, counts = self._reconcile(tender, merged, documents)
        record_audit(
            self.db,
            action="tender.requirements_extracted",
            entity_kind="tender",
            entity_id=tender.id,
            payload={"extracted": len(outputs), **counts},
        )
        self.db.flush()
        log.info("requirements.done", tender_id=str(tender.id), **counts)
        return rows

    def _reconcile(
        self, tender: Tender, merged: list[RequirementOutput], documents: dict[str, TenderDocument]
    ) -> tuple[list[TenderRequirement], dict[str, int]]:
        """Rapproche les exigences extraites des existantes ; renvoie les lignes dans l'ordre
        d'extraction et les compteurs (créées, mises à jour, supprimées)."""
        existing = list(tender.requirements)
        codes = [r.code for r in existing]
        unmatched = {id(r) for r in existing}
        rows: list[TenderRequirement] = []
        created = updated = 0
        for item in merged:
            match = next(
                (
                    r
                    for r in existing
                    if id(r) in unmatched and _similar(r.description, item.description, MATCH_THRESHOLD)
                ),
                None,
            )
            source = documents.get(item.source_document or "")
            if match is not None:
                unmatched.discard(id(match))
                self._apply(match, item, source)
                if not match.manual_status:
                    match.status, match.justification, match.evidence = RequirementStatus.A_VERIFIER, None, []
                rows.append(match)
                updated += 1
            else:
                code = next_code(CODE_PREFIX[RequirementCategory(item.category)], codes)
                codes.append(code)
                row = TenderRequirement(code=code, category=item.category, description=item.description)
                self._apply(row, item, source)
                tender.requirements.append(row)
                rows.append(row)
                created += 1
        deleted = 0
        for row in existing:
            if id(row) in unmatched:
                tender.requirements.remove(row)
                deleted += 1
        self.db.flush()
        counts = {"kept": len(rows), "created": created, "updated": updated, "deleted": deleted}
        return rows, counts

    @staticmethod
    def _apply(row: TenderRequirement, item: RequirementOutput, source: TenderDocument | None) -> None:
        if not row.manual_status:
            row.is_mandatory = item.is_mandatory
            row.priority = item.priority
        row.evidence_required = item.evidence_required
        row.source_document = source
        row.source_page = item.source_page
        row.source_excerpt = (item.source_excerpt or None) and item.source_excerpt[:500]
