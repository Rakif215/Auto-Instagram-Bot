"""
scheduler.py — Runs the pipeline on a recurring schedule using APScheduler.

Start with: python main.py --schedule
"""

import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from config import POST_INTERVAL_HOURS

logger = logging.getLogger(__name__)


def start(dry_run: bool = False, news_mode: str = "auto"):
    """Start the blocking scheduler. Runs pipeline every POST_INTERVAL_HOURS hours."""
    from main import run_pipeline

    scheduler = BlockingScheduler(timezone="UTC")

    def job():
        logger.info(f"Scheduler triggered (dry_run={dry_run}, news_mode={news_mode})")
        try:
            run_pipeline(dry_run=dry_run, news_mode=news_mode)
        except Exception as e:
            logger.error(f"Scheduled run failed: {e}", exc_info=True)

    scheduler.add_job(
        job,
        trigger="interval",
        hours=POST_INTERVAL_HOURS,
        id="instagram_reel_job",
        name="Post Instagram Reel",
        replace_existing=True,
    )

    logger.info(f"Scheduler started — running every {POST_INTERVAL_HOURS} hour(s). Press Ctrl+C to stop.")

    # Fire once immediately on start so we don't wait for the first interval
    job()

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
