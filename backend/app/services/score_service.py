"""Score d'une opportunité (CdC §35) : règles déterministes (services/scoring) + lecture IA
(justification, forces/faiblesses, ajustement borné à ± 10). RB-004 : un score a toujours une
justification — si le modèle échoue, elle est remplacée par le résumé des sous-scores et
l'ajustement vaut 0. Au-delà du seuil de pertinence, une fiche NOUVEAU passe A_ANALYSER."""

from sqlalchemy.orm import Session

from app.ai.llm import LLMProvider
from app.ai.outputs import ScoreAssessment
from app.ai.prompts import score_assessment
from app.core import deps
from app.core.audit import record_audit
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models import SearchProfile, Tender, TenderScore, TenderStatus, TenderStatusHistory
from app.services.company import CompanyService
from app.services.scoring import LABELS, SCORING_VERSION, ScoreResult, compute_score

log = get_logger("scoring")

MAX_ADJUSTMENT = 10
FALLBACK_PREFIX = "Justification IA indisponible : "


class ScoreService:
    def __init__(self, db: Session, llm: LLMProvider | None = None):
        self.db = db
        self.llm = llm or deps.get_llm()

    def score_tender(self, tender: Tender) -> TenderScore:
        company = CompanyService.get_or_create(self.db)
        profile = self.db.get(SearchProfile, tender.search_profile_id) if tender.search_profile_id else None
        eligibility_ratio = ((tender.extra or {}).get("eligibility") or {}).get("ratio")
        result = compute_score(tender, company, profile, eligibility_ratio)

        assessment, model = self._assess(tender, company, result)
        if assessment is not None:
            adjustment = max(-MAX_ADJUSTMENT, min(MAX_ADJUSTMENT, assessment.adjustment))
            justification = assessment.justification.strip() or FALLBACK_PREFIX + result.summary()
            strengths = assessment.strengths or [LABELS[k] for k in result.strengths]
            weaknesses = assessment.weaknesses or [LABELS[k] for k in result.weaknesses]
            prompt_version: str | None = score_assessment.PROMPT_VERSION
        else:
            adjustment, model, prompt_version = 0, None, None
            justification = FALLBACK_PREFIX + result.summary()
            strengths = [LABELS[k] for k in result.strengths]
            weaknesses = [LABELS[k] for k in result.weaknesses]
        total = round(max(0.0, min(100.0, result.total + adjustment)), 1)

        score = tender.score or TenderScore(tender_id=tender.id)
        score.total = total
        score.breakdown = [s.model_dump() for s in result.breakdown]
        score.strengths = strengths
        score.weaknesses = weaknesses
        score.justification = justification
        score.ai_adjustment = adjustment
        score.model = model
        score.prompt_version = prompt_version
        score.scoring_version = SCORING_VERSION
        tender.score = score

        self._promote_if_relevant(tender, total)
        record_audit(
            self.db,
            action="tender.scored",
            entity_kind="tender",
            entity_id=tender.id,
            payload={"total": total, "adjustment": adjustment, "scoring_version": SCORING_VERSION},
        )
        self.db.flush()
        log.info("scoring.done", tender_id=str(tender.id), total=total, adjustment=adjustment)
        return score

    def _assess(
        self, tender: Tender, company, result: ScoreResult
    ) -> tuple[ScoreAssessment | None, str | None]:
        """Lecture IA du score ; `(None, None)` si le modèle échoue (RB-004 : on n'attend pas)."""
        try:
            assessment = self.llm.structured(
                system=score_assessment.SYSTEM,
                user=score_assessment.user_prompt(tender, company, result),
                output=ScoreAssessment,
                tier="fast",
            )
        except Exception as e:  # noqa: BLE001 — quota, réseau, refus : le score reste calculable
            log.warning(
                "scoring.assessment_failed", tender_id=str(tender.id), error=f"{type(e).__name__}: {e}"
            )
            return None, None
        return assessment, get_settings().openai_model_fast

    def _promote_if_relevant(self, tender: Tender, total: float) -> None:
        threshold = get_settings().relevance_threshold
        if tender.status != TenderStatus.NOUVEAU or total < threshold:
            return
        tender.status_history.append(
            TenderStatusHistory(
                from_status=TenderStatus.NOUVEAU,
                to_status=TenderStatus.A_ANALYSER,
                comment=f"Score {total:g} ≥ seuil de pertinence {threshold}",
            )
        )
        tender.status = TenderStatus.A_ANALYSER
