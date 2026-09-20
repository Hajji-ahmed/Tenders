"""Analyse IA structurée d'un dossier : corpus des pièces extraites (marqueurs de page, priorité aux
pièces réglementaires, plafond), persistance de l'analyse et des critères, enrichissement de la
fiche (résumé, échéance, documents demandés), audit."""

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select

from app.ai.llm import FakeLLM
from app.ai.outputs import CriterionOut, DatedItem, RequestedDocument, TenderAnalysisOutput
from app.core.errors import AppError
from app.models import AuditLog, DownloadStatus, ExtractionStatus, Tender, TenderCriterion, TenderDocument
from app.services.analysis import MAX_CORPUS_CHARS, AnalysisService, build_corpus

PDF = "application/pdf"


def _doc(name: str, pages: list[str], status: ExtractionStatus = ExtractionStatus.done) -> TenderDocument:
    return TenderDocument(
        name=name,
        mime_type=PDF,
        download_status=DownloadStatus.done,
        extraction_status=status,
        extracted_text="\f".join(pages) if status == ExtractionStatus.done else None,
        page_count=len(pages),
    )


@pytest.fixture
def tender(db) -> Tender:
    t = Tender(title="Rénovation de l'éclairage public de Salé", organization="Commune de Salé")
    t.documents.append(_doc("annexe-technique.pdf", ["Annexe : plans et schémas."]))
    t.documents.append(
        _doc(
            "RC.pdf",
            [
                "Règlement de consultation. Article 1 : objet.",
                "Article 5 : critères. Prix 40 %, technique 60 %.",
            ],
        )
    )
    t.documents.append(_doc("CCTP.pdf", ["Cahier des clauses techniques : 4 500 luminaires LED."]))
    t.documents.append(_doc("scan.pdf", [], status=ExtractionStatus.failed))
    t.documents.append(_doc("en-attente.pdf", [], status=ExtractionStatus.pending))
    db.add(t)
    db.flush()
    return t


def _output() -> TenderAnalysisOutput:
    return TenderAnalysisOutput(
        object="Rénovation de l'éclairage public : 4 500 luminaires LED, télégestion, maintenance 5 ans",
        organization="Commune de Salé",
        reference="27/2026",
        budget="18 000 000 MAD TTC",
        duration="24 mois + maintenance 5 ans",
        location="Salé, Maroc",
        key_dates=[
            DatedItem(label="Date limite de remise des offres", date=date(2026, 11, 20), source_page=1),
            DatedItem(label="Visite de site", date=date(2026, 10, 15), source_page=2),
        ],
        deliverables=["Étude d'exécution", "Fourniture et pose des luminaires", "Système de télégestion"],
        evaluation_criteria=[
            CriterionOut(name="Prix", weight=40, description="Offre financière", source_page=2),
            CriterionOut(
                name="Valeur technique", weight=60, description="Méthodologie, moyens", source_page=2
            ),
            CriterionOut(name="Délai", weight=None, description=None, source_page=None),
        ],
        requested_documents=[
            RequestedDocument(name="Attestation fiscale", mandatory=True, source_page=1),
            RequestedDocument(name="Références similaires", mandatory=False, source_page=2),
        ],
        eligibility_conditions=["Qualification éclairage public", "CA > 10 MMAD sur 3 ans"],
        summary="Marché de rénovation LED avec télégestion ; offre avant le 20/11/2026.",
    )


def test_corpus_marks_pages_and_puts_regulatory_documents_first(tender):
    corpus = build_corpus(tender.documents)
    assert "=== RC.pdf — page 1 ===\nRèglement de consultation" in corpus
    assert "=== RC.pdf — page 2 ===\nArticle 5" in corpus
    assert "=== CCTP.pdf — page 1 ===" in corpus and "=== annexe-technique.pdf — page 1 ===" in corpus
    assert corpus.index("RC.pdf") < corpus.index("CCTP.pdf") < corpus.index("annexe-technique.pdf")
    assert "scan.pdf" not in corpus and "en-attente.pdf" not in corpus


def test_corpus_is_capped_but_keeps_priority_documents_whole():
    docs = [_doc("volumineux.pdf", ["x" * 200_000]), _doc("RC.pdf", ["Règlement complet."])]
    corpus = build_corpus(docs)
    assert len(corpus) <= MAX_CORPUS_CHARS + 200
    assert "=== RC.pdf — page 1 ===\nRèglement complet." in corpus
    assert "[… texte tronqué …]" in corpus


def test_analyze_persists_analysis_and_criteria_and_enriches_the_tender(db, tender):
    llm = FakeLLM([_output()])
    analysis = AnalysisService(db, llm).analyze(tender)

    assert analysis.tender_id == tender.id and tender.analysis is analysis
    assert analysis.object.startswith("Rénovation") and analysis.budget == "18 000 000 MAD TTC"
    assert analysis.key_dates[0] == {
        "label": "Date limite de remise des offres",
        "date": "2026-11-20",
        "source_page": 1,
    }
    assert analysis.requested_documents[0] == {
        "name": "Attestation fiscale",
        "mandatory": True,
        "source_page": 1,
    }
    assert analysis.eligibility_conditions == ["Qualification éclairage public", "CA > 10 MMAD sur 3 ans"]
    assert analysis.model and analysis.prompt_version == "v1" and analysis.analyzed_at is not None

    assert [(c.name, c.weight and float(c.weight), c.source_page) for c in tender.criteria] == [
        ("Prix", 40.0, 2),
        ("Valeur technique", 60.0, 2),
        ("Délai", None, None),
    ]
    assert tender.summary == "Marché de rénovation LED avec télégestion ; offre avant le 20/11/2026."
    assert tender.deadline_at == datetime(2026, 11, 20, 23, 59, 59, tzinfo=UTC)  # absente : trouvée
    assert tender.reference == "27/2026"  # trou comblé, jamais écrasé
    assert tender.extra["requested_documents"] == [
        {"name": "Attestation fiscale", "mandatory": True, "source_page": 1},
        {"name": "Références similaires", "mandatory": False, "source_page": 2},
    ]
    prompt = llm.calls[0]["user"]
    assert "=== RC.pdf — page 2 ===" in prompt and "Rénovation de l'éclairage public de Salé" in prompt
    assert llm.calls[0]["tier"] == "fast"
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "tender.analyzed"))
    assert audit is not None and audit.entity_id == tender.id and audit.payload["criteria"] == 3


def test_reanalyze_upserts_and_replaces_criteria_without_touching_a_known_deadline(db, tender):
    tender.deadline_at = datetime(2026, 12, 1, 23, 59, 59, tzinfo=UTC)
    service = AnalysisService(db, FakeLLM([_output(), _output()]))
    first = service.analyze(tender)
    before = {c.id for c in tender.criteria}
    second = service.analyze(tender)

    assert first.id == second.id
    assert len(tender.criteria) == 3 and {c.id for c in tender.criteria}.isdisjoint(before)
    assert db.scalar(select(func.count(TenderCriterion.id))) == 3
    assert tender.deadline_at == datetime(2026, 12, 1, 23, 59, 59, tzinfo=UTC)  # jamais écrasée


def test_analyze_without_usable_document_is_refused(db):
    empty = Tender(title="Sans pièces")
    empty.documents.append(_doc("scan.pdf", [], status=ExtractionStatus.failed))
    db.add(empty)
    db.flush()
    with pytest.raises(AppError, match="Aucun document exploitable") as info:
        AnalysisService(db, FakeLLM()).analyze(empty)
    assert info.value.code == "no_documents" and info.value.status_code == 422
