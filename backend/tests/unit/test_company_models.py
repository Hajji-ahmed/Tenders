from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import (
    Certification,
    CertificationCategory,
    Company,
    CompanyDocument,
    CompanyProfile,
    DocumentCategory,
    DocumentStatus,
    ExtractionStatus,
    Project,
    Reference,
    Skill,
    SkillCategory,
)


def _company(db) -> Company:
    c = Company(legal_name="Innovative & Sustainable Solutions", trade_name="InnoSustain", country="MA")
    db.add(c)
    db.flush()
    return c


def _document(company, **kw) -> CompanyDocument:
    base = dict(
        company_id=company.id,
        name="Attestation",
        category=DocumentCategory.attestation,
        storage_key="company/ab/abc.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        sha256="a" * 64,
    )
    base.update(kw)
    return CompanyDocument(**base)


def test_document_expiry_and_usability(db):
    c = _company(db)
    expired = _document(c, expires_at=date.today() - timedelta(days=1))
    valid = _document(c, sha256="b" * 64, expires_at=date.today() + timedelta(days=30))
    no_date = _document(c, sha256="c" * 64)
    archived = _document(c, sha256="d" * 64, status=DocumentStatus.archived)
    db.add_all([expired, valid, no_date, archived])
    db.flush()

    assert expired.is_expired and not expired.is_usable
    assert not valid.is_expired and valid.is_usable
    assert no_date.is_usable
    assert not archived.is_usable  # RB-007 : jamais sélectionné automatiquement
    assert valid.status == DocumentStatus.valid
    assert valid.version == 1
    assert valid.extraction_status == ExtractionStatus.pending
    assert valid.tags == []


def test_certification_validity(db):
    c = _company(db)
    ok = Certification(
        company_id=c.id,
        name="ISO 14001",
        category=CertificationCategory.qualite,
        expires_at=date.today() + timedelta(days=365),
    )
    expired = Certification(company_id=c.id, name="ISO 9001", expires_at=date.today() - timedelta(days=30))
    perpetual = Certification(company_id=c.id, name="Agrément")
    db.add_all([ok, expired, perpetual])
    db.flush()
    assert ok.is_valid and perpetual.is_valid and not expired.is_valid
    assert perpetual.category == CertificationCategory.autre


def test_company_relationships_and_cascade(db):
    c = _company(db)
    c.profile = CompanyProfile(positioning="Solutions innovantes et durables")
    c.skills.append(Skill(name="Audit énergétique", category=SkillCategory.expertise))
    project = Project(
        company_id=c.id, title="Plan climat territorial", client="Ville Y", sector="Environnement"
    )
    db.add(project)
    db.flush()
    ref = Reference(company_id=c.id, project_id=project.id, client_name="Ville Y")
    db.add(ref)
    db.flush()

    assert c.profile.company_id == c.id
    assert [s.name for s in c.skills] == ["Audit énergétique"]
    assert ref.project.title == "Plan climat territorial"

    db.delete(c)
    db.flush()
    assert db.scalar(select(Skill).where(Skill.company_id == c.id)) is None
    assert db.scalar(select(CompanyProfile).where(CompanyProfile.company_id == c.id)) is None
    assert db.scalar(select(Project).where(Project.company_id == c.id)) is None


def test_company_profile_is_unique_per_company(db):
    c = _company(db)
    db.add(CompanyProfile(company_id=c.id))
    db.flush()
    db.add(CompanyProfile(company_id=c.id))
    with pytest.raises(IntegrityError):
        db.flush()
