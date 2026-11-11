import uuid
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from backend.db.models import User, Problem, Topic, UserSkill, Attempt

COMPANY_REQUIREMENTS = {
    "Google": {
        "key_topics": ["DP", "Graphs", "Trees", "Arrays", "BinarySearch"],
        "target_solved": 350,
        "target_medium_hard": 250,
        "description": "High focus on complex Graph algorithms, Dynamic Programming optimizations, and Tree recursion.",
    },
    "Microsoft": {
        "key_topics": ["Trees", "LinkedList", "Strings", "Arrays", "Graphs"],
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
        "key_topics": ["BinarySearch", "Arrays", "Strings", "Trees", "DP"],
        "target_solved": 300,
        "target_medium_hard": 220,
        "description": "Emphasis on speed execution accuracy, Two Pointers, Monotonic Stacks, and Tree paths.",
    },
    "Adobe": {
        "key_topics": ["Arrays", "Strings", "DP", "Math", "Stack"],
        "target_solved": 200,
        "target_medium_hard": 120,
        "description": "Focus on String manipulations, Stack parsing, Math logic, and Array subarray techniques.",
    },
}

def generate_personalized_roadmap(user: User, session: Session) -> Dict[str, Any]:
    """
    Generates personalized roadmap per Section E of SRS spec:
    Current Position -> Skill Gap -> Recommended Topics -> Recommended Questions -> Target Companies
    """
    skills = (
        session.query(Topic.name, UserSkill.skill_score)
        .join(UserSkill, Topic.id == UserSkill.topic_id)
        .filter(UserSkill.user_id == user.id)
        .all()
    )
    skill_map = {name: score for name, score in skills}

    # Weak topics (< 60% mastery)
    weak_topics = [t for t, s in skill_map.items() if s < 0.60]
    if not weak_topics:
        weak_topics = sorted(skill_map.keys(), key=lambda t: skill_map[t])[:3]

    # Strong topics (>= 75% mastery)
    strong_topics = [t for t, s in skill_map.items() if s >= 0.75]

    # 1. Current Position
    current_position = {
        "total_solved": user.total_solved or 0,
        "easy_solved": user.easy_solved or 0,
        "medium_solved": user.medium_solved or 0,
        "hard_solved": user.hard_solved or 0,
        "contest_rating": user.contest_rating or 1500,
        "strongest_domains": strong_topics[:3],
    }

    # 2. Skill Gap Analysis
    skill_gap = []
    for topic, score in skill_map.items():
        if score < 0.70:
            skill_gap.append({
                "topic": topic,
                "current_mastery": round(score, 2),
                "target_mastery": 0.85,
                "gap_score": round(0.85 - score, 2),
            })
    skill_gap.sort(key=lambda x: x["gap_score"], reverse=True)

    # 3. Recommended Focus Topics
    recommended_topics = [item["topic"] for item in skill_gap[:4]]

    # 4. Target Company Readiness
    company_readiness = []
    total_solved = user.total_solved or 0
    medium_hard_solved = (user.medium_solved or 0) + (user.hard_solved or 0)

    for company, req in COMPANY_REQUIREMENTS.items():
        solves_pct = min(100, int((total_solved / req["target_solved"]) * 100))
        med_hard_pct = min(100, int((medium_hard_solved / req["target_medium_hard"]) * 100))
        
        # Topic alignment
        aligned_skills = [skill_map.get(t, 0.35) for t in req["key_topics"]]
        avg_topic_mastery = sum(aligned_skills) / len(aligned_skills)
        readiness_pct = int((0.4 * solves_pct) + (0.4 * med_hard_pct) + (0.2 * avg_topic_mastery * 100))
        readiness_pct = min(98, max(25, readiness_pct))

        company_readiness.append({
            "company": company,
            "readiness_percentage": readiness_pct,
            "key_topics": req["key_topics"],
            "description": req["description"],
            "unmet_prerequisites": [t for t in req["key_topics"] if skill_map.get(t, 0.35) < 0.65],
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
