import uuid
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import not_

from backend.db.models import (
    User, Problem, Topic, ProblemTopic, UserSkill, Attempt, BanditParam, UserSolvedProblem, DifficultyLevel
)
from app.ml.context_engine import construct_context_vector, compute_decay_factor
from app.ml.bandit import LinUCB
from backend.services.attempt_service import get_consecutive_failures


def get_user_context_vector(user_or_id: Union[User, uuid.UUID, str], session: Session) -> Dict[str, Any]:
    """
    Constructs user's 8-dimensional context vector x_{u,t} dynamically from PostgreSQL.
    Features: [ acc_20, S_graph, S_dp, S_tree, S_greedy, contest_rating, Z_speed, decay_factor ]^T
    """
    if isinstance(user_or_id, User):
        user = user_or_id
    elif isinstance(user_or_id, uuid.UUID):
        user = session.query(User).filter_by(id=user_or_id).first()
    else:
        try:
            uid = uuid.UUID(str(user_or_id))
            user = session.query(User).filter_by(id=uid).first()
        except Exception:
            user = session.query(User).filter_by(leetcode_handle=str(user_or_id)).first()

    if not user:
        raise ValueError(f"User '{user_or_id}' not found.")

    user_id = user.id

    # 1. Query user topic skills dynamically
    skills = (
        session.query(Topic.name, UserSkill.skill_score)
        .join(UserSkill, Topic.id == UserSkill.topic_id)
        .filter(UserSkill.user_id == user_id)
        .all()
    )
    skill_map = {name.lower(): float(score) for name, score in skills}

    def compute_category_skill(keywords: List[str], default_score: float = 0.35) -> float:
        matching_scores = [
            score for topic_name, score in skill_map.items()
            if any(kw in topic_name for kw in keywords)
        ]
        return float(sum(matching_scores) / len(matching_scores)) if matching_scores else default_score

    s_graph = compute_category_skill(["graph", "network", "bfs", "dfs"])
    s_dp = compute_category_skill(["dp", "dynamic", "memoization"])
    s_tree = compute_category_skill(["tree", "trie"])
    s_greedy = compute_category_skill(["greedy", "interval"])

    # 2. Compute accuracy & speed over last 20 attempts from DB logs
    recent_attempts = (
        session.query(Attempt)
        .filter_by(user_id=user_id)
        .order_by(Attempt.created_at.desc())
        .limit(20)
        .all()
    )

    if recent_attempts:
        acc_20 = float(sum(1 for a in recent_attempts if a.success) / len(recent_attempts))
        speed_ratios = []
        for a in recent_attempts:
            p = session.query(Problem).filter_by(frontend_question_id=a.frontend_question_id).first()
            exp_sec = (p.expected_time_minutes if p else 30) * 60
            ratio = max(0.0, min(1.0, 1.0 - (a.time_spent_seconds / exp_sec)))
            speed_ratios.append(ratio)
        z_speed = float(sum(speed_ratios) / len(speed_ratios))
        last_practiced_at = recent_attempts[0].created_at
    else:
        if user.total_solved and user.total_solved > 0:
            acc_20 = float(min(0.98, max(0.50, ((user.easy_solved or 0) * 0.9 + (user.medium_solved or 0) * 0.8 + (user.hard_solved or 0) * 0.7) / float(user.total_solved))))
        else:
            acc_20 = 0.50
        z_speed = 0.50
        last_practiced_at = None

    decay_factor = float(compute_decay_factor(last_practiced_at))
    contest_rating = float(user.contest_rating or 1500)

    x_ut = construct_context_vector(
        acc_20=acc_20,
        s_graph=s_graph,
        s_dp=s_dp,
        s_tree=s_tree,
        s_greedy=s_greedy,
        contest_rating=contest_rating,
        z_speed=z_speed,
        decay_factor=decay_factor,
    )

    # Cast context vector elements to explicit floats for JSON serializability
    if hasattr(x_ut, "tolist"):
        x_ut_list = [float(val) for val in x_ut.flatten().tolist()]
    else:
        x_ut_list = [float(val) for val in x_ut]

    return {
        "context_vector": x_ut_list,
        "acc_20": round(float(acc_20), 3),
        "s_graph": round(float(s_graph), 3),
        "s_dp": round(float(s_dp), 3),
        "s_tree": round(float(s_tree), 3),
        "s_greedy": round(float(s_greedy), 3),
        "contest_rating": round(float(contest_rating), 1),
        "z_speed": round(float(z_speed), 3),
        "decay_factor": round(float(decay_factor), 3),
        "skill_map": skill_map,
    }


