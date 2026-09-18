"""Déduplicateur RB-001 : une règle par test, dans l'ordre d'application, puis la fusion."""

from datetime import UTC, date, datetime, time

from sqlalchemy import select

from app.ai.embeddings import FakeEmbeddings
from app.ai.outputs import TenderCandidate
from app.models import AuditLog, Tender, TenderDocument, TenderSourceLink
from app.services.dedup import Deduplicator
from app.services.normalize import NormalizedTender, normalize


def _cand(**kw) -> NormalizedTender:
    base = dict(
        is_tender=True, confidence=0.9, title="Refonte du système d'information", source_url="https://b/2"
    )
    base.update(kw)
    return normalize(TenderCandidate(**base))


def _existing(db, n: NormalizedTender, *, url="https://a/1", **over) -> Tender:
    """Fiche déjà en base, créée depuis un candidat normalisé (comme le fera l'ingestion v2)."""
    t = Tender(
        title=n.title,
        organization=n.organization,
        reference=n.reference,
        country=n.country,
        deadline_at=datetime.combine(n.deadline_at, time(23, 59), tzinfo=UTC) if n.deadline_at else None,
        norm_title=n.norm_title,
        norm_org=n.norm_org,
        norm_reference=n.norm_reference,
        fingerprint=n.fingerprint,
        extra={"document_urls": list(n.document_urls)},
    )
    for k, v in over.items():
        setattr(t, k, v)
    t.source_links.append(TenderSourceLink(url=url, title_seen=n.title))
    db.add(t)
    db.flush()
    return t


def _dedup(db) -> Deduplicator:
    return Deduplicator(db, FakeEmbeddings(dimensions=8))


def test_rule_1_url_already_linked(db):
    existing = _existing(db, _cand(title="Tout autre titre", organization="Org A"), url="https://a/1")
    match = _dedup(db).find_duplicate(
        _cand(title="Refonte du SI", organization="Org B", source_url="https://a/1")
    )
    assert match is not None and match.tender.id == existing.id and match.rule == "url"


def test_rule_2_reference_and_organization(db):
    existing = _existing(db, _cand(title="Titre initial", organization="Ministère X", reference="AO 12-2026"))
    n = _cand(title="Titre reformulé par la source", organization="ministere x", reference="ao-12/2026")
    match = _dedup(db).find_duplicate(n)
    assert match is not None and match.tender.id == existing.id and match.rule == "reference"


def test_rule_2_tolerates_organization_suffix_but_not_another_organization(db):
    """Parcours réel : « Commune de Salé (Maroc), Direction des services techniques » désigne le même
    acheteur que « Commune de Salé » ; la même référence chez un autre acheteur n'est pas un doublon."""
    existing = _existing(
        db, _cand(title="Éclairage public", organization="Commune de Salé", reference="27/2026")
    )
    n = _cand(
        title="Avis d'appel d'offres ouvert n° 27/2026",
        organization="Commune de Salé (Maroc), Direction des services techniques",
        reference="27/2026",
        deadline_at=None,
    )
    match = _dedup(db).find_duplicate(n)
    assert match is not None and match.tender.id == existing.id and match.rule == "reference"

    other = _cand(
        title="Fourniture de véhicules", organization="Commune de Fès", reference="27/2026", deadline_at=None
    )
    assert _dedup(db).find_duplicate(other) is None


def test_rule_3_fingerprint(db):
    existing = _existing(db, _cand(organization="Ministère X", deadline_at=date(2026, 10, 1)))
    n = _cand(
        title="REFONTE DU SYSTÈME D'INFORMATION", organization="ministere x", deadline_at=date(2026, 10, 1)
    )
    match = _dedup(db).find_duplicate(n)
    assert match is not None and match.tender.id == existing.id and match.rule == "fingerprint"


def test_rule_4_fuzzy_title_with_same_org_or_deadline(db):
    existing = _existing(
        db, _cand(title="Refonte du système d'information de la commune", organization="Commune A")
    )
    # même organisme, titre quasi identique (mots réordonnés / abrégés)
    n = _cand(
        title="Commune A : refonte du système d'information", organization="Commune A", deadline_at=None
    )
    match = _dedup(db).find_duplicate(n)
    assert match is not None and match.tender.id == existing.id and match.rule == "fuzzy_title"
    # même échéance, organisme absent côté candidat
    dated = _existing(
        db,
        _cand(
            title="Audit énergétique de douze bâtiments", organization="Org B", deadline_at=date(2026, 11, 5)
        ),
        url="https://c/3",
    )
    n2 = _cand(
        title="Audit énergétique de 12 bâtiments communaux", organization=None, deadline_at=date(2026, 11, 5)
    )
    match2 = _dedup(db).find_duplicate(n2)
    assert match2 is not None and match2.tender.id == dated.id and match2.rule == "fuzzy_title"


