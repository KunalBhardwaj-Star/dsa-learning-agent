import sys
import os
import json
import uuid
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.db.database import engine, SessionLocal
from backend.db.models import (
    Base,
    User,
    Problem,
    Topic,
    ProblemTopic,
    UserSkill,
    BanditParam,
    DifficultyLevel,
    UserSolvedProblem,
)
from backend.services.leetcode_sync import fetch_leetcode_graphql_user, sync_leetcode_activity, sync_leetcode_catalog
from backend.services.auth_service import hash_password

TOPICS_LIST = [
    "Arrays",
    "Strings",
    "LinkedList",
    "Stack",
    "Queue",
    "Hashing",
    "BinarySearch",
    "Trees",
    "Trie",
    "Heap",
    "Graphs",
    "UnionFind",
    "DP",
    "Greedy",
    "Backtracking",
    "BitManipulation",
    "Math",
    "Design",
]


def init_db():
    print("Ensuring database tables exist (non-destructive)...")
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        # 1. Seed Topics Taxonomy
        topic_map = {}
        for name in TOPICS_LIST:
            t = session.query(Topic).filter_by(name=name).first()
            if not t:
                t = Topic(name=name)
                session.add(t)
                session.flush()
            topic_map[name] = t.id
        session.commit()
        print(f"Seeded {len(topic_map)} topics.")

        # 2. Dynamic LeetCode Problem Catalog Synchronization (~4,000+ problems)
        print("Synchronizing production LeetCode catalog from official endpoint...")
        catalog_stats = sync_leetcode_catalog(session)
        print(f"Catalog sync completed: {catalog_stats}")

    except Exception as e:
        session.rollback()
        print(f"Error during init_db: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    init_db()