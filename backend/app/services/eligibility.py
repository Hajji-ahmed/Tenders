"""Moteur d'éligibilité par règles (Phase 7) : chaque exigence est jugée contre le profil de
l'entreprise selon sa catégorie — certifications valides, technologies et compétences citées,
références et ancienneté des experts, rôles d'équipe, documents utilisables (RB-007) — avec les
preuves retenues. Une réponse de l'utilisateur prime sur les règles. `evaluate` persiste les
jugements (les statuts saisis à la main sont conservés), résume (ratio, obligatoires non
satisfaites — RB-003), relance le score avec le ratio et signale chaque obligatoire non satisfaite."""

import re
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field
from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm import LLMProvider
from app.core.audit import record_audit
from app.core.logging import get_logger
from app.models import (
    Company,
    CompanyDocument,
    RequirementCategory,
    RequirementStatus,
    Tender,
    TenderRequirement,
)
from app.models.document import DocumentCategory
from app.services.normalize import norm_text
from app.services.score_service import ScoreService

log = get_logger("eligibility")

S = RequirementStatus
C = RequirementCategory
FUZZY = 85
MIN_WORD = 4  # mots significatifs d'une description (« fiscale », « cnss »…)
# Mots trop génériques pour rapprocher une exigence d'un document : « attestation » désignerait
# n'importe quelle attestation, « obligatoire » n'importe quelle étiquette.
GENERIC_WORDS = frozenset(
    [
        "attestation", "certificat", "document", "documents", "piece", "pieces", "fournir", "fourniture",
        "justifier", "justificatif", "obligatoire", "obligatoires", "valide", "validite", "cours", "moins",
        "jour", "jours", "dans", "pour", "avec", "sans", "copie", "original", "declaration", "extrait",
        "releve", "dossier", "candidat", "candidature", "offre", "offres",
    ]
)  # fmt: skip
# Sur la forme normalisée (sans accents) : « deux references », « 5 ans », « 3 projets ».
_NUMBER = re.compile(r"(\d+)\s*(ans|annees|projets?|references?)")
_WORDS = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "dix": 10}
_NUMBER_WORDS = re.compile(r"\b(un|une|deux|trois|quatre|cinq|six|dix)\s+(ans|annees|projets?|references?)")
_YES = re.compile(r"\boui\b|\bok\b|\baffirmatif\b", re.IGNORECASE)
_NO = re.compile(r"\bnon\b|\bpas\b|\baucun", re.IGNORECASE)
DOCUMENT_CATEGORIES: dict[RequirementCategory, tuple[DocumentCategory, ...]] = {
    C.administrative: (DocumentCategory.administratif, DocumentCategory.attestation),
    C.financiere: (DocumentCategory.financier,),
    C.juridique: (DocumentCategory.juridique,),
}


class Evidence(BaseModel):
    kind: Literal["certification", "technology", "skill", "expert", "project", "document", "answer", "chunk"]
    id: str
    label: str


class Judgement(BaseModel):
    status: RequirementStatus
    justification: str
    evidence: list[Evidence] = Field(default_factory=list)


class EligibilitySummary(BaseModel):
    total: int
    by_status: dict[str, int]
    mandatory_unmet: list[str]  # codes des exigences obligatoires NON_CONFORME | INFO_MANQUANTE
    ratio: float  # (CONFORME + 0,5 × A_VERIFIER) / total ; 1.0 sans exigence
    evaluated_at: str | None = None


class AnswerLike(Protocol):
    """Réponse de l'utilisateur à une question liée à l'exigence (modèle `QuestionAnswer`, 7.3)."""

    @property
    def id(self) -> Any: ...

    @property
    def text(self) -> str: ...


def _mentions(term: str, text: str) -> bool:
    """`term` (nom de certification, technologie, rôle…) apparaît dans `text`, à peu près. Un terme
    court (« Go », « R », « SQL ») n'est reconnu que comme mot entier : le flou inventerait des liens."""
    t, x = norm_text(term), norm_text(text)
    if not t:
        return False
    if len(t) < 5:
        return re.search(rf"\b{re.escape(t)}\b", x) is not None
    return t in x or fuzz.partial_ratio(t, x) >= FUZZY