def test_rule_5_semantic_neighbour_within_deadline_window(db):
    emb = FakeEmbeddings()  # 1536 dimensions, comme la colonne
    vec = emb.embed(["audit énergétique bâtiments"])[0]
    existing = _existing(
        db,
        _cand(
            title="Audit énergétique de bâtiments publics",
            organization="Org C",
            deadline_at=date(2026, 12, 1),
        ),
        embedding=vec,
    )
    n = _cand(
        title="Diagnostic de performance énergétique du patrimoine bâti",
        organization="Org D",
        deadline_at=date(2026, 12, 3),
    )
    dedup = Deduplicator(db, emb)
    match = dedup.find_duplicate(n, embedding=vec)  # même vecteur : cosinus = 1
    assert match is not None and match.tender.id == existing.id and match.rule == "semantic"
    # hors fenêtre d'échéance (± 3 jours) : pas de rapprochement sémantique
    far = _cand(title="Diagnostic énergétique", organization="Org D", deadline_at=date(2026, 12, 20))
    assert dedup.find_duplicate(far, embedding=vec) is None
    # vecteur orthogonal : pas de doublon
    other = emb.embed(["fourniture de véhicules"])[0]
    assert dedup.find_duplicate(n, embedding=other) is None


def test_not_a_duplicate_when_titles_differ(db):
    _existing(db, _cand(title="Refonte du système d'information", organization="Org A"))
    n = _cand(title="Fourniture de mobilier scolaire", organization="Org A", source_url="https://z/9")
    assert _dedup(db).find_duplicate(n) is None


def test_inactive_tenders_are_ignored_for_fuzzy_and_semantic_rules(db):
    _existing(db, _cand(title="Refonte du système d'information", organization="Org A"), is_active=False)
    n = _cand(title="Refonte du système d information", organization="Org A", deadline_at=date(2027, 1, 1))
    assert _dedup(db).find_duplicate(n) is None


def test_merge_into_adds_link_fills_gaps_and_never_overwrites(db):
    existing = _existing(
        db,
        _cand(
            title="Refonte du SI",
            organization="Org A",
            budget_max=500000,
            document_urls=["https://a/1/dce.pdf"],
        ),
        budget_max=500000,
    )
    existing.documents.append(TenderDocument(name="dce.pdf", source_url="https://a/1/dce.pdf"))
    db.flush()
    n = _cand(
        title="Refonte du SI (avis rectificatif)",
        organization="Org A",
        reference="AO 7/2026",
        budget_max=999999,
        country="Maroc",
        document_urls=["https://a/1/dce.pdf", "https://b/2/annexe.pdf"],
        technologies=["ERP"],
    )
    merged = _dedup(db).merge_into(
        existing, n, source_id=None, title_seen="Refonte du SI (avis rectificatif)", rule="fuzzy_title"
    )
    db.flush()

    assert merged.id == existing.id
    assert merged.title == "Refonte du SI"  # jamais écrasé
    assert float(merged.budget_max) == 500000  # valeur existante conservée
    assert merged.reference == "AO 7/2026" and merged.country == "MA"  # trous comblés
    urls = {link.url for link in merged.source_links}
    assert urls == {"https://a/1", "https://b/2"}
    assert sorted(merged.extra["document_urls"]) == ["https://a/1/dce.pdf", "https://b/2/annexe.pdf"]
    assert {d.source_url for d in merged.documents} == {"https://a/1/dce.pdf", "https://b/2/annexe.pdf"}
    assert merged.extra["technologies"] == ["ERP"]
    audit = db.scalar(select(AuditLog).where(AuditLog.action == "tender.merged"))
    assert (
        audit is not None and audit.payload["rule"] == "fuzzy_title" and audit.payload["url"] == "https://b/2"
    )

    # Fusionner une seconde fois la même URL n'ajoute pas de lien ni de pièce.
    _dedup(db).merge_into(existing, n, source_id=None, title_seen=None, rule="url")
    db.flush()
    assert len(merged.source_links) == 2 and len(merged.documents) == 2