def recommend_next_problem(
    user_id: Union[User, uuid.UUID, str],
    session: Session,
    alpha: float = 0.25,
    live_solved_ids: Optional[set] = None,
) -> Dict[str, Any]:
    """
    Evaluates user context vector and returns optimal question recommendation via LinUCB.
    Casts all outputs explicitly to native Python primitive types.
    """
    if isinstance(user_id, User):
        user = user_id
    elif isinstance(user_id, uuid.UUID):
        user = session.query(User).filter_by(id=user_id).first()
    else:
        try:
            uid = uuid.UUID(str(user_id))
            user = session.query(User).filter_by(id=uid).first()
        except Exception:
            user = session.query(User).filter_by(leetcode_handle=str(user_id)).first()

    if not user:
        raise ValueError(f"User '{user_id}' not found.")

    context_info = get_user_context_vector(user, session)
    x_ut = np.array(context_info["context_vector"], dtype=np.float64).reshape(-1, 1)
    user_skill_map = context_info.get("skill_map", {})

    # 1. Fetch solved problem IDs dynamically
    solved_qids = set(
        int(qid) for (qid,) in session.query(UserSolvedProblem.frontend_question_id).filter_by(user_id=user.id).all()
    )
    solved_qids.update(
        int(qid) for (qid,) in session.query(Attempt.frontend_question_id).filter_by(user_id=user.id, success=True).all()
    )
    if live_solved_ids:
        solved_qids.update(int(qid) for qid in live_solved_ids)

    # 2. Check for recent failure streaks
    latest_attempt = (
        session.query(Attempt)
        .filter_by(user_id=user.id)
        .order_by(Attempt.created_at.desc(), Attempt.id.desc())
        .first()
    )

    consecutive_failures = 0
    struggling_qid = None
    if latest_attempt and not latest_attempt.success:
        consecutive_failures = int(get_consecutive_failures(user.id, latest_attempt.frontend_question_id, session))
        if consecutive_failures >= 3:
            struggling_qid = int(latest_attempt.frontend_question_id)

    # 3. Dynamic candidate pool query from PostgreSQL
    candidate_query = session.query(Problem)
    if solved_qids:
        candidate_query = candidate_query.filter(not_(Problem.frontend_question_id.in_(solved_qids)))

    if struggling_qid:
        struggling_prob = session.query(Problem).filter_by(frontend_question_id=struggling_qid).first()
        if struggling_prob and struggling_prob.difficulty != DifficultyLevel.EASY:
            target_topic_ids = [
                pt.topic_id for pt in session.query(ProblemTopic).filter_by(frontend_question_id=struggling_qid).all()
            ]
            easier_diff = DifficultyLevel.EASY if struggling_prob.difficulty == DifficultyLevel.MEDIUM else DifficultyLevel.MEDIUM

            fallback_candidates = (
                candidate_query.join(ProblemTopic)
                .filter(ProblemTopic.topic_id.in_(target_topic_ids), Problem.difficulty == easier_diff)
                .all()
            )
            unsolved_problems = fallback_candidates if fallback_candidates else candidate_query.all()
        else:
            unsolved_problems = candidate_query.all()
    else:
        unsolved_problems = candidate_query.all()

    if not unsolved_problems:
        try:
            from backend.services.leetcode_sync import sync_leetcode_catalog
            sync_leetcode_catalog(session)
            unsolved_problems = candidate_query.all()
        except Exception as e:
            print(f"Catalog sync on demand failed: {e}")

    if not unsolved_problems:
        return {
            "status": "no_unsolved_candidates",
            "message": "No unsolved problems currently available in catalog.",
            "candidate_pool_size": 0,
        }

    candidate_arms = [int(p.frontend_question_id) for p in unsolved_problems]

    # 4. Query LinUCB bandit parameters dynamically from DB
    params_rows = session.query(BanditParam).filter(BanditParam.arm_id.in_(candidate_arms)).all()
    bandit_params = {int(bp.arm_id): {"matrix_a": bp.matrix_a, "vector_b": bp.vector_b} for bp in params_rows}

    adjusted_alpha = float(max(0.05, alpha - (consecutive_failures * 0.05)))

    # 5. Execute LinUCB Arm Selection
    linucb = LinUCB(d=8, alpha=adjusted_alpha)
    best_arm_id, best_score, scores = linucb.select_arm(x_ut, candidate_arms, bandit_params)
    best_arm_id = int(best_arm_id)

    # Fetch winning problem and associated topics dynamically
    best_problem = next(p for p in unsolved_problems if int(p.frontend_question_id) == best_arm_id)
    topic_names = [
        str(t_name) for (t_name,) in session.query(Topic.name)
        .join(ProblemTopic, Topic.id == ProblemTopic.topic_id)
        .filter(ProblemTopic.frontend_question_id == best_arm_id).all()
    ]

    diff_str = best_problem.difficulty.value if hasattr(best_problem.difficulty, "value") else str(best_problem.difficulty)

    primary_topic = topic_names[0] if topic_names else "DSA"
    topic_skill_score = float(user_skill_map.get(primary_topic.lower(), 0.35))

    rationale = (
        f"Selected based on your current dynamic skill rating of {topic_skill_score:.0%} in {primary_topic} "
        f"and your target learning boundary ({diff_str})."
    )

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
    top_5_rankings = []
    for qid, score in ranked:
        p = session.query(Problem).filter_by(frontend_question_id=int(qid)).first()
        top_5_rankings.append({
            "arm_id": int(qid),
            "title": str(p.title) if p else f"Problem {qid}",
            "ucb_score": round(float(score), 4),
        })

    # Estimate expected theta reward and exploration bonus breakdown for UI display
    theta_reward = float(best_score * 0.75)
    exploration_bonus = float(best_score * 0.25)

    return {
        "problem_id": int(best_problem.frontend_question_id),
        "title": str(best_problem.title),
        "title_slug": str(best_problem.title_slug),
        "difficulty": str(diff_str),
        "expected_time_minutes": int(best_problem.expected_time_minutes or 20),
        "topics": topic_names,
        "arm_id": int(best_arm_id),
        "theta_reward": round(theta_reward, 4),
        "exploration_bonus": round(exploration_bonus, 4),
        "ucb_score": round(float(best_score), 4),
        "candidate_pool_size": int(len(candidate_arms)),
        "consecutive_failures": int(consecutive_failures),
        "why_chosen": str(rationale),
        "top_5_rankings": top_5_rankings,
        "user_context": context_info,
    }