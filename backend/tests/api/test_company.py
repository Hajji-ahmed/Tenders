import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models import AuditLog, Company, CompanyDocument, DocumentCategory, DocumentStatus, Skill

PROFILE = "/api/v1/company/profile"
SKILLS = "/api/v1/company/skills"


# --- Profil ---------------------------------------------------------------------------------------


def test_get_profile_creates_company(auth_client, db):
    r = auth_client.get(PROFILE)
    assert r.status_code == 200
    body = r.json()
    assert body["legal_name"] == "" and body["sectors"] == [] and body["positioning"] is None
    assert body["counts"] == {
        "skills": 0,
        "technologies": 0,
        "certifications": 0,
        "experts": 0,
        "projects": 0,
        "references": 0,
        "documents": 0,
    }
    auth_client.get(PROFILE)  # un second GET ne crée pas une seconde entreprise
    assert db.scalar(select(func.count()).select_from(Company)) == 1


def test_get_profile_returns_fixture_company(auth_client, company):
    body = auth_client.get(PROFILE).json()
    assert body["id"] == str(company.id)
    assert body["trade_name"] == "InnoSustain" and body["country"] == "MA"
    assert body["sectors"] == ["Environnement", "Énergie", "Conseil"]
    assert body["counts"]["technologies"] == 3
    assert body["counts"]["certifications"] == 2
    assert body["counts"]["projects"] == 2


def test_put_profile_partial(auth_client, company, db):
    r = auth_client.put(PROFILE, json={"city": "Rabat", "positioning": "Conseil en transition énergétique"})
    assert r.status_code == 200
    body = r.json()
    assert body["legal_name"] == "Innovative & Sustainable Solutions"  # non envoyé : inchangé
    assert body["city"] == "Rabat"
    assert body["positioning"] == "Conseil en transition énergétique"
    db.refresh(company.profile)
    assert company.profile.positioning == "Conseil en transition énergétique"


def test_put_profile_sectors_and_country_normalised(auth_client):
    r = auth_client.put(PROFILE, json={"country": "ma", "sectors": [" Énergie ", "Conseil", "Énergie", ""]})
    assert r.status_code == 200
    assert r.json()["country"] == "MA"
    assert r.json()["sectors"] == ["Énergie", "Conseil"]


def test_put_profile_rejects_invalid_values(auth_client):
    r = auth_client.put(PROFILE, json={"legal_name": None})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = auth_client.put(PROFILE, json={"country": "Maroc"})
    assert r.status_code == 422 and "country" in r.json()["error"]["message"]
    r = auth_client.put(PROFILE, json={"email": "pas-un-email"})
    assert r.status_code == 422


def test_profile_counts_exclude_archived_documents(auth_client, company, db):
    common = {
        "company_id": company.id,
        "category": DocumentCategory.administratif,
        "storage_key": "k",
        "mime_type": "application/pdf",
        "size_bytes": 1,
        "sha256": "a" * 64,
    }
    db.add(CompanyDocument(name="Kbis", **common))
    db.add(CompanyDocument(name="Ancien Kbis", status=DocumentStatus.archived, **common))
    db.flush()
    assert auth_client.get(PROFILE).json()["counts"]["documents"] == 1


# --- CRUD générique (sur /company/skills) ---------------------------------------------------------


def test_skill_crud(auth_client):
    r = auth_client.post(SKILLS, json={"name": "Audit énergétique", "category": "expertise"})
    assert r.status_code == 201
    created = r.json()
    sid = created["id"]
    assert created["category"] == "expertise" and created["level"] is None

    page = auth_client.get(SKILLS).json()
    assert page["total"] == 1 and page["page"] == 1 and page["size"] == 50
    assert page["items"][0]["id"] == sid

    assert auth_client.get(f"{SKILLS}/{sid}").json()["name"] == "Audit énergétique"

    r = auth_client.patch(f"{SKILLS}/{sid}", json={"level": "expert"})
    assert r.status_code == 200
    assert r.json()["level"] == "expert" and r.json()["name"] == "Audit énergétique"

    assert auth_client.delete(f"{SKILLS}/{sid}").status_code == 204
    assert auth_client.get(SKILLS).json()["total"] == 0
    assert auth_client.get(f"{SKILLS}/{sid}").status_code == 404


def test_create_attaches_to_company(auth_client, company, db):
    r = auth_client.post(SKILLS, json={"name": "Bilan carbone"})
    assert r.status_code == 201
    skill = db.get(Skill, uuid.UUID(r.json()["id"]))
    assert skill.company_id == company.id
    assert auth_client.get(PROFILE).json()["counts"]["skills"] == 1


def test_pagination(auth_client):
    for name in ["A", "B", "C"]:
        auth_client.post(SKILLS, json={"name": name})
    page = auth_client.get(f"{SKILLS}?page=2&size=2").json()
    assert page["total"] == 3 and page["page"] == 2 and page["size"] == 2
    assert [s["name"] for s in page["items"]] == ["C"]  # tri par nom
    assert auth_client.get(f"{SKILLS}?size=0").status_code == 422
    assert auth_client.get(f"{SKILLS}?size=101").status_code == 422
    assert auth_client.get(f"{SKILLS}?page=0").status_code == 422


