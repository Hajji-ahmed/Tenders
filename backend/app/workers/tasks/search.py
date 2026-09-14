"""Job `search_tenders` : pour un profil de recherche, interroge chaque source active (par priorité),
enregistre les nouvelles opportunités et rend un rapport par source. Une source en erreur n'arrête
jamais la recherche ; le job n'échoue que sur un problème global (profil inconnu, base indisponible)."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from app.core import deps
from app.core.audit import record_audit
from app.core.logging import get_logger
from app.models import SearchProfile, TenderSource
from app.services.collect import CollectService
from app.services.ingest import IngestService, IngestStats
from app.services.query_builder import build_queries
from app.workers.tracking import set_progress, tracked_task

log = get_logger("search")


@tracked_task("search_tenders")
def search_tenders(db, job, *, search_profile_id: str) -> dict:
    profile = db.get(SearchProfile, UUID(search_profile_id))
    if profile is None:
        raise ValueError(f"Profil de recherche introuvable : {search_profile_id}")
    sources = list(
        db.scalars(
            select(TenderSource)
            .where(TenderSource.is_enabled.is_(True))
            .order_by(TenderSource.priority, TenderSource.name)
        )
    )
    queries = build_queries(profile)
    collect = CollectService(
        deps.get_web_search(),
        deps.get_crawler(),
        deps.get_tender_extractor(),
        rss=deps.get_rss(),
        js_crawler=deps.get_js_crawler(),
    )
    ingest = IngestService(db)
    totals = IngestStats()
    reports: dict[str, dict] = {}

    for index, source in enumerate(sources):
        set_progress(
            db,
            job,
            int(index * 100 / max(len(sources), 1)),
            f"Source {index + 1}/{len(sources)} : {source.name}",
        )
        report = collect.collect_source(source, queries, already_known=ingest.known_url)
        stats = ingest.ingest(report, profile)
        totals.add(stats)
        source.last_run_at = datetime.now(UTC)
        source.last_status = report.status
        source.last_error = report.error
        db.flush()
        reports[str(source.id)] = {
            "name": source.name,
            "kind": str(source.kind),
            **report.as_dict(),
            **stats.as_dict(),
        }
        log.info("search.source_done", source=source.name, **report.as_dict(), **stats.as_dict())

    profile.last_run_at = datetime.now(UTC)
    record_audit(
        db,
        action="search.launched",
        entity_kind="search_profile",
        entity_id=profile.id,
        payload={"job_id": str(job.id), "sources": len(sources), **totals.as_dict()},
    )
    return {**totals.as_dict(), "queries": queries, "sources": reports}
