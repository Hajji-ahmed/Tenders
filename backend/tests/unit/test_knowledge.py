"""Base de connaissances (Task 8.2) : recherche sémantique sur les morceaux indexés, filtrée par
nature de propriétaire, par appel d'offres, par catégorie de document et — RB-007 — limitée aux
documents utilisables ; contexte RAG numéroté `[S1] (fichier p. n)` borné en caractères."""

from datetime import date, timedelta

import pytest

from app.models import DocumentChunk, Tender, TenderDocument
from app.models.document import CompanyDocument, DocumentCategory, DocumentStatus
from app.services.knowledge import KBHit, KnowledgeBase

TEXTS = {
    "iso": "Certificat ISO 27001 délivré à InnoSustain, valable jusqu'au 31 décembre 2027.",
    "cnss": "Attestation CNSS de InnoSustain, situation régulière au 3 septembre 2026.",
    "rc": "Le candidat fournit une attestation fiscale de moins d'un an sous peine de rejet.",
    "plaquette": "InnoSustain conduit des audits énergétiques et la rénovation de l'éclairage public.",
}


def _company_doc(db, company, name, category, **over) -> CompanyDocument:
    doc = CompanyDocument(
        company_id=company.id,
        name=name,
        category=category,
        storage_key=f"company/{name}",
        mime_type="application/pdf",
        size_bytes=1,
        sha256=f"{abs(hash(name)):064d}"[:64],
        **over,
    )
    db.add(doc)
    db.flush()
    return doc


def _chunk(
    db, embeddings, *, text, owner_kind, owner_id, page=1, tender_id=None, company_document_id=None, meta=None
):
    chunk = DocumentChunk(
        owner_kind=owner_kind,
        owner_id=owner_id,
        tender_id=tender_id,
        company_document_id=company_document_id,
        chunk_index=0,
        page=page,
        content=text,
        embedding=embeddings.embed([text])[0],
        token_count=len(text) // 4,
        meta=meta or {},
    )
    db.add(chunk)
    db.flush()
    return chunk


@pytest.fixture
def corpus(db, company, fake_embeddings):
    """Trois documents d'entreprise (un valide, un expiré, un archivé) et une pièce d'appel d'offres."""
    today = date.today()
    iso = _company_doc(
        db,
        company,
        "ISO-27001.pdf",
        DocumentCategory.certification,
        expires_at=today + timedelta(days=400),
    )
    cnss = _company_doc(
        db,
        company,
        "CNSS.pdf",
        DocumentCategory.attestation,
        status=DocumentStatus.expired,
        expires_at=today - timedelta(days=3),
    )
    plaquette = _company_doc(db, company, "Plaquette.pdf", DocumentCategory.presentation)
    tender = Tender(title="Éclairage public de Salé")
    db.add(tender)
    db.flush()
    piece = TenderDocument(
        tender_id=tender.id, name="RC-27-2026.pdf", storage_key="t/rc.pdf", mime_type="application/pdf"
    )
    db.add(piece)
    db.flush()

    _chunk(
        db,
        fake_embeddings,
        text=TEXTS["iso"],
        owner_kind="company_document",
        owner_id=iso.id,
        company_document_id=iso.id,
        page=2,
        meta={"category": "certification", "name": iso.name, "expires_at": None, "version": 1},
    )
    _chunk(
        db,
        fake_embeddings,
        text=TEXTS["cnss"],
        owner_kind="company_document",
        owner_id=cnss.id,
        company_document_id=cnss.id,
    )
    _chunk(
        db,
        fake_embeddings,
        text=TEXTS["plaquette"],
        owner_kind="company_document",
        owner_id=plaquette.id,
        company_document_id=plaquette.id,
    )
    _chunk(
        db,
        fake_embeddings,
        text=TEXTS["rc"],
        owner_kind="tender_document",
        owner_id=piece.id,
        tender_id=tender.id,
        page=3,
    )
    return {"iso": iso, "cnss": cnss, "plaquette": plaquette, "tender": tender, "piece": piece}


@pytest.fixture
def kb(db, fake_embeddings) -> KnowledgeBase:
    return KnowledgeBase(db, fake_embeddings)


def test_search_ranks_the_matching_chunk_first_with_its_source(kb, corpus):
    hits = kb.search(TEXTS["iso"], usable_only=False)

    assert hits and isinstance(hits[0], KBHit)
    top = hits[0]
    assert top.content == TEXTS["iso"] and top.document_name == "ISO-27001.pdf" and top.page == 2
    assert top.owner_kind == "company_document" and top.owner_id == corpus["iso"].id
    assert top.score > 0.99 and hits[-1].score < top.score  # score = 1 - distance cosinus
    assert top.metadata["category"] == "certification"


def test_unusable_documents_are_excluded_by_default(kb, corpus):
    """RB-007 : un document expiré (ou brouillon, ou archivé) ne doit jamais être cité comme preuve."""
    names = [h.document_name for h in kb.search(TEXTS["cnss"])]
    assert "CNSS.pdf" not in names

    relaxed = kb.search(TEXTS["cnss"], usable_only=False)
    assert relaxed[0].document_name == "CNSS.pdf"

    corpus["plaquette"].status = DocumentStatus.archived
    assert "Plaquette.pdf" not in [h.document_name for h in kb.search(TEXTS["plaquette"])]


def test_tender_pieces_are_searchable_and_never_filtered_by_rb007(kb, corpus):
    hits = kb.search(TEXTS["rc"])
    top = hits[0]
    assert top.owner_kind == "tender_document" and top.document_name == "RC-27-2026.pdf" and top.page == 3

    only_tender = kb.search(TEXTS["iso"], tender_id=corpus["tender"].id)
    assert [h.document_name for h in only_tender] == ["RC-27-2026.pdf"]


def test_filters_by_owner_kind_and_category(kb, corpus):
    company_only = kb.search(TEXTS["rc"], owner_kind="company_document")
    assert company_only and all(h.owner_kind == "company_document" for h in company_only)

    certifications = kb.search(TEXTS["plaquette"], categories=["certification"])
    assert [h.document_name for h in certifications] == ["ISO-27001.pdf"]

    several = kb.search(TEXTS["plaquette"], categories=["certification", "presentation"])
    assert sorted(h.document_name for h in several) == ["ISO-27001.pdf", "Plaquette.pdf"]


def test_k_limits_the_number_of_hits(kb, corpus):
    assert len(kb.search(TEXTS["iso"], usable_only=False, k=2)) == 2
    assert kb.search(TEXTS["iso"], k=0) == []


def test_build_context_numbers_sources_and_respects_the_limit(kb, corpus):
    hits = kb.search(TEXTS["iso"], usable_only=False, k=4)

    context = kb.build_context(hits)
    assert context.startswith("[S1] (ISO-27001.pdf p. 2)")
    assert "[S2] (" in context and context.count("[S") == 4

    short = kb.build_context(hits, max_chars=160)
    assert len(short) <= 160 and short.count("[S") < 4 and short.startswith("[S1]")
    assert kb.build_context([]) == ""


def test_search_on_an_empty_base_returns_nothing(db, fake_embeddings):
    assert KnowledgeBase(db, fake_embeddings).search("n'importe quoi") == []
