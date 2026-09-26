"""Base de connaissances (Phase 8) : un document d'entreprise déposé ou versionné est indexé
automatiquement (job `index_document`, morceaux portant catégorie, nom, expiration et version) ;
`company_facts(db)` rassemble les faits vérifiables du profil (source unique) et
`refresh_company_summary` en tire le résumé IA, enfilé par les écritures sur le profil."""

from datetime import date, timedelta

from sqlalchemy import select

from app.ai.llm import FakeLLM
from app.models import DocumentChunk, Expert, JobStatus, Skill
from app.models.document import DocumentCategory, DocumentStatus
from app.services.company import CompanyService
from app.services.company_facts import CompanyFacts, company_facts
from app.services.documents import DocumentService
from app.services.jobs import JobService

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _upload(db, storage, fixtures_dir, **over):
    return DocumentService(db, storage).upload(
        filename=over.pop("filename", "presentation.docx"),
        data=over.pop("data", (fixtures_dir / "sample.docx").read_bytes()),
        content_type=over.pop("content_type", DOCX),
        category=over.pop("category", DocumentCategory.presentation),
        **over,
    )


def test_upload_enqueues_indexing_and_chunks_carry_document_metadata(
    db, storage, run_jobs_inline, fake_embeddings, company, fixtures_dir
):
    expires = date.today() + timedelta(days=200)
    doc = _upload(db, storage, fixtures_dir, name="Plaquette InnoSustain", expires_at=expires)

    jobs = JobService.list(db, type="index_document")
    assert len(jobs) == 1 and jobs[0].status == JobStatus.done, jobs[0].error if jobs else "aucun job"
    assert jobs[0].params == {"kind": "company_document", "document_id": str(doc.id)}
    chunks = list(db.scalars(select(DocumentChunk).where(DocumentChunk.company_document_id == doc.id)))
    assert chunks and chunks[0].owner_kind == "company_document"
    assert chunks[0].meta == {
        "category": "presentation",
        "name": "Plaquette InnoSustain",
        "expires_at": expires.isoformat(),
        "version": 1,
    }


def test_new_version_reindexes_the_document(
    db, storage, run_jobs_inline, fake_embeddings, company, fixtures_dir
):
    doc = _upload(db, storage, fixtures_dir)
    DocumentService(db, storage).new_version(
        doc,
        filename="presentation.txt",
        data=b"InnoSustain, cabinet de conseil en transition energetique.",
        content_type="text/plain",
        changelog="mise a jour 2026",
    )

    assert len(JobService.list(db, type="index_document")) == 2
    chunks = list(db.scalars(select(DocumentChunk).where(DocumentChunk.company_document_id == doc.id)))
    assert len(chunks) == 1 and "transition energetique" in chunks[0].content
    assert chunks[0].meta["version"] == 2


def test_company_facts_only_lists_verifiable_and_usable_elements(db, storage, company, fixtures_dir):
    today = date.today()
    company.skills.append(Skill(name="Audit énergétique"))
    company.experts.append(Expert(full_name="Nadia F.", role="Chef de projet énergie", years_experience=8))
    db.flush()
    usable = _upload(
        db, storage, fixtures_dir, name="Attestation fiscale", expires_at=today + timedelta(days=30)
    )
    expired = _upload(
        db,
        storage,
        fixtures_dir,
        filename="note.txt",
        data=b"vieux document",
        content_type="text/plain",
        category=DocumentCategory.attestation,
        name="Attestation CNSS",
        expires_at=today - timedelta(days=5),
        status=DocumentStatus.expired,
    )

    facts = company_facts(db)

    assert isinstance(facts, CompanyFacts)
    assert facts.trade_name == "InnoSustain" and "Énergie" in facts.sectors
    assert [s.name for s in facts.skills] == ["Audit énergétique"]
    assert [t.name for t in facts.technologies] == ["PostgreSQL", "Power BI", "Python"]
    # RB-007 / RB-005 : seules les certifications valides et les documents utilisables sont des faits
    assert [c.name for c in facts.certifications] == ["ISO 14001"]
    assert [e.full_name for e in facts.experts] == ["Nadia F."] and facts.experts[0].years_experience == 8
    assert [p.title for p in facts.projects] == ["Audit énergétique", "Plan climat territorial"]
    names = [d.name for d in facts.documents]
    assert usable.name in names and expired.name not in names

    text = facts.as_text()
    assert "InnoSustain" in text and "ISO 14001" in text and "ISO 9001" not in text
    assert "Attestation CNSS" not in text and usable.name in text
    assert "Références clients : (aucun)" in text  # le scoring a besoin de voir ce qui manque
    # Pour une présentation : ni la base documentaire, ni les rubriques vides (Task 8.1, constaté en réel)
    presentation = facts.as_text(include_documents=False, include_empty=False)
    assert usable.name not in presentation and "(aucun)" not in presentation


