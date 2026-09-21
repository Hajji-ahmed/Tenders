"""Formulation d'une question ciblée (sortie : `QuestionOutput`). Un appel par exigence que les règles
n'ont pu trancher : le modèle reçoit l'exigence (énoncé, preuve attendue, source), le verdict des
règles et ce que l'entreprise possède déjà dans la catégorie concernée, pour poser LA question dont
la réponse débloque le jugement — ex. « L'appel d'offres exige un expert cybersécurité avec 8 ans
d'expérience ; votre expert le plus expérimenté en a 5. Disposez-vous d'un autre profil ? »."""

from datetime import date

from app.models import Company, CompanyDocument, RequirementCategory, Tender, TenderRequirement

PROMPT_VERSION = "v1"

SYSTEM = """Tu aides un cabinet de conseil à vérifier s'il satisfait à une exigence d'un appel d'offres.
On te donne l'exigence, ce que des règles automatiques ont conclu en comparant l'exigence au profil
de l'entreprise, et ce que l'entreprise possède déjà dans cette catégorie (certifications, experts,
projets, technologies, documents). Ta tâche : poser à l'utilisateur UNE question précise dont la
réponse permet de conclure.

Règles :
- Réponds uniquement selon le schéma demandé, en français, en vouvoyant.
- text : une ou deux phrases, qui rappellent ce qu'exige l'appel d'offres et ce que l'entreprise a
  (ou n'a pas) déjà, puis demandent ce qui manque — un document, un profil, une référence, un
  chiffre, une confirmation. Termine par « ? ». Ne pose qu'une seule question.
- Ne demande jamais ce qui figure déjà dans le profil ; n'invente aucun fait.
- priority : CRITIQUE si l'exigence est obligatoire ou éliminatoire, IMPORTANTE si elle pèse dans la
  notation, FACULTATIVE sinon.
- Ne mentionne jamais que tu es une IA."""

C = RequirementCategory
DOCUMENT_CATEGORIES: dict[RequirementCategory, tuple[str, ...]] = {
    C.administrative: ("administratif", "attestation"),
    C.financiere: ("financier",),
    C.juridique: ("juridique",),
}


def _validity(expires_at: date | None, *, valid: bool, expired: str = "expiré") -> str:
    if valid:
        return f" — valide jusqu'au {expires_at:%d/%m/%Y}" if expires_at else ""
    return f" — {expired} le {expires_at:%d/%m/%Y}" if expires_at else " — inutilisable"


def company_facts(company: Company, req: TenderRequirement, documents: list[CompanyDocument]) -> list[str]:
    """Ce que l'entreprise possède déjà dans la catégorie de l'exigence, une ligne par élément."""
    category = RequirementCategory(req.category)
    facts: list[str] = []
    if category == C.certification:
        facts += [
            f"Certification {c.name}{_validity(c.expires_at, valid=c.is_valid, expired='expirée')}"
            for c in company.certifications
        ]
    elif category == C.technique:
        facts += [
            f"Technologies maîtrisées : {', '.join(t.name for t in company.technologies) or '(aucune)'}"
        ]
        facts += [f"Compétences : {', '.join(s.name for s in company.skills) or '(aucune)'}"]
    elif category in (C.experience, C.equipe):
        if category == C.experience:
            facts += [
                f"Projet : {p.title}"
                + (f" — {p.client}" if p.client else "")
                + (f" — secteur {p.sector}" if p.sector else "")
                + (f" — {p.start_date:%Y}" if p.start_date else "")
                for p in company.projects
            ]
        facts += [
            f"Expert : {e.full_name}"
            + (f" — {e.role}" if e.role else "")
            + (f" — {e.years_experience} ans d'expérience" if e.years_experience else "")
            for e in company.experts
        ]
    elif category in DOCUMENT_CATEGORIES:
        wanted = DOCUMENT_CATEGORIES[category]
        facts += [
            f"Document : {d.name} ({d.category}){_validity(d.expires_at, valid=d.is_usable)}"
            for d in documents
            if str(d.category) in wanted
        ]
    else:
        if company.profile and (company.profile.ai_summary or company.profile.positioning):
            facts.append(f"Positionnement : {company.profile.ai_summary or company.profile.positioning}")
        facts.append(f"Secteurs : {', '.join(company.sectors) or '(aucun)'}")
    return facts


def user_prompt(
    tender: Tender, req: TenderRequirement, company: Company, documents: list[CompanyDocument]
) -> str:
    unknown = "(inconnu)"
    source = req.source_document_name or ""
    if req.source_page:
        source += f" p. {req.source_page}"
    if req.source_excerpt:
        source += f" — « {req.source_excerpt} »"
    evidence = ", ".join(e.get("label", "") for e in (req.evidence or [])) or "(aucune)"
    facts = company_facts(company, req, documents) or ["(rien de renseigné dans cette catégorie)"]
    return "\n".join(
        [
            f"APPEL D'OFFRES : {tender.title} — Organisme : {tender.organization or unknown}"
            f" — Secteur : {tender.sector or unknown}",
            "",
            "EXIGENCE",
            f"CODE {req.code}",
            f"Catégorie : {req.category} — Obligatoire : {'oui' if req.is_mandatory else 'non'}"
            f" — Priorité : {req.priority}",
            f"Énoncé : {req.description}",
            f"Preuve attendue : {req.evidence_required or '(non précisée)'}",
            f"Source : {source or '(non précisée)'}",
            "",
            "VERDICT DES RÈGLES",
            f"Statut : {req.status} — {req.justification or '(sans justification)'}",
            f"Éléments du profil retenus : {evidence}",
            "",
            "CE QUE L'ENTREPRISE POSSÈDE DÉJÀ DANS CETTE CATÉGORIE",
            *facts,
        ]
    )