def test_not_found_uses_error_envelope(auth_client):
    missing = uuid.uuid4()
    for r in (
        auth_client.get(f"{SKILLS}/{missing}"),
        auth_client.patch(f"{SKILLS}/{missing}", json={"level": "x"}),
        auth_client.delete(f"{SKILLS}/{missing}"),
    ):
        assert r.status_code == 404
        assert r.json()["error"]["code"] == "not_found"


def test_items_of_another_company_are_invisible(auth_client, company, db):
    # created_at explicite : dans une même transaction PostgreSQL, now() est identique pour les deux
    # lignes et l'ordre de get_or_create serait indéterminé.
    other = Company(legal_name="Autre société", created_at=datetime.now(UTC) + timedelta(days=1))
    db.add(other)
    db.flush()
    foreign = Skill(company_id=other.id, name="Hors périmètre")
    db.add(foreign)
    db.flush()
    assert auth_client.get(SKILLS).json()["total"] == 0
    assert auth_client.get(f"{SKILLS}/{foreign.id}").status_code == 404
    assert auth_client.delete(f"{SKILLS}/{foreign.id}").status_code == 404


def test_validation_errors(auth_client):
    assert auth_client.post(SKILLS, json={"category": "expertise"}).status_code == 422  # name requis
    assert auth_client.post(SKILLS, json={"name": "x", "category": "inconnue"}).status_code == 422
    sid = auth_client.post(SKILLS, json={"name": "Éolien"}).json()["id"]
    r = auth_client.patch(f"{SKILLS}/{sid}", json={"name": None})  # null sur colonne NOT NULL
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    r = auth_client.patch(f"{SKILLS}/{sid}", json={"description": None})  # null sur colonne nullable
    assert r.status_code == 200 and r.json()["description"] is None


def test_audit_recorded(auth_client, db, user):
    sid = auth_client.post(SKILLS, json={"name": "SIG"}).json()["id"]
    auth_client.patch(f"{SKILLS}/{sid}", json={"level": "avancé"})
    auth_client.put(PROFILE, json={"city": "Rabat"})
    logs = list(db.scalars(select(AuditLog).where(AuditLog.action == "profile.updated")))
    kinds = sorted((log.entity_kind, log.payload.get("op") or log.payload.get("fields")[0]) for log in logs)
    assert kinds == [("company", "city"), ("skills", "create"), ("skills", "update")]
    assert all(log.user_id == user.id for log in logs)
    assert {str(log.entity_id) for log in logs if log.entity_kind == "skills"} == {sid}


def test_company_requires_auth(client):
    assert client.get(PROFILE).status_code == 401
    assert client.get(SKILLS).status_code == 401
    assert client.post(SKILLS, json={"name": "x"}).status_code == 401


# --- Sous-ressources spécifiques ------------------------------------------------------------------


def test_certification_exposes_validity(auth_client, company):
    page = auth_client.get("/api/v1/company/certifications").json()
    assert page["total"] == 2
    by_name = {c["name"]: c for c in page["items"]}
    assert by_name["ISO 14001"]["is_valid"] is True
    assert by_name["ISO 9001"]["is_valid"] is False
    r = auth_client.post(
        "/api/v1/company/certifications",
        json={"name": "ISO 27001", "category": "securite", "expires_at": "2020-01-01"},
    )
    assert r.status_code == 201 and r.json()["is_valid"] is False
    r = auth_client.post("/api/v1/company/certifications", json={"name": "Qualiopi"})  # sans expiration
    assert r.json()["is_valid"] is True and r.json()["category"] == "autre"


def test_technologies_from_fixture(auth_client, company):
    page = auth_client.get("/api/v1/company/technologies").json()
    assert [(t["name"], t["category"]) for t in page["items"]] == [
        ("PostgreSQL", "database"),
        ("Power BI", "tool"),
        ("Python", "language"),
    ]


def test_project_roundtrip(auth_client, company):
    r = auth_client.post(
        "/api/v1/company/projects",
        json={
            "title": "Schéma directeur énergie",
            "client": "Région Z",
            "sector": "Énergie",
            "country": "ma",
            "start_date": "2025-01-15",
            "budget": 120000.5,
            "currency": "mad",
            "technologies": ["Python", "Power BI", "Python"],
            "is_reference": True,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["budget"] == 120000.5 and body["currency"] == "MAD" and body["country"] == "MA"
    assert body["technologies"] == ["Python", "Power BI"] and body["is_reference"] is True
    assert auth_client.get("/api/v1/company/projects").json()["total"] == 3
    assert auth_client.post("/api/v1/company/projects", json={"title": "x", "budget": -1}).status_code == 422


def test_expert_and_reference_create(auth_client, company):
    r = auth_client.post(
        "/api/v1/company/experts",
        json={
            "full_name": "Amina B.",
            "role": "Cheffe de projet",
            "years_experience": 12,
            "skills": ["ISO 14001"],
        },
    )
    assert r.status_code == 201 and r.json()["skills"] == ["ISO 14001"]
    project_id = auth_client.get("/api/v1/company/projects").json()["items"][0]["id"]
    r = auth_client.post(
        "/api/v1/company/references",
        json={
            "client_name": "Office National X",
            "project_id": project_id,
            "contact_email": "dg@example.com",
        },
    )
    assert r.status_code == 201 and r.json()["project_id"] == project_id
    bad_email = {"client_name": "X", "contact_email": "nope"}
    assert auth_client.post("/api/v1/company/references", json=bad_email).status_code == 422
    assert auth_client.post("/api/v1/company/references", json={"contact_name": "X"}).status_code == 422