def test_refresh_company_summary_writes_the_ai_summary_from_the_facts(
    db, run_jobs_inline, monkeypatch, company
):
    from app.core import deps

    llm = FakeLLM(text_responses=["InnoSustain accompagne les collectivités marocaines…"])
    monkeypatch.setattr(deps, "_llm_override", llm)

    job = JobService.enqueue(db, "refresh_company_summary", entity_kind="company", entity_id=company.id)
    db.refresh(job)

    assert job.status == JobStatus.done, job.error
    profile = CompanyService.get_or_create(db).profile
    assert profile.ai_summary == "InnoSustain accompagne les collectivités marocaines…"
    assert profile.ai_summary_updated_at is not None
    assert job.result == {"words": 5}
    prompt = llm.calls[0]["user"]
    assert "ISO 14001" in prompt and "Python" in prompt  # le modèle ne reçoit que des faits du profil
    assert "ISO 9001" not in prompt and "Documents disponibles" not in prompt


def test_refresh_company_summary_keeps_the_previous_summary_when_the_model_fails(
    db, run_jobs_inline, monkeypatch, company
):
    from app.core import deps

    company.profile.positioning = "Cabinet de conseil"
    company.profile.ai_summary = "Résumé précédent"
    db.flush()
    monkeypatch.setattr(deps, "_llm_override", FakeLLM())  # aucune réponse scriptée ⇒ erreur

    job = JobService.enqueue(db, "refresh_company_summary", entity_kind="company", entity_id=company.id)
    db.refresh(job)

    assert job.status == JobStatus.failed and "FakeLLM" in (job.error or "")
    assert CompanyService.get_or_create(db).profile.ai_summary == "Résumé précédent"


def test_profile_writes_enqueue_a_single_summary_refresh(auth_client, db, fake_llm, company):
    r = auth_client.put("/api/v1/company/profile", json={"positioning": "Conseil en énergie"})
    assert r.status_code == 200, r.text
    r = auth_client.post("/api/v1/company/skills", json={"name": "ACV", "category": "expertise"})
    assert r.status_code == 201, r.text

    jobs = JobService.list(db, type="refresh_company_summary")
    assert len(jobs) == 1  # un seul job en attente : les écritures suivantes ne l'empilent pas
    assert jobs[0].entity_kind == "company"


def test_deleting_a_skill_also_asks_for_a_refresh(auth_client, db, fake_llm, company):
    skill = {"name": "ACV", "category": "expertise"}
    created = auth_client.post("/api/v1/company/skills", json=skill).json()
    JobService.list(db, type="refresh_company_summary")[0].status = JobStatus.done  # le premier est traité
    db.flush()

    assert auth_client.delete(f"/api/v1/company/skills/{created['id']}").status_code == 204

    # `created_at` vaut now() — identique dans une même transaction : compter plutôt qu'ordonner
    jobs = JobService.list(db, type="refresh_company_summary")
    assert len(jobs) == 2 and sum(j.status == JobStatus.pending for j in jobs) == 1
