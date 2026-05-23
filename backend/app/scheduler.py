"""
Single APScheduler instance, owned by the FastAPI app lifespan.
Adds and removes jobs in one place so it's easy to disable for tests.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .config import settings
from .ingestion import disruption, ktmb, rapid_rail_sim
from .news import scrapers as news_scrapers
from .reliability import observer as reliability_observer
from .reliability import rollup as reliability_rollup

log = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    s = AsyncIOScheduler(timezone=settings.timezone)

    # KTMB realtime poll.
    s.add_job(
        ktmb.poll_once,
        "interval",
        seconds=settings.poll_interval_seconds,
        id="poll_ktmb",
        max_instances=1,
        coalesce=True,
    )
    # Rapid rail simulation (MRT/LRT/Monorail) — runs while rapid_rail_live=false.
    s.add_job(
        rapid_rail_sim.poll_once,
        "interval",
        seconds=settings.poll_interval_seconds,
        id="sim_rapid_rail",
        max_instances=1,
        coalesce=True,
    )
    # Disruption detection — runs slightly off-phase so polls finish first.
    s.add_job(
        disruption.run_once,
        "interval",
        seconds=settings.poll_interval_seconds,
        id="detect_disruptions",
        max_instances=1,
        coalesce=True,
    )
    # Reliability observer — records arrival events from live polls.
    s.add_job(
        reliability_observer.run_once,
        "interval",
        seconds=settings.poll_interval_seconds,
        id="reliability_observer",
        max_instances=1,
        coalesce=True,
    )
    # Daily rollup at 02:00 KL time.
    s.add_job(
        reliability_rollup.run_daily,
        "cron",
        hour=2,
        minute=0,
        id="reliability_rollup",
        max_instances=1,
    )
    # News scraping.
    s.add_job(
        news_scrapers.run_once,
        "interval",
        minutes=settings.news_scrape_interval_minutes,
        id="scrape_news",
        max_instances=1,
        coalesce=True,
    )
    s.add_job(news_scrapers.run_once, id="scrape_news_initial", max_instances=1)
    # Kick off initial polls so the UI has data on first load.
    s.add_job(ktmb.poll_once, id="poll_ktmb_initial", max_instances=1)
    s.add_job(rapid_rail_sim.poll_once, id="sim_rapid_rail_initial", max_instances=1)

    s.start()
    _scheduler = s
    log.info("Scheduler started with %d jobs", len(s.get_jobs()))
    return s


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        log.info("Scheduler stopped")
