"""Endpoints /documents : dépôt multipart, filtres, versions, téléchargement, archivage (RB-007)."""

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models.audit import AuditLog

DOCS = "/api/v1/documents"
PDF = "application/pdf"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _upload(client, filename: str, data: bytes, content_type: str, **fields) -> dict:
    r = client.post(DOCS, files={"file": (filename, data, content_type)}, data=fields)
    assert r.status_code == 201, r.text
    return r.json()


def _total(client, query: str) -> int:
    r = client.get(f"{DOCS}{query}")
    assert r.status_code == 200, r.text
    return r.json()["total"]


def _seed(client) -> dict[str, dict]:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    return {
        "kbis": _upload(client, "kbis.pdf", b"%PDF-1.4 kbis", PDF, category="administratif", tags="kbis"),
        "fiscale": _upload(
            client,
            "attestation.pdf",
            b"%PDF-1.4 fiscale",
            PDF,
            category="attestation",
            name="Attestation fiscale 2025",
            expires_at=yesterday,
        ),
        "plaquette": _upload(
            client,
            "plaquette.docx",
            b"PK\x03\x04 plaquette",
            DOCX,
            category="presentation",
            name="Plaquette InnoSustain",
            tags="commercial",
        ),
    }


def test_upload_returns_201_with_metadata(auth_client, company):
    body = _upload(
        auth_client,
        "kbis.pdf",
        b"%PDF-1.4 kbis",
        PDF,
        category="administratif",
        tags="kbis, 2026,kbis",
        description="Extrait Kbis",
    )
    assert body["company_id"] == str(company.id)
    assert body["name"] == "kbis.pdf"  # nom par défaut = nom du fichier
    assert body["category"] == "administratif"
    assert body["status"] == "valid" and body["version"] == 1
    assert body["tags"] == ["kbis", "2026"]  # CSV nettoyé, doublons supprimés
    assert body["size_bytes"] == len(b"%PDF-1.4 kbis") and len(body["sha256"]) == 64
    assert body["is_expired"] is False and body["is_usable"] is True
    assert "storage_key" not in body and "extracted_text" not in body


def test_upload_with_past_expiry_is_marked_expired_immediately(auth_client, company):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    body = _upload(
        auth_client,
        "cnss.pdf",
        b"%PDF-1.4 cnss",
        PDF,
        category="attestation",
        name="Attestation CNSS 2025",
        expires_at=yesterday,
    )
    assert body["name"] == "Attestation CNSS 2025"
    assert body["expires_at"] == yesterday
    assert body["is_expired"] is True and body["is_usable"] is False
    assert body["status"] == "expired"  # RB-007 appliquée sans attendre la tâche nocturne


