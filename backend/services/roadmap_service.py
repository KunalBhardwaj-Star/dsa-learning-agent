import uuid
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.db.models import (
    User,
    Problem,
    Topic,
    UserSkill,
    UserSolvedProblem,
    Attempt,
    ProblemTopic,
    DifficultyLevel,
)

# Standard target company requirements schema mapped against database topics
COMPANY_REQUIREMENTS = {
    "Google": {
        "key_topics": ["Dynamic Programming", "Graphs", "Trees", "Arrays", "Binary Search"],
        "target_solved": 350,
        "target_medium_hard": 250,
        "description": "High focus on complex Graph algorithms, Dynamic Programming optimizations, and Tree recursion.",
    },
    "Microsoft": {
        "key_topics": ["Trees", "Linked List", "Strings", "Arrays", "Graphs"],
        "target_solved": 250,
        "target_medium_hard": 150,
        "description": "Heavy emphasis on Tree traversals, Linked Lists, HashMap design, and System fundamentals.",
    },
    "Amazon": {
        "key_topics": ["Heap", "Graphs", "Trees", "Hashing", "Greedy"],
        "target_solved": 300,
        "target_medium_hard": 200,
        "description": "Focus on Priority Queues, BFS/DFS Grid searches, Object-Oriented Design, and Scalability.",
    },
    "Meta": {
        "key_topics": ["Binary Search", "Arrays", "Strings", "Trees", "Dynamic Programming"],
        "target_solved": 300,
        "target_medium_hard": 220,
        "description": "Emphasis on speed execution accuracy, Two Pointers, Monotonic Stacks, and Tree paths.",
    },
    "Adobe": {
        "key_topics": ["Arrays", "Strings", "Dynamic Programming", "Math", "Stack"],
        "target_solved": 200,
        "target_medium_hard": 120,
        "description": "Focus on String manipulations, Stack parsing, Math logic, and Array subarray techniques.",
    },
}


def generate_personalized_roadmap(user: User, session: Session) -> Dict[str, Any]:
    """
    Generates a personalized DSA roadmap dynamically from PostgreSQL models.
    Calculates current position, skill gap analysis, topic recommendations,
    and target company readiness percentages based on actual DB records.
    """
    if session is None:
        raise ValueError("Database session is required to generate personalized roadmap.")

    # 1. Fetch user topic skills dynamically from PostgreSQL
    skills = (
        session.query(Topic.name, UserSkill.skill_score)
        .join(UserSkill, Topic.id == UserSkill.topic_id)
        .filter(UserSkill.user_id == user.id)
        .all()
    )
    skill_map = {name.lower(): score for name, score in skills}

    # 2. Compute dynamic solved counts from database tables
    solved_qids = set(
        qid for (qid,) in session.query(UserSolvedProblem.frontend_question_id).filter_by(user_id=user.id).all()
    )
    solved_qids.update(
        qid for (qid,) in session.query(Attempt.frontend_question_id).filter_by(user_id=user.id, success=True).all()
    )

    if solved_qids:
        solved_problems = session.query(Problem).filter(Problem.frontend_question_id.in_(solved_qids)).all()
        total_solved = len(solved_problems)
        easy_solved = sum(1 for p in solved_problems if p.difficulty == DifficultyLevel.EASY)
        medium_solved = sum(1 for p in solved_problems if p.difficulty == DifficultyLevel.MEDIUM)
        hard_solved = sum(1 for p in solved_problems if p.difficulty == DifficultyLevel.HARD)
    else:
        total_solved = user.total_solved or 0
        easy_solved = user.easy_solved or 0
        medium_solved = user.medium_solved or 0
        hard_solved = user.hard_solved or 0

    medium_hard_solved = medium_solved + hard_solved

    # 3. Dynamic Current Position
    strong_topics = [t_name for t_name, score in skill_map.items() if score >= 0.75]
    current_position = {
        "total_solved": total_solved,
        "easy_solved": easy_solved,
        "medium_solved": medium_solved,
        "hard_solved": hard_solved,
        "contest_rating": user.contest_rating or 1500,
        "strongest_domains": [t.title() for t in strong_topics[:3]],
    }

    # 4. Dynamic Skill Gap Analysis
    skill_gap = []
    for topic_name, score in skill_map.items():
        if score < 0.70:
            skill_gap.append({
                "topic": topic_name.title(),
                "current_mastery": round(score, 2),
                "target_mastery": 0.85,
                "gap_score": round(0.85 - score, 2),
            })

    # Sort gaps by largest gap score first
    skill_gap.sort(key=lambda x: x["gap_score"], reverse=True)

    # 5. Dynamic Topic Recommendations
    if skill_gap:
        recommended_topics = [item["topic"] for item in skill_gap[:4]]
    else:
        # Fallback to lowest mastery topics in database
        sorted_skills = sorted(skill_map.items(), key=lambda x: x[1])
        recommended_topics = [t[0].title() for t in sorted_skills[:4]]

    # 6. Dynamic Target Company Readiness Calculation
    company_readiness = []
    for company, req in COMPANY_REQUIREMENTS.items():
        solves_pct = min(100, int((total_solved / req["target_solved"]) * 100))
        med_hard_pct = min(100, int((medium_hard_solved / req["target_medium_hard"]) * 100))

        # Evaluate actual topic mastery from skill_map dynamically
        aligned_scores = [
            skill_map.get(t.lower(), 0.35) for t in req["key_topics"]
        ]
        avg_topic_mastery = sum(aligned_scores) / len(aligned_scores) if aligned_scores else 0.35

        # Weighted composite readiness calculation
        readiness_pct = int((0.4 * solves_pct) + (0.4 * med_hard_pct) + (0.2 * avg_topic_mastery * 100))
        readiness_pct = min(98, max(25, readiness_pct))

        unmet_prereqs = [
            t for t in req["key_topics"] if skill_map.get(t.lower(), 0.35) < 0.65
        ]

        company_readiness.append({
            "company": company,
            "readiness_percentage": readiness_pct,
            "key_topics": req["key_topics"],
            "description": req["description"],
            "unmet_prerequisites": unmet_prereqs,
        })

    company_readiness.sort(key=lambda x: x["readiness_percentage"], reverse=True)

    return {
        "user_id": str(user.id),
        "leetcode_handle": user.leetcode_handle,
        "current_position": current_position,
        "skill_gap": skill_gap[:6],
        "recommended_topics": recommended_topics,
        "target_companies": company_readiness,
    }