def _numbers(text: str) -> list[tuple[int, str]]:
    plain = norm_text(text)
    found = [(int(n), unit) for n, unit in _NUMBER.findall(plain)]
    found += [(_WORDS[w], unit) for w, unit in _NUMBER_WORDS.findall(plain)]
    return found


def _label(*parts: str | None) -> str:
    return " — ".join(p for p in parts if p)


class EligibilityEngine:
    def __init__(
        self,
        db: Session,
        company: Company,
        *,
        llm: LLMProvider | None = None,
        on_mandatory_unmet: Callable[[Tender, TenderRequirement], None] | None = None,
    ):
        self.db = db
        self.company = company
        self.llm = llm
        self.tender: Tender | None = None  # posé par `evaluate` : contexte (secteur) des règles d'expérience
        self.on_mandatory_unmet = on_mandatory_unmet or self._log_unmet

    # --- jugement d'une exigence ---------------------------------------------------------------

    def judge(self, req: TenderRequirement, answers: Sequence[AnswerLike]) -> Judgement:
        if answers:
            return self._from_answer(answers[-1])
        match RequirementCategory(req.category):
            case C.certification:
                return self._certification(req)
            case C.technique:
                return self._technique(req)
            case C.experience:
                return self._experience(req)
            case C.equipe:
                return self._team(req)
            case C.administrative | C.financiere | C.juridique:
                return self._document(req)
        return Judgement(
            status=S.A_VERIFIER, justification="À apprécier par un humain (méthodologie / divers)"
        )

    def _from_answer(self, answer: AnswerLike) -> Judgement:
        evidence = [Evidence(kind="answer", id=str(answer.id), label=answer.text[:200])]
        if _YES.search(answer.text):
            return Judgement(
                status=S.CONFORME, justification=f"Réponse : « {answer.text[:200]} »", evidence=evidence
            )
        if _NO.search(answer.text):
            return Judgement(
                status=S.NON_CONFORME, justification=f"Réponse : « {answer.text[:200]} »", evidence=evidence
            )
        return Judgement(
            status=S.A_VERIFIER,
            justification=f"Réponse à préciser : « {answer.text[:200]} »",
            evidence=evidence,
        )

    def _certification(self, req: TenderRequirement) -> Judgement:
        cited = [c for c in self.company.certifications if _mentions(c.name, req.description)]
        valid = [c for c in cited if c.is_valid]
        if valid:
            c = valid[0]
            return Judgement(
                status=S.CONFORME,
                justification=f"Certification {c.name} détenue"
                + (f", valide jusqu'au {c.expires_at:%d/%m/%Y}" if c.expires_at else ""),
                evidence=[Evidence(kind="certification", id=str(c.id), label=c.name)],
            )
        if cited:
            c = cited[0]
            return Judgement(
                status=S.NON_CONFORME,
                justification=f"Certification {c.name} expirée le {c.expires_at:%d/%m/%Y}",
                evidence=[Evidence(kind="certification", id=str(c.id), label=f"{c.name} (expirée)")],
            )
        return Judgement(
            status=S.INFO_MANQUANTE, justification="Aucune certification correspondante dans le profil"
        )

    def _technique(self, req: TenderRequirement) -> Judgement:
        demanded = [
            t
            for t in ((self.tender.extra or {}).get("technologies", []) if self.tender else [])
            if _mentions(t, req.description)
        ]
        owned_tech = [t for t in self.company.technologies if _mentions(t.name, req.description)]
        owned_skills = [s for s in self.company.skills if _mentions(s.name, req.description)]
        evidence = [Evidence(kind="technology", id=str(t.id), label=t.name) for t in owned_tech]
        evidence += [Evidence(kind="skill", id=str(s.id), label=s.name) for s in owned_skills]
        if demanded:
            missing = [
                d
                for d in demanded
                if not any(_mentions(d, t.name) or _mentions(t.name, d) for t in self.company.technologies)
            ]
            if not missing:
                return Judgement(
                    status=S.CONFORME,
                    justification=f"Technologies maîtrisées : {', '.join(demanded)}",
                    evidence=evidence,
                )
            if len(missing) < len(demanded):
                return Judgement(
                    status=S.A_VERIFIER, justification=f"Manque : {', '.join(missing)}", evidence=evidence
                )
            return Judgement(
                status=S.INFO_MANQUANTE, justification=f"Non trouvé dans le profil : {', '.join(missing)}"
            )
        if evidence:
            return Judgement(
                status=S.CONFORME,
                justification="Compétence / technologie présente au profil : "
                + ", ".join(e.label for e in evidence),
                evidence=evidence,
            )
        return Judgement(
            status=S.INFO_MANQUANTE, justification="Aucune technologie ou compétence du profil ne correspond"
        )

    def _experience(self, req: TenderRequirement) -> Judgement:
        numbers = _numbers(req.description)
        if not numbers:
            return Judgement(
                status=S.INFO_MANQUANTE,
                justification="Aucun critère chiffré (années, projets, références) comparable au profil",
            )
        needed, unit = numbers[0]
        if unit.startswith("an"):
            experts = sorted(
                (e for e in self.company.experts if e.years_experience),
                key=lambda e: -(e.years_experience or 0),
            )
            if not experts:
                return Judgement(
                    status=S.INFO_MANQUANTE, justification="Ancienneté des experts non renseignée"
                )
            best = experts[0]
            years = best.years_experience or 0
            evidence = [Evidence(kind="expert", id=str(best.id), label=f"{best.full_name} — {years} ans")]
            if years >= needed:
                return Judgement(
                    status=S.CONFORME,
                    justification=f"{needed} ans requis ; expert le plus expérimenté : {years} ans",
                    evidence=evidence,
                )
            return Judgement(
                status=S.NON_CONFORME,
                justification=f"{needed} ans requis ; expert le plus expérimenté : {years} ans",
                evidence=evidence,
            )
        sector = self.tender.sector if self.tender else None
        projects = [
            p for p in self.company.projects if not sector or (p.sector and _mentions(p.sector, sector))
        ]
        evidence = [Evidence(kind="project", id=str(p.id), label=_label(p.title, p.client)) for p in projects]
        scope = f" dans le secteur {sector}" if sector else ""
        count = len(projects)
        text = f"{needed} requis{scope} ; {count} projet{'s' if count > 1 else ''} au profil"
        if count >= needed:
            return Judgement(status=S.CONFORME, justification=text, evidence=evidence)
        return Judgement(status=S.NON_CONFORME, justification=text, evidence=evidence)

    def _team(self, req: TenderRequirement) -> Judgement:
        experts = [e for e in self.company.experts if e.role and _mentions(e.role, req.description)]
        if experts:
            e = experts[0]
            return Judgement(
                status=S.CONFORME,
                justification=f"Profil disponible : {e.full_name} ({e.role})",
                evidence=[
                    Evidence(kind="expert", id=str(x.id), label=_label(x.full_name, x.role)) for x in experts
                ],
            )
        return Judgement(
            status=S.INFO_MANQUANTE, justification="Aucun expert du profil ne correspond au rôle demandé"
        )

    def _document(self, req: TenderRequirement) -> Judgement:
        categories = DOCUMENT_CATEGORIES[RequirementCategory(req.category)]
        docs = self.db.scalars(
            select(CompanyDocument).where(
                CompanyDocument.company_id == self.company.id, CompanyDocument.category.in_(categories)
            )
        ).all()
        words = [
            w for w in norm_text(req.description).split() if len(w) >= MIN_WORD and w not in GENERIC_WORDS
        ]
        # Le document qui partage le plus de mots avec l'exigence l'emporte (« attestation CNSS » ne
        # doit pas être satisfaite par « attestation fiscale »).
        scored = [(sum(w in norm_text(f"{d.name} {' '.join(d.tags or [])}") for w in words), d) for d in docs]
        best = max((s for s, _ in scored), default=0)
        matching = [d for s, d in scored if s and s == best]
        usable = [d for d in matching if d.is_usable]
        if usable:
            d = usable[0]
            return Judgement(
                status=S.CONFORME,
                justification=f"Document disponible : {d.name}"
                + (f" (valide jusqu'au {d.expires_at:%d/%m/%Y})" if d.expires_at else ""),
                evidence=[Evidence(kind="document", id=str(d.id), label=d.name)],
            )
        if matching:
            d = matching[0]
            when = f" le {d.expires_at:%d/%m/%Y}" if d.expires_at else ""
            return Judgement(
                status=S.NON_CONFORME,
                justification=f"Document {d.name} présent mais expiré{when} ou inutilisable",
                evidence=[Evidence(kind="document", id=str(d.id), label=f"{d.name} (expiré)")],
            )
        return Judgement(
            status=S.INFO_MANQUANTE, justification="Aucun document correspondant dans la base documentaire"
        )

    # --- évaluation d'une fiche ----------------------------------------------------------------

    @staticmethod
    def apply(req: TenderRequirement, judgement: Judgement) -> None:
        req.status = judgement.status
        req.justification = judgement.justification
        req.evidence = [e.model_dump() for e in judgement.evidence]

    def refresh(self, tender: Tender) -> EligibilitySummary:
        """Résumé recalculé dans `tender.extra["eligibility"]` et score relancé (le sous-score
        « éligibilité » suit le ratio) — après `evaluate` comme après une réponse à une question."""
        summary = self.summarize(tender)
        extra = dict(tender.extra or {})
        extra["eligibility"] = summary.model_dump()
        tender.extra = extra
        self.db.flush()
        ScoreService(self.db, self.llm).score_tender(tender)
        return summary

    def evaluate(
        self, tender: Tender, answers_by_requirement: Mapping[Any, Sequence[AnswerLike]] | None = None
    ) -> EligibilitySummary:
        self.tender = tender
        answers = answers_by_requirement or {}
        for req in tender.requirements:
            if req.manual_status:
                continue  # la main de l'utilisateur prime sur les règles
            self.apply(req, self.judge(req, answers.get(req.id, [])))
        summary = self.refresh(tender)
        for req in tender.requirements:
            if req.is_mandatory and req.status in (S.NON_CONFORME, S.INFO_MANQUANTE):
                self.on_mandatory_unmet(tender, req)  # RB-003
        record_audit(
            self.db,
            action="tender.eligibility_evaluated",
            entity_kind="tender",
            entity_id=tender.id,
            payload=summary.model_dump(),
        )
        self.db.flush()
        log.info(
            "eligibility.done",
            tender_id=str(tender.id),
            ratio=summary.ratio,
            unmet=len(summary.mandatory_unmet),
        )
        return summary

    @staticmethod
    def summarize(tender: Tender) -> EligibilitySummary:
        reqs = list(tender.requirements)
        by_status = {s.value: sum(1 for r in reqs if r.status == s) for s in RequirementStatus}
        total = len(reqs)
        ratio = (
            1.0 if not total else round((by_status["CONFORME"] + 0.5 * by_status["A_VERIFIER"]) / total, 3)
        )
        unmet = [r.code for r in reqs if r.is_mandatory and r.status in (S.NON_CONFORME, S.INFO_MANQUANTE)]
        return EligibilitySummary(
            total=total,
            by_status=by_status,
            mandatory_unmet=unmet,
            ratio=ratio,
            evaluated_at=datetime.now(tz=UTC).isoformat(timespec="seconds"),
        )

    @staticmethod
    def _log_unmet(tender: Tender, req: TenderRequirement) -> None:
        log.warning(
            "eligibility.mandatory_unmet", tender_id=str(tender.id), code=req.code, status=str(req.status)
        )
