import uuid
import requests
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.db.models import (
    User,
    Problem,
    Topic,
    ProblemTopic,
    UserSkill,
    Attempt,
    BanditParam,
    UserSolvedProblem,
    DifficultyLevel,
)
from scripts.leetcode_import.topic_mapper import TAG_TO_TOPIC

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"

GRAPHQL_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com/problemset/all/",
}

# Fallback starter catalog in case network/Cloudflare blocks GraphQL
STARTER_PROBLEM_FALLBACK = [
    {"frontend_question_id": 1, "title": "Two Sum", "title_slug": "two-sum", "difficulty": "Easy", "expected_time_minutes": 15},
    {"frontend_question_id": 2, "title": "Add Two Numbers", "title_slug": "add-two-numbers", "difficulty": "Medium", "expected_time_minutes": 25},
    {"frontend_question_id": 3, "title": "Longest Substring Without Repeating Characters", "title_slug": "longest-substring-without-repeating-characters", "difficulty": "Medium", "expected_time_minutes": 25},
    {"frontend_question_id": 4, "title": "Median of Two Sorted Arrays", "title_slug": "median-of-two-sorted-arrays", "difficulty": "Hard", "expected_time_minutes": 40},
    {"frontend_question_id": 5, "title": "Longest Palindromic Substring", "title_slug": "longest-palindromic-substring", "difficulty": "Medium", "expected_time_minutes": 25},
    {"frontend_question_id": 15, "title": "3Sum", "title_slug": "3sum", "difficulty": "Medium", "expected_time_minutes": 25},
    {"frontend_question_id": 20, "title": "Valid Parentheses", "title_slug": "valid-parentheses", "difficulty": "Easy", "expected_time_minutes": 15},
    {"frontend_question_id": 21, "title": "Merge Two Sorted Lists", "title_slug": "merge-two-sorted-lists", "difficulty": "Easy", "expected_time_minutes": 15},
    {"frontend_question_id": 53, "title": "Maximum Subarray", "title_slug": "maximum-subarray", "difficulty": "Medium", "expected_time_minutes": 25},
    {"frontend_question_id": 70, "title": "Climbing Stairs", "title_slug": "climbing-stairs", "difficulty": "Easy", "expected_time_minutes": 15},
    {"frontend_question_id": 102, "title": "Binary Tree Level Order Traversal", "title_slug": "binary-tree-level-order-traversal", "difficulty": "Medium", "expected_time_minutes": 25},
    {"frontend_question_id": 121, "title": "Best Time to Buy and Sell Stock", "title_slug": "best-time-to-buy-and-sell-stock", "difficulty": "Easy", "expected_time_minutes": 15},
    {"frontend_question_id": 141, "title": "Linked List Cycle", "title_slug": "linked-list-cycle", "difficulty": "Easy", "expected_time_minutes": 15},
    {"frontend_question_id": 200, "title": "Number of Islands", "title_slug": "number-of-islands", "difficulty": "Medium", "expected_time_minutes": 25},
    {"frontend_question_id": 206, "title": "Reverse Linked List", "title_slug": "reverse-linked-list", "difficulty": "Easy", "expected_time_minutes": 15},
    {"frontend_question_id": 300, "title": "Longest Increasing Subsequence", "title_slug": "longest-increasing-subsequence", "difficulty": "Medium", "expected_time_minutes": 25},
]


