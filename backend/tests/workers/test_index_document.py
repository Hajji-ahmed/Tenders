"""Indexation d'un document (pièce d'AO ou document d'entreprise) : extraction, texte et pages
stockés, morceaux vectorisés en base, statut ; job `index_document` résilient."""

import pymupdf
from sqlalchemy import func, select

from app.models import DocumentChunk, DownloadStatus, ExtractionStatus, JobStatus, Tender, TenderDocument
from app.models.document import DocumentCategory
from app.services.documents import DocumentService
from app.services.indexing import IndexingService
from app.services.jobs import JobService


def _protected_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 90), "secret", fontsize=11)
    data = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw="x", user_pw="x")
    doc.close()
    return data


def _tender_doc(db, storage, name: str, data: bytes, mime: str) -> TenderDocument:
    tender = Tender(title="AO")
    db.add(tender)
    db.flush()
    key = f"tenders/{tender.id}/ab/{name}"
    storage.put(key, data, mime)
    doc = TenderDocument(
        tender_id=tender.id,
        name=name,
        storage_key=key,
        mime_type=mime,
        size_bytes=len(data),
        download_status=DownloadStatus.done,
    )
    db.add(doc)
    db.flush()
    return doc


def _chunks(db, owner_id) -> list[DocumentChunk]:
    return list(
        db.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.owner_id == owner_id)
            .order_by(DocumentChunk.chunk_index)
        )
    )


def test_index_tender_pdf_stores_text_pages_and_vectorized_chunks(db, storage, fake_embeddings, fixtures_dir):
    doc = _tender_doc(
        db, storage, "sample.pdf", (fixtures_dir / "sample.pdf").read_bytes(), "application/pdf"
    )

    count = IndexingService(db, storage, fake_embeddings).index("tender_document", doc)

    assert count >= 1 and doc.extraction_status == ExtractionStatus.done and doc.error is None
    assert doc.page_count == 1 and "Attestation fiscale InnoSustain 2026" in doc.extracted_text
    chunks = _chunks(db, doc.id)
    assert len(chunks) == count
    first = chunks[0]
    assert first.owner_kind == "tender_document" and first.tender_id == doc.tender_id
    assert first.company_document_id is None and first.page == 1 and first.chunk_index == 0
    assert "Attestation fiscale" in first.content and first.token_count and first.token_count > 0
    db.expire(first)
    assert len(list(first.embedding)) == 1536


def test_reindex_replaces_previous_chunks(db, storage, fake_embeddings, fixtures_dir):
    doc = _tender_doc(db, storage, "sample.txt", (fixtures_dir / "sample.txt").read_bytes(), "text/plain")
    service = IndexingService(db, storage, fake_embeddings)
    service.index("tender_document", doc)
    before = [c.id for c in _chunks(db, doc.id)]
    doc.extraction_status = ExtractionStatus.pending  # nouvelle version : on ré-extrait
    service.index("tender_document", doc)
    after = [c.id for c in _chunks(db, doc.id)]
    assert len(before) == len(after) == 1 and before != after
    assert db.scalar(select(func.count(DocumentChunk.id))) == 1


def test_zip_chunks_carry_the_inner_filename(db, storage, fake_embeddings, fixtures_dir):
    doc = _tender_doc(
        db, storage, "sample.zip", (fixtures_dir / "sample.zip").read_bytes(), "application/zip"
    )
    IndexingService(db, storage, fake_embeddings).index("tender_document", doc)
    chunks = _chunks(db, doc.id)
    assert sorted({c.meta["inner_filename"] for c in chunks}) == ["sample.pdf", "sample.txt"]
    assert doc.page_count == 2 and "Note interne InnoSustain" in doc.extracted_text


def test_company_document_is_indexed_with_its_own_key(db, storage, fake_embeddings, company, fixtures_dir):
    doc = DocumentService(db, storage).upload(
        filename="presentation.docx",
        data=(fixtures_dir / "sample.docx").read_bytes(),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        category=DocumentCategory.presentation,
    )
    count = IndexingService(db, storage, fake_embeddings).index("company_document", doc)
    chunks = _chunks(db, doc.id)
    assert count == len(chunks) >= 1 and doc.extraction_status == ExtractionStatus.done
    assert chunks[0].owner_kind == "company_document" and chunks[0].company_document_id == doc.id
    assert chunks[0].tender_id is None and "InnoSustain" in doc.extracted_text and doc.page_count == 1


def test_index_job_reports_extraction_failure_without_failing(db, storage, run_jobs_inline, fake_embeddings):
    doc = _tender_doc(db, storage, "protected.pdf", _protected_pdf(), "application/pdf")

    job = JobService.enqueue(
        db,
        "index_document",
        entity_kind="tender_document",
        entity_id=doc.id,
        kind="tender_document",
        document_id=str(doc.id),
    )
    db.refresh(job)

    assert job.status == JobStatus.done, job.error
    assert job.result["chunks"] == 0 and "PDF protégé" in job.result["error"]
    assert doc.extraction_status == ExtractionStatus.failed and "PDF protégé" in doc.error
    assert _chunks(db, doc.id) == []


def test_index_job_indexes_a_readable_document(db, storage, run_jobs_inline, fake_embeddings, fixtures_dir):
    doc = _tender_doc(
        db, storage, "sample.pdf", (fixtures_dir / "sample.pdf").read_bytes(), "application/pdf"
    )
    job = JobService.enqueue(
        db,
        "index_document",
        entity_kind="tender_document",
        entity_id=doc.id,
        kind="tender_document",
        document_id=str(doc.id),
    )
    db.refresh(job)
    assert job.status == JobStatus.done and job.result == {"chunks": len(_chunks(db, doc.id)), "pages": 1}
    assert doc.extraction_status == ExtractionStatus.done


def test_missing_file_in_storage_is_a_failure(db, storage, fake_embeddings):
    doc = _tender_doc(db, storage, "gone.pdf", b"%PDF-1.4", "application/pdf")
    storage.delete(doc.storage_key)
    IndexingService(db, storage, fake_embeddings).index("tender_document", doc)
    assert doc.extraction_status == ExtractionStatus.failed and "stockage" in doc.error.lower()
