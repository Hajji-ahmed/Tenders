"""Enregistrement des candidats collectés : v1 = une fiche `Tender` par URL nouvelle, avec son lien de
provenance et ses pièces. La fusion des doublons (`merged`) arrive en Phase 4 avec la déduplication."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from urllib.parse import unquote, urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.outputs import TenderCandidate
from app.models import SearchProfile, Tender, TenderDocument, TenderSourceLink, TenderStatus
from app.services.collect import SourceReport


@dataclass
class IngestStats:
    created: int = 0
    merged: int = 0
    skipped: int = 0  # URL déjà connue
    invalid: int = 0  # candidat sans titre ou sans URL

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "merged": self.merged,
            "skipped": self.skipped,
            "invalid": self.invalid,
        }

    def add(self, other: "IngestStats") -> None:
        self.created += other.created
        self.merged += other.merged
        self.skipped += other.skipped
        self.invalid += other.invalid


def end_of_day(d: date | None) -> datetime | None:
    """Une date limite sans heure vaut jusqu'à la fin de la journée (UTC)."""
    return None if d is None else datetime.combine(d, time(23, 59, 59), tzinfo=UTC)


def document_name(url: str) -> str:
    """Nom lisible d'une pièce depuis son URL (dernier segment décodé), « document » à défaut."""
    last = unquote(urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]).strip()
    return last[:255] or "document"


class IngestService:
    def __init__(self, db: Session):
        self.db = db

    def known_url(self, url: str) -> bool:
        return self.db.scalar(select(TenderSourceLink.id).where(TenderSourceLink.url == url)) is not None

    def ingest(self, report: SourceReport, profile: SearchProfile) -> IngestStats:
        stats = IngestStats()
        source_id = UUID(report.source_id) if report.source_id else None
        for candidate in report.candidates:
            url = candidate.source_url.strip()
            if not url or not candidate.title.strip():
                stats.invalid += 1
                continue
            if self.known_url(url):
                stats.skipped += 1
                continue
            self._create(candidate, url, source_id, profile, title_seen=report.titles.get(url))
            self.db.flush()  # rend l'URL connue pour les candidats suivants de la même passe
            stats.created += 1
        return stats

    def _create(
        self,
        c: TenderCandidate,
        url: str,
        source_id: UUID | None,
        profile: SearchProfile,
        *,
        title_seen: str | None,
    ) -> Tender:
        tender = Tender(
            title=c.title.strip()[:512],
            reference=c.reference,
            organization=c.organization,
            organization_type=c.organization_type,
            country=(c.country or "").strip().upper()[:2] or None,
            region=c.region,
            sector=c.sector,
            market_type=c.market_type,
            budget_min=c.budget_min,
            budget_max=c.budget_max,
            currency=(c.currency or "").strip().upper()[:3] or None,
            published_at=c.published_at,
            deadline_at=end_of_day(c.deadline_at),
            questions_deadline_at=end_of_day(c.questions_deadline_at),
            source_url=url,
            description=c.description or None,
            status=TenderStatus.NOUVEAU,
            search_profile_id=profile.id,
            raw=c.model_dump(mode="json"),
            extra={"technologies": c.technologies, "required_certifications": c.required_certifications},
        )
        tender.source_links.append(TenderSourceLink(source_id=source_id, url=url, title_seen=title_seen))
        for doc_url in dict.fromkeys(c.document_urls):
            tender.documents.append(TenderDocument(name=document_name(doc_url), source_url=doc_url))
        self.db.add(tender)
        return tender