def fetch_leetcode_graphql_user(username: str) -> Optional[Dict[str, Any]]:
    query = """
    query userPublicProfile($username: String!) {
        matchedUser(username: $username) {
            username
            githubUrl
            profile { ranking reputation userAvatar realName }
            submitStats {
                acSubmissionNum { difficulty count }
                totalSubmissionNum { difficulty count }
            }
            tagProblemCounts {
                fundamental { tagName tagSlug problemsSolved }
                intermediate { tagName tagSlug problemsSolved }
                advanced { tagName tagSlug problemsSolved }
            }
        }
        recentSubmissionList(username: $username, limit: 20) {
            title titleSlug timestamp statusDisplay lang memory runtime
        }
        userContestRanking(username: $username) {
            rating globalRanking topPercentage totalParticipants
        }
    }
    """
    try:
        resp = requests.post(
            LEETCODE_GRAPHQL_URL,
            json={"query": query, "variables": {"username": username}},
            headers=GRAPHQL_HEADERS,
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data and data["data"].get("matchedUser"):
                return data["data"]
    except Exception as e:
        print(f"GraphQL request failed for username='{username}': {e}")
    return None


def fetch_leetcode_catalog_graphql(limit: int = 4000) -> List[Dict[str, Any]]:
    """Fetches full problemset catalog dynamically via LeetCode GraphQL."""
    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
        problemsetQuestionList: questionList(
            categorySlug: $categorySlug
            limit: $limit
            skip: $skip
            filters: $filters
        ) {
            questions: data {
                frontendQuestionId: questionFrontendId
                title
                titleSlug: titleSlug
                difficulty
            }
        }
    }
    """
    variables = {
        "categorySlug": "all-code-essentials",
        "skip": 0,
        "limit": limit,
        "filters": {}
    }
    
    try:
        resp = requests.post(
            LEETCODE_GRAPHQL_URL,
            json={"query": query, "variables": variables},
            headers=GRAPHQL_HEADERS,
            timeout=15
        )
        if resp.status_code == 200:
            res_json = resp.json()
            questions = res_json.get("data", {}).get("problemsetQuestionList", {}).get("questions", [])
            return questions
    except Exception as e:
        print(f"GraphQL catalog query failed: {e}")
    return []


def sync_leetcode_catalog(session: Session) -> Dict[str, Any]:
    """
    Dynamic LeetCode catalog synchronization.
    Queries GraphQL problemset questions and falls back to starter array if blocked.
    Populates PostgreSQL problems & bandit_params (8x8 Identity matrix, 8x1 zero vector).
    """
    discovered = 0
    inserted = 0
    updated = 0
    unchanged = 0
    failed = 0

    questions = fetch_leetcode_catalog_graphql(limit=4000)

    eye_8x8 = np.eye(8, dtype=np.float64).tolist()
    zero_8x1 = np.zeros((8, 1), dtype=np.float64).tolist()

    if questions:
        discovered = len(questions)
        for q in questions:
            qid_str = q.get("frontendQuestionId")
            if not qid_str or not qid_str.isdigit():
                continue
            qid = int(qid_str)
            title = q.get("title")
            title_slug = q.get("titleSlug")
            diff_str = (q.get("difficulty") or "Easy").upper()

            diff_enum = DifficultyLevel.EASY if diff_str == "EASY" else (DifficultyLevel.MEDIUM if diff_str == "MEDIUM" else DifficultyLevel.HARD)
            exp_time = 15 if diff_enum == DifficultyLevel.EASY else (25 if diff_enum == DifficultyLevel.MEDIUM else 40)

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
                    session.add(BanditParam(arm_id=qid, matrix_a=eye_8x8, vector_b=zero_8x1))
            else:
                unchanged += 1
    else:
        # Fallback Seeding Loop
        print("Using fallback local catalog snapshot for PostgreSQL problem seeding...")
        discovered = len(STARTER_PROBLEM_FALLBACK)
        for item in STARTER_PROBLEM_FALLBACK:
            qid = item["frontend_question_id"]
            diff_str = item["difficulty"].upper()
            diff_enum = DifficultyLevel.EASY if diff_str == "EASY" else (DifficultyLevel.MEDIUM if diff_str == "MEDIUM" else DifficultyLevel.HARD)

            p = session.query(Problem).filter_by(frontend_question_id=qid).first()
            if not p:
                session.add(Problem(
                    frontend_question_id=qid,
                    title=item["title"],
                    title_slug=item["title_slug"],
                    difficulty=diff_enum,
                    expected_time_minutes=item["expected_time_minutes"],
                ))
                session.flush()
                inserted += 1

                bp = session.query(BanditParam).filter_by(arm_id=qid).first()
                if not bp:
                    session.add(BanditParam(arm_id=qid, matrix_a=eye_8x8, vector_b=zero_8x1))
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


def sync_leetcode_activity(
    username_or_id: Any,
    profile_data: Optional[Dict[str, Any]] = None,
    session: Session = None,
) -> Dict[str, Any]:
    if session is None:
        raise ValueError("A database session is required to resolve the application user.")

    user = None
    if isinstance(username_or_id, uuid.UUID):
        user = session.query(User).filter_by(id=username_or_id).first()
    elif isinstance(username_or_id, str):
        try:
            user_id = uuid.UUID(username_or_id)
            user = session.query(User).filter_by(id=user_id).first()
        except ValueError:
            user = session.query(User).filter_by(leetcode_handle=username_or_id).first()

    if user is None:
        return {"status": "error", "message": "Application user not found. Please log in first."}

    username = user.leetcode_handle
    if not username:
        return {"status": "error", "message": "No LeetCode handle is connected to this account.", "user_id": str(user.id)}

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

    solved_counts = {stat.get("difficulty"): stat.get("count", 0) for stat in accepted_submissions}
    contest = profile_data.get("userContestRanking") or {}

    tag_counts = matched_user.get("tagProblemCounts") or {}
    topic_solved = {}

    for bucket in ("fundamental", "intermediate", "advanced"):
        for entry in tag_counts.get(bucket, []):
            topic_name = TAG_TO_TOPIC.get(entry.get("tagSlug"))
            if topic_name:
                topic_solved[topic_name] = topic_solved.get(topic_name, 0) + entry.get("problemsSolved", 0)

    # 1. Update user profile metrics directly
    user.total_solved = int(solved_counts.get("All", 0))
    user.easy_solved = int(solved_counts.get("Easy", 0))
    user.medium_solved = int(solved_counts.get("Medium", 0))
    user.hard_solved = int(solved_counts.get("Hard", 0))

    if profile_info.get("userAvatar"):
        user.user_avatar = str(profile_info["userAvatar"])

    if contest.get("rating") is not None:
        user.contest_rating = int(round(contest["rating"]))

    if profile_info.get("ranking") is not None:
        user.global_ranking = int(profile_info["ranking"])

    # 2. Update topic skills in UserSkill table dynamically
    for topic_name, count in topic_solved.items():
        topic_obj = session.query(Topic).filter(Topic.name.ilike(topic_name)).first()
        if topic_obj:
            user_skill = session.query(UserSkill).filter_by(user_id=user.id, topic_id=topic_obj.id).first()
            # Normalize score scaled between 0.35 and 0.95 based on solved count
            new_score = min(0.95, max(0.35, 0.35 + (count * 0.02)))
            if user_skill:
                user_skill.skill_score = new_score
            else:
                session.add(UserSkill(user_id=user.id, topic_id=topic_obj.id, skill_score=new_score))

    session.commit()

    return {
        "status": "success",
        "user_id": str(user.id),
        "leetcode_handle": username,
        "username": user.username,
        "user_avatar": user.user_avatar,
        "total_solved": user.total_solved,
        "easy_solved": user.easy_solved,
        "medium_solved": user.medium_solved,
        "hard_solved": user.hard_solved,
        "contest_rating": user.contest_rating,
        "global_ranking": user.global_ranking,
        "topics_solved": topic_solved,
        "recent_submissions": profile_data.get("recentSubmissionList") or [],
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }