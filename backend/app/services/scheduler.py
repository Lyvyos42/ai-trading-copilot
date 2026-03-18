"""
Background scheduler — runs the news scraper every 5 minutes using APScheduler.
"""
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

log = structlog.get_logger()

_scheduler: AsyncIOScheduler | None = None


async def _scrape_job():
    try:
        from app.services.news_scraper import scrape_all_feeds
        count = await scrape_all_feeds()
        log.info("scheduler_scrape_complete", new_articles=count)
    except Exception as exc:
        log.error("scheduler_scrape_failed", error=str(exc))


def start_scheduler():
    global _scheduler
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.add_job(
        _scrape_job,
        trigger=IntervalTrigger(minutes=5),
        id="news_scraper",
        name="News Feed Scraper",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    log.info("scheduler_started", job="news_scraper", interval_minutes=5)


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler_stopped")
