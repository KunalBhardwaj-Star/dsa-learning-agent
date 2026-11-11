import sys
import os
import logging
from sqlalchemy.orm import Session

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.db.database import SessionLocal, engine, verify_database_connection
from backend.db.models import Base, Topic
from backend.services.leetcode_sync import sync_leetcode_catalog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SeedDB")

# Taxonomy topics array (used strictly for catalog initialization, not runtime logic)
DEFAULT_TOPICS = [
    "Arrays", "Strings", "Two Pointers", "Sliding Window",
    "Hashing", "Stack", "Queue", "Linked List",
    "Trees", "Binary Search", "Heap", "Graphs",
    "Dynamic Programming", "Greedy", "Backtracking", "Bit Manipulation"
]

def init_and_seed_db():
    """Initializes tables and populates dynamic LeetCode catalog into PostgreSQL."""
    logger.info("Verifying PostgreSQL database connection...")
    verify_database_connection()

    # Create tables if missing
    Base.metadata.create_all(bind=engine)

    session: Session = SessionLocal()
    try:
        # 1. Seed base topic taxonomy dynamically
        logger.info("Seeding base topic taxonomy...")
        for topic_name in DEFAULT_TOPICS:
            existing = session.query(Topic).filter_by(name=topic_name).first()
            if not existing:
                session.add(Topic(name=topic_name))
        session.commit()

        # 2. Sync full dynamic LeetCode catalog into database
        logger.info("Fetching and upserting dynamic LeetCode problem catalog...")
        catalog_result = sync_leetcode_catalog(session)
        logger.info(f"Catalog Sync Result: {catalog_result}")

    except Exception as e:
        session.rollback()
        logger.error(f"Failed to seed database: {e}")
        raise e
    finally:
        session.close()

if __name__ == "__main__":
    init_and_seed_db()