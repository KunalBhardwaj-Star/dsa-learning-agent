import uuid
import requests
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.db.models import User, Problem, Topic, ProblemTopic, UserSkill, Attempt, BanditParam, UserSolvedProblem, DifficultyLevel
from scripts.leetcode_import.topic_mapper import TAG_TO_TOPIC

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"


def fetch_leetcode_graphql_user(username: str) -> Optional[Dict[str, Any]]:
    """
    Queries LeetCode GraphQL API for live user profile, solved breakdown, recent submissions, and contest rating.
    Works for ANY valid LeetCode handle.
    """
    query = """
    query userPublicProfile($username: String!) {
        matchedUser(username: $username) {
            username
            githubUrl
            profile {
                ranking
                reputation
                userAvatar
                realName
            }
            submitStats {
                acSubmissionNum {
                    difficulty
                    count
                }
                totalSubmissionNum {
                    difficulty
                    count
                }
            }
            tagProblemCounts {
                fundamental {
                    tagName
                    tagSlug
                    problemsSolved
                }
                intermediate {
                    tagName
                    tagSlug
                    problemsSolved
                }
                advanced {
                    tagName
                    tagSlug
                    problemsSolved
                }
            }
        }
        recentSubmissionList(username: $username, limit: 20) {
            title
            titleSlug
            timestamp
            statusDisplay
            lang
            memory
            runtime
        }
        userContestRanking(username: $username) {
            rating
            globalRanking
            topPercentage
            totalParticipants
        }
    }
    """
    try:
        resp = requests.post(
            LEETCODE_GRAPHQL_URL,
            json={"query": query, "variables": {"username": username}},
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data and data["data"].get("matchedUser"):
                return data["data"]
    except Exception as e:
        print(f"GraphQL request failed for username='{username}': {e}")
    return None


def sync_leetcode_catalog(session: Session) -> Dict[str, Any]:
    """
    Production dynamic LeetCode catalog synchronization.
    Fetches complete current LeetCode problem catalog (4000+ problems) from official endpoint:
    https://leetcode.com/api/problems/all/
    Upserts into PostgreSQL `problems` & `bandit_params` tables.
    Idempotent, non-destructive, with detailed audit metrics.
    """
    url = "https://leetcode.com/api/problems/all/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    discovered = 0
    inserted = 0
    updated = 0
    unchanged = 0
    failed = 0

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"Catalog sync request returned status {resp.status_code}")
            return {
                "status": "failed",
                "message": f"LeetCode catalog API status {resp.status_code}",
                "discovered": 0, "inserted": 0, "updated": 0, "unchanged": 0, "failed": 1
            }

        data = resp.json()
        stat_pairs = data.get("stat_status_pairs", [])
        discovered = len(stat_pairs)

        eye_8x8 = np.eye(8, dtype=np.float64).tolist()
        zero_8x1 = np.zeros((8, 1), dtype=np.float64).tolist()

        for item in stat_pairs:
            stat = item.get("stat", {})
            qid = stat.get("frontend_question_id")
            title = stat.get("question__title")
            title_slug = stat.get("question__title_slug")
            diff_level = item.get("difficulty", {}).get("level", 1)

            if not qid or not title or not title_slug:
                failed += 1
                continue

            diff_enum = DifficultyLevel.EASY if diff_level == 1 else (DifficultyLevel.MEDIUM if diff_level == 2 else DifficultyLevel.HARD)
            exp_time = 15 if diff_level == 1 else (25 if diff_level == 2 else 40)

            p = session.query(Problem).filter_by(frontend_question_id=qid).first()
            if not p:
                p = Problem(
                    frontend_question_id=qid,
                    title=title,
                    title_slug=title_slug,
                    difficulty=diff_enum,
                    expected_time_minutes=exp_time,
                )
                session.add(p)
                session.flush()
                inserted += 1

                bp = session.query(BanditParam).filter_by(arm_id=qid).first()
                if not bp:
                    bp = BanditParam(
                        arm_id=qid,
                        matrix_a=eye_8x8,
                        vector_b=zero_8x1
                    )
                    session.add(bp)
            else:
                is_changed = False
                if p.title != title:
                    p.title = title
                    is_changed = True
                if p.title_slug != title_slug:
                    p.title_slug = title_slug
                    is_changed = True
                if p.difficulty != diff_enum:
                    p.difficulty = diff_enum
                    is_changed = True

                if is_changed:
                    updated += 1
                else:
                    unchanged += 1

        session.commit()
        return {
            "status": "success",
            "discovered": discovered,
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
            "failed": failed,
        }
    except Exception as e:
        session.rollback()
        print(f"Error during catalog sync: {e}")
        return {
            "status": "failed",
            "message": str(e),
            "discovered": discovered,
            "inserted": inserted,
            "updated": updated,
            "unchanged": unchanged,
            "failed": failed + 1,
        }



