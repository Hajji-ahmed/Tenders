"""Contexte de génération d'une section (Phase 9) : tout ce que le modèle recevra — et rien d'autre.

Le plan de la section commande (`requires`) : une section qui ne demande pas les exigences ne les
voit pas. Deux filtres tiennent du principe plutôt que de la technique : les faits de l'entreprise
sont ceux de `CompanyFacts` (certifications valides, documents utilisables seulement) et les
extraits viennent de `KnowledgeBase`, qui écarte déjà ce qui n'est pas opposable (RB-007). Ce qui
n'entre pas ici ne pourra pas être écrit."""

from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import SectionSource, Tender
from app.services.company_facts import CompanyFacts, company_facts
from app.services.knowledge import KBHit, KnowledgeBase

KB_HITS = 6
KB_CONTEXT_CHARS = 6_000


class GenerationContext(BaseModel):
    """Ce qu'une section a le droit de lire, prêt pour le prompt."""

    company: CompanyFacts
    tender: dict[str, Any] = Field(default_factory=dict)
    requirements: list[dict] = Field(default_factory=list)
    answers: list[dict] = Field(default_factory=list)
    kb_context: str = ""
    kb_hits: list[KBHit] = Field(default_factory=list)
    template_instructions: str = ""
    section_title: str = ""
    max_words: int = 400
    # Document répétable (CV, fiche de référence) : l'expert ou le projet dont il parle.
    subject: dict[str, Any] | None = None


def tender_facts(tender: Tender) -> dict[str, Any]:
    """La fiche telle qu'elle a été lue : identité, puis l'analyse du dossier si elle existe."""
    facts: dict[str, Any] = {
        "title": tender.title,
        "organization": tender.organization,
        "reference": tender.reference,
        "sector": tender.sector,
        "deadline_at": tender.deadline_at.date().isoformat() if tender.deadline_at else None,
    }
    analysis = tender.analysis
    if analysis is not None:
        facts |= {
            "object": analysis.object,
            "budget": analysis.budget,
            "duration": analysis.duration,
            "location": analysis.location,
            "key_dates": list(analysis.key_dates or []),
            "deliverables": list(analysis.deliverables or []),
            "requested_documents": list(analysis.requested_documents or []),
            "eligibility_conditions": list(analysis.eligibility_conditions or []),
            "summary": analysis.summary,
        }
        facts["organization"] = facts["organization"] or analysis.organization
        facts["reference"] = facts["reference"] or analysis.reference
    if tender.criteria:
        facts["criteria"] = [
            {"name": c.name, "weight": float(c.weight) if c.weight is not None else None}
            for c in tender.criteria
        ]
    return facts


def requirement_facts(tender: Tender) -> list[dict]:
    return [
        {
            "code": r.code,
            "category": str(r.category),
            "description": r.description,
            "is_mandatory": r.is_mandatory,
            "status": str(r.status),
            "justification": r.justification,
        }
        for r in tender.requirements
    ]


def answer_facts(tender: Tender) -> list[dict]:
    """Les réponses de l'utilisateur : ce qu'il a affirmé fait foi et peut être écrit."""
    return [
        {"code": q.requirement.code, "question": q.text, "answer": q.answer.answer}
        for q in tender.questions
        if q.answer is not None
    ]


def build_context(
    db: Session,
    kb: KnowledgeBase | None,
    tender: Tender,
    section_spec: dict,
    *,
    repeat_item: dict | None = None,
) -> GenerationContext:
    """Rassemble les sources déclarées par la section. `repeat_item` : le sujet d'un document
    répétable (un expert pour un CV, un projet pour une fiche de référence)."""
    requires = set(section_spec.get("requires") or [])
    title = section_spec.get("title", "")
    context = GenerationContext(
        company=CompanyFacts(legal_name=""),
        template_instructions=section_spec.get("instructions", ""),
        section_title=title,
        max_words=int(section_spec.get("max_words") or 400),
        subject=repeat_item,
    )
    if SectionSource.company_facts in requires:
        context.company = company_facts(db)
    if SectionSource.tender_analysis in requires:
        context.tender = tender_facts(tender)
    if SectionSource.requirements in requires:
        context.requirements = requirement_facts(tender)
    if SectionSource.answers in requires:
        context.answers = answer_facts(tender)
    if SectionSource.kb in requires and kb is not None:
        query = " ".join(x for x in (title, tender_facts(tender).get("object"), tender.title) if x)
        context.kb_hits = kb.search(query, owner_kind="company_document", k=KB_HITS)
        context.kb_context = kb.build_context(context.kb_hits, max_chars=KB_CONTEXT_CHARS)
    return context