def test_upload_rejects_unsupported_type(auth_client, company):
    files = {"file": ("setup.exe", b"MZ\x90\x00", "application/octet-stream")}
    r = auth_client.post(DOCS, files=files, data={"category": "autre"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "unsupported_file_type"  # code précis, exploitable par le front


def test_upload_rejects_unknown_category(auth_client, company):
    r = auth_client.post(DOCS, files={"file": ("a.pdf", b"%PDF", PDF)}, data={"category": "inconnue"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_upload_duplicate_is_conflict(auth_client, company):
    _upload(auth_client, "a.pdf", b"%PDF-1.4 same", PDF, category="autre")
    r = auth_client.post(DOCS, files={"file": ("b.pdf", b"%PDF-1.4 same", PDF)}, data={"category": "autre"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "duplicate_document"


def test_list_filters(auth_client, company):
    docs = _seed(auth_client)
    assert _total(auth_client, "") == 3
    assert _total(auth_client, "?category=administratif") == 1
    assert _total(auth_client, "?status=expired") == 1
    assert _total(auth_client, "?status=valid") == 2
    assert _total(auth_client, "?tag=kbis") == 1
    assert _total(auth_client, "?tag=inconnu") == 0
    assert _total(auth_client, "?q=FISCALE") == 1  # insensible à la casse
    assert _total(auth_client, "?usable_only=true") == 2
    assert _total(auth_client, "?category=attestation&usable_only=true") == 0
    r = auth_client.get(f"{DOCS}?category=attestation")
    assert r.json()["items"][0]["id"] == docs["fiscale"]["id"]


def test_list_pagination(auth_client, company):
    _seed(auth_client)
    page1 = auth_client.get(f"{DOCS}?size=2").json()
    page2 = auth_client.get(f"{DOCS}?page=2&size=2").json()
    assert page1["total"] == 3 and page1["page"] == 1 and page1["size"] == 2
    assert len(page1["items"]) == 2 and len(page2["items"]) == 1
    ids = {d["id"] for d in page1["items"]} | {d["id"] for d in page2["items"]}
    assert len(ids) == 3  # ordre stable entre les pages
    assert auth_client.get(f"{DOCS}?size=1000").status_code == 422


def test_get_and_patch_metadata(auth_client, company):
    did = _upload(auth_client, "rc.pdf", b"%PDF-1.4 rc", PDF, category="administratif")["id"]
    r = auth_client.get(f"{DOCS}/{did}")
    assert r.status_code == 200 and r.json()["name"] == "rc.pdf"

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    body = {"name": "Registre de commerce", "tags": [" rc ", "", "2026"], "expires_at": yesterday}
    r = auth_client.patch(f"{DOCS}/{did}", json=body)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Registre de commerce"
    assert r.json()["tags"] == ["rc", "2026"]
    assert r.json()["status"] == "expired" and r.json()["is_usable"] is False

    next_year = (date.today() + timedelta(days=365)).isoformat()
    r = auth_client.patch(f"{DOCS}/{did}", json={"expires_at": next_year})
    assert r.json()["status"] == "valid" and r.json()["is_usable"] is True  # RB-007 dans les deux sens

    assert auth_client.patch(f"{DOCS}/{did}", json={"name": ""}).status_code == 422
    assert auth_client.get(f"{DOCS}/{uuid.uuid4()}").status_code == 404


def test_new_version_and_versions_list(auth_client, company):
    did = _upload(auth_client, "kbis.pdf", b"%PDF-1.4 v1", PDF, category="administratif")["id"]
    files = {"file": ("kbis-2026.pdf", b"%PDF-1.4 v2", PDF)}
    r = auth_client.post(f"{DOCS}/{did}/versions", files=files, data={"changelog": "Kbis à jour"})
    assert r.status_code == 201, r.text
    assert r.json()["version"] == 2
    assert r.json()["size_bytes"] == len(b"%PDF-1.4 v2")
    versions = auth_client.get(f"{DOCS}/{did}/versions").json()
    assert [v["version_number"] for v in versions] == [1, 2]
    assert versions[1]["changelog"] == "Kbis à jour"
    assert auth_client.get(f"{DOCS}/{did}/download").content == b"%PDF-1.4 v2"


def test_download_returns_bytes_and_attachment_header(auth_client, company):
    did = _upload(auth_client, "kbis.pdf", b"%PDF-1.4 test", PDF, category="administratif")["id"]
    r = auth_client.get(f"{DOCS}/{did}/download")
    assert r.status_code == 200
    assert r.content == b"%PDF-1.4 test"
    assert r.headers["content-type"] == "application/pdf"
    assert r.headers["content-disposition"] == 'attachment; filename="kbis.pdf"'


def test_download_name_adds_extension_and_encodes_utf8(auth_client, company):
    body = _upload(auth_client, "att.pdf", b"%PDF-1.4 att", PDF, category="attestation", name="Reçu été")
    r = auth_client.get(f"{DOCS}/{body['id']}/download")
    cd = r.headers["content-disposition"]
    assert cd.startswith('attachment; filename="Recu ete.pdf"')  # repli ASCII
    assert "filename*=utf-8''Re%C3%A7u%20%C3%A9t%C3%A9.pdf" in cd  # RFC 5987


def test_delete_archives_and_excludes_from_usable(auth_client, company):
    did = _upload(auth_client, "kbis.pdf", b"%PDF-1.4 kbis", PDF, category="administratif")["id"]
    assert _total(auth_client, "?usable_only=true") == 1
    assert auth_client.delete(f"{DOCS}/{did}").status_code == 204
    body = auth_client.get(f"{DOCS}/{did}").json()
    assert body["status"] == "archived" and body["is_usable"] is False
    assert _total(auth_client, "?usable_only=true") == 0
    assert _total(auth_client, "?status=archived") == 1
    r = auth_client.post(f"{DOCS}/{did}/versions", files={"file": ("kbis.pdf", b"%PDF-1.4 v2", PDF)})
    assert r.status_code == 409  # un document archivé ne reçoit plus de version


def test_actions_are_audited(auth_client, company, db, user):
    did = _upload(auth_client, "kbis.pdf", b"%PDF-1.4 kbis", PDF, category="administratif")["id"]
    auth_client.patch(f"{DOCS}/{did}", json={"description": "Kbis"})
    auth_client.delete(f"{DOCS}/{did}")
    logs = list(db.scalars(select(AuditLog).where(AuditLog.entity_id == uuid.UUID(did))))
    assert {log.action for log in logs} == {"document.uploaded", "document.updated", "document.archived"}
    assert all(log.user_id == user.id for log in logs)
    updated = next(log for log in logs if log.action == "document.updated")
    assert updated.entity_kind == "company_document" and updated.payload == {"fields": ["description"]}


def test_documents_require_auth(client):
    assert client.get(DOCS).status_code == 401
    r = client.post(DOCS, files={"file": ("a.pdf", b"%PDF", PDF)}, data={"category": "autre"})
    assert r.status_code == 401
    assert client.get(f"{DOCS}/{uuid.uuid4()}/download").status_code == 401