def sync_leetcode_activity(
    username_or_id: Any,
    profile_data: Optional[Dict[str, Any]] = None,
    session: Session = None,
) -> Dict[str, Any]:
    """
    Fetch live LeetCode data for an existing application user.
    Does not create users or persist fetched LeetCode activity.
    """

    if session is None:
        raise ValueError("A database session is required to resolve the application user.")

    # Resolve an existing application user only.
    user = None

    if isinstance(username_or_id, uuid.UUID):
        user = session.query(User).filter_by(id=username_or_id).first()

    elif isinstance(username_or_id, str):
        try:
            user_id = uuid.UUID(username_or_id)
            user = session.query(User).filter_by(id=user_id).first()
        except ValueError:
            user = session.query(User).filter_by(
                leetcode_handle=username_or_id
            ).first()

    if user is None:
        return {
            "status": "error",
            "message": "Application user not found. Please log in first.",
        }

    username = user.leetcode_handle

    if not username:
        return {
            "status": "error",
            "message": "No LeetCode handle is connected to this account.",
            "user_id": str(user.id),
        }

    # Fetch live data. No profile_data is persisted.
    if profile_data is None:
        profile_data = fetch_leetcode_graphql_user(username)

    if not profile_data or not profile_data.get("matchedUser"):
        return {
            "status": "error",
            "message": f"Could not fetch live LeetCode data for '{username}'.",
            "user_id": str(user.id),
            "leetcode_handle": username,
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }

    matched_user = profile_data["matchedUser"]
    profile_info = matched_user.get("profile") or {}

    submit_stats = matched_user.get("submitStats") or {}
    accepted_submissions = submit_stats.get("acSubmissionNum") or []

    solved_counts = {
        stat.get("difficulty"): stat.get("count", 0)
        for stat in accepted_submissions
    }

    contest = profile_data.get("userContestRanking") or {}

    # Convert the live topic counts into a read-only response.
    tag_counts = matched_user.get("tagProblemCounts") or {}
    topic_solved = {}

    for bucket in ("fundamental", "intermediate", "advanced"):
        for entry in tag_counts.get(bucket, []):
            topic_name = TAG_TO_TOPIC.get(entry.get("tagSlug"))
            if topic_name:
                topic_solved[topic_name] = (
                    topic_solved.get(topic_name, 0)
                    + entry.get("problemsSolved", 0)
                )

    return {
        "status": "success",
        "user_id": str(user.id),
        "leetcode_handle": username,
        "username": user.username,
        "user_avatar": profile_info.get("userAvatar"),
        "total_solved": solved_counts.get("All", 0),
        "easy_solved": solved_counts.get("Easy", 0),
        "medium_solved": solved_counts.get("Medium", 0),
        "hard_solved": solved_counts.get("Hard", 0),
        "contest_rating": (
            round(contest["rating"])
            if contest.get("rating") is not None
            else None
        ),
        "global_ranking": profile_info.get("ranking"),
        "topics_solved": topic_solved,
        "recent_submissions": profile_data.get("recentSubmissionList") or [],
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
