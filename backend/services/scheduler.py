import os
import sys
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.db.database import SessionLocal
from backend.db.models import User
from backend.services.leetcode_sync import sync_leetcode_activity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BackgroundSyncScheduler")

scheduler = BackgroundScheduler()

def scheduled_leetcode_sync_job():
    """
    Background Cron / Scheduler Job:
    Polls LeetCode GraphQL every 15 minutes for all registered users in PostgreSQL.
    """
    db: Session = SessionLocal()
    try:
        users = db.query(User).all()
        logger.info(f"Running scheduled LeetCode sync job for {len(users)} registered users...")

        for user in users:
            try:
                result = sync_leetcode_activity(username_or_id=user.leetcode_handle, session=db)
                logger.info(
                    f"Synced {user.leetcode_handle}: total_solved={result.get('total_solved')}, "
                    f"contest_rating={result.get('contest_rating')}"
                )
            except Exception as e:
                logger.error(f"Error syncing {user.leetcode_handle}: {e}")
    finally:
        db.close()


def start_scheduler(interval_minutes: int = 15):
    """Starts the background APScheduler loop."""
    if not scheduler.running:
        scheduler.add_job(
            scheduled_leetcode_sync_job,
            trigger="interval",
            minutes=interval_minutes,
            id="leetcode_background_sync",
            replace_existing=True,
        )
        scheduler.start()
        logger.info(f"Background Sync Scheduler started. Sync interval: every {interval_minutes} minutes.")


def stop_scheduler():
    """Stops the background scheduler."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background Sync Scheduler stopped.")
