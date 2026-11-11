from backend.services import auth_service
from requests import session
import uuid
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union
from sqlalchemy.orm import Session
from backend.services.leetcode_sync import sync_leetcode_activity

from backend.db.models import User, Problem, Topic, ProblemTopic, UserSkill, Attempt, BanditParam, UserSolvedProblem , DifficultyLevel
from app.ml.context_engine import construct_context_vector, compute_decay_factor
from app.ml.bandit import LinUCB


def get_user_context_vector(user_or_id: Union[User, uuid.UUID, str], session: Session) -> Dict[str, Any]:
    """
    Constructs user's 8-dimensional context vector x_{u,t} per SRS Section 3.1:
      x_{u,t} = [ acc_20, S_graph, S_dp, S_tree, S_greedy, contest_rating, Z_speed, decay_factor ]^T
    Accepts User object, UUID, or leetcode_handle string.
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

    # 1. Topic skill scores
    skills = session.query(UserSkill, Topic).join(Topic, UserSkill.topic_id == Topic.id).filter(UserSkill.user_id == user_id).all()
    skill_map = {topic.name: us.skill_score for us, topic in skills}

    s_graph = skill_map.get("Graphs", 0.35)
    s_dp = skill_map.get("DP", 0.35)
    s_tree = skill_map.get("Trees", 0.35)
    s_greedy = skill_map.get("Greedy", 0.35)

    # 2. acc_20 (accuracy over last 20 attempts in database)
    recent_attempts = (
        session.query(Attempt)
        .filter_by(user_id=user_id)
        .order_by(Attempt.created_at.desc())
        .limit(20)
        .all()
    )

    if recent_attempts:
        acc_20 = sum(1 for a in recent_attempts if a.success) / len(recent_attempts)
        speed_ratios = []
        for a in recent_attempts:
            p = session.query(Problem).filter_by(frontend_question_id=a.frontend_question_id).first()
            exp_sec = (p.expected_time_minutes if p else 30) * 60
            ratio = max(0.0, min(1.0, 1.0 - (a.time_spent_seconds / exp_sec)))
            speed_ratios.append(ratio)
        z_speed = sum(speed_ratios) / len(speed_ratios)
        last_practiced_at = recent_attempts[0].created_at
    else:
        # Dynamic calculation from user's overall solved statistics
        if user.total_solved and user.total_solved > 0:
            acc_20 = min(0.98, max(0.50, ((user.easy_solved or 0) * 0.9 + (user.medium_solved or 0) * 0.8 + (user.hard_solved or 0) * 0.7) / float(user.total_solved)))
        else:
            acc_20 = 0.50
        z_speed = 0.50
        last_practiced_at = None

    # 3. decay_factor
    decay_factor = compute_decay_factor(last_practiced_at)

    # 4. contest_rating
    contest_rating = float(user.contest_rating or 1521)

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

    return {
        "context_vector": x_ut,
        "acc_20": round(acc_20, 3),
        "s_graph": round(s_graph, 3),
        "s_dp": round(s_dp, 3),
        "s_tree": round(s_tree, 3),
        "s_greedy": round(s_greedy, 3),
        "contest_rating": contest_rating,
        "z_speed": round(z_speed, 3),
        "decay_factor": round(decay_factor, 3),
    }


def recommend_next_problem(
    user_id: Union[User, uuid.UUID, str],
    session: Session,
    alpha: float = 0.25,
    live_solved_ids: Optional[set] = None,
) -> Dict[str, Any]:
    """
    Evaluates user context vector and returns optimal question recommendation via LinUCB.
    Provides complete proof breakdown of LinUCB score, candidate pool size, theta reward, and exploration bonus.
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

    # Fetch current LeetCode statistics for this authenticated user.
    live_data = sync_leetcode_activity(
        username_or_id=user.id,
        session=session,
    )

    if live_data.get("status") != "success":
        raise ValueError(
            live_data.get("message", "Unable to fetch live LeetCode data.")
        )

    # Use live contest rating and solved counts for the context vector.
    context_info = get_user_context_vector(user, session)

    live_rating = live_data.get("contest_rating")

    if live_rating is not None:
        context_info["contest_rating"] = float(live_rating)

    x_ut = construct_context_vector(
        acc_20=context_info["acc_20"],
        s_graph=context_info["s_graph"],
        s_dp=context_info["s_dp"],
        s_tree=context_info["s_tree"],
        s_greedy=context_info["s_greedy"],
        contest_rating=context_info["contest_rating"],
        z_speed=context_info["z_speed"],
        decay_factor=context_info["decay_factor"],
    )

    context_info["context_vector"] = x_ut

    # Fetch candidate problems
    problems = session.query(Problem).all()
    if not problems:
        try:
            from backend.db.init_db import init_db
            init_db()
            problems = session.query(Problem).all()
        except Exception as e:
            print(f"Auto-seeding catalog on empty database failed: {e}")

    if not problems:
        raise ValueError("No problems available in catalog.")

    
    # 1. Fetch solved problem IDs for the user.
    # Prefer live IDs supplied by the Chrome extension.
    if live_solved_ids is not None:
        solved_ids = {int(qid) for qid in live_solved_ids}
    else:
        solved_rows = (
            session.query(UserSolvedProblem.frontend_question_id)
            .filter_by(user_id=user.id)
            .all()
        )
        solved_ids = {row[0] for row in solved_rows}

        successful_attempts = (
            session.query(Attempt.frontend_question_id)
            .filter_by(user_id=user.id, success=True)
            .all()
        )
        solved_ids.update(row[0] for row in successful_attempts)

    # 2. Exclude solved problems for BOTH live and database-based requests.
    unsolved_problems = [
        p for p in problems
        if p.frontend_question_id not in solved_ids
    ]

        # Identify the most recently attempted question.
    latest_attempt = (
        session.query(Attempt)
        .filter_by(user_id=user.id)
        .order_by(Attempt.created_at.desc(), Attempt.id.desc())
        .first()
    )

    struggling_question_id = None
    consecutive_failures = 0

    if latest_attempt and not latest_attempt.success:
        from backend.services.attempt_service import get_consecutive_failures

        consecutive_failures = get_consecutive_failures(
            user_id=user.id,
            frontend_question_id=latest_attempt.frontend_question_id,
            session=session,
        )

        if consecutive_failures >= 3:
            struggling_question_id = latest_attempt.frontend_question_id

    if not unsolved_problems:
        return {
            "status": "no_unsolved_candidates",
            "message": (
                "No unsolved problems are currently available in the catalog. "
                "Please sync/import more LeetCode problems."
            ),
            "candidate_pool_size": 0,
            "solved_count_in_catalog": len(
                solved_ids & {p.frontend_question_id for p in problems}
            ),
            "total_catalog_problems": len(problems),
        }

        # After 3 consecutive failures, prioritize easier problems
    # sharing at least one topic with the struggling question.
    adaptive_fallback_used = False

    if struggling_question_id is not None:
        struggling_difficulty = (
            session.query(Problem.difficulty)
            .filter_by(frontend_question_id=struggling_question_id)
            .scalar()
        )

        struggling_topic_ids = {
            row[0]
            for row in (
                session.query(ProblemTopic.topic_id)
                .filter_by(frontend_question_id=struggling_question_id)
                .all()
            )
        }

        difficulty_rank = {
            DifficultyLevel.EASY: 1,
            DifficultyLevel.MEDIUM: 2,
            DifficultyLevel.HARD: 3,
        }

        current_rank = difficulty_rank.get(struggling_difficulty, 0)

        easier_related = []

        if struggling_topic_ids and current_rank > 1:
            for candidate in unsolved_problems:
                candidate_rank = difficulty_rank.get(candidate.difficulty, 0)

                if candidate_rank >= current_rank:
                    continue

                candidate_topic_ids = {
                    row[0]
                    for row in (
                        session.query(ProblemTopic.topic_id)
                        .filter_by(
                            frontend_question_id=candidate.frontend_question_id
                        )
                        .all()
                    )
                }

                if struggling_topic_ids & candidate_topic_ids:
                    easier_related.append(candidate)

        if easier_related:
            unsolved_problems = easier_related
            adaptive_fallback_used = True

            print(
                f"[ADAPTIVE FALLBACK] User: {user.leetcode_handle} | "
                f"Failed question: {struggling_question_id} | "
                f"Consecutive failures: {consecutive_failures} | "
                f"Easier related candidates: {len(easier_related)}"
            )

    candidate_arms = [p.frontend_question_id for p in unsolved_problems]
    candidate_pool_size = len(candidate_arms)

    # Fetch bandit parameters from DB
    params_rows = session.query(BanditParam).all()
    bandit_params = {}
    for bp in params_rows:
        bandit_params[bp.arm_id] = {
            "matrix_a": bp.matrix_a,
            "vector_b": bp.vector_b,
        }

    # LinUCB selection on UNSOLVED candidate pool ONLY
    linucb = LinUCB(d=8, alpha=alpha)
    best_arm_id, best_score, scores = linucb.select_arm(x_ut, candidate_arms, bandit_params)

    # Safety guard: never return a problem present in the solved-ID set.
    if best_arm_id in solved_ids:
        raise RuntimeError(
            f"Safety violation: LinUCB selected solved problem ID {best_arm_id}."
        )

    if best_arm_id not in set(candidate_arms):
        raise RuntimeError(
            f"Safety violation: selected problem ID {best_arm_id} "
            "is not in the eligible candidate pool."
        )

    # Detailed LinUCB component breakdown for chosen arm
    param = bandit_params.get(best_arm_id, {})
    A_a = np.asarray(param.get("matrix_a", np.eye(8)), dtype=np.float64)
    b_a = np.asarray(param.get("vector_b", np.zeros((8,1))), dtype=np.float64).reshape((8, 1))
    A_inv = np.linalg.inv(A_a + np.eye(8)*1e-6)
    theta_a = A_inv @ b_a
    x_u = x_ut.reshape((8, 1))

    theta_reward = float((theta_a.T @ x_u).item())
    var_term = float((x_u.T @ A_inv @ x_u).item())
    exploration_bonus = alpha * np.sqrt(max(0.0, var_term))

    # Fetch details for chosen problem
    best_problem = session.query(Problem).filter_by(frontend_question_id=best_arm_id).first()
    prob_topics = (
        session.query(Topic.name)
        .join(ProblemTopic, Topic.id == ProblemTopic.topic_id)
        .filter(ProblemTopic.frontend_question_id == best_arm_id)
        .all()
    )
    topic_names = [t[0] for t in prob_topics]

    # Structured Backend Audit Logging
    total_problems = len(problems)
    solved_in_catalog = len(solved_ids & {p.frontend_question_id for p in problems})
    print(f"[RECOMMENDATION AUDIT] User: {user.leetcode_handle} | Total problems: {total_problems} | Solved in catalog: {solved_in_catalog} | Unsolved candidates: {candidate_pool_size} | Selected recommendation: LC #{best_arm_id} ({best_problem.title})")

    # Human-readable Rationale generation
    primary_topic = topic_names[0] if topic_names else "DSA"
    topic_skill = 0.35
    if primary_topic == "Graphs":
        topic_skill = context_info["s_graph"]
    elif primary_topic == "DP":
        topic_skill = context_info["s_dp"]
    elif primary_topic == "Trees":
        topic_skill = context_info["s_tree"]
    elif primary_topic == "Greedy":
        topic_skill = context_info["s_greedy"]

    rationale = (
        f"You have not solved this problem. {primary_topic} (Skill: {topic_skill:.0%}) is currently one of your targeted areas, "
        f"and this {best_problem.difficulty.value} problem matches your difficulty progression."
    )

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
    top_5_rankings = []
    for qid, score in ranked:
        p = session.query(Problem).filter_by(frontend_question_id=qid).first()
        top_5_rankings.append({
            "arm_id": qid,
            "title": p.title if p else f"Problem {qid}",
            "ucb_score": round(score, 4)
        })

    return {
        "problem_id": best_problem.frontend_question_id,
        "title": best_problem.title,
        "title_slug": best_problem.title_slug,
        "difficulty": best_problem.difficulty.value,
        "expected_time_minutes": best_problem.expected_time_minutes,
        "topics": topic_names,
        "is_solved": False,
        "arm_id": best_arm_id,
        "theta_reward": round(theta_reward, 4),
        "exploration_bonus": round(exploration_bonus, 4),
        "ucb_score": round(best_score, 4),
        "candidate_pool_size": candidate_pool_size,
        "why_chosen": rationale,
        "top_5_rankings": top_5_rankings,
        "user_context": {
            "acc_20": context_info["acc_20"],
            "s_graph": context_info["s_graph"],
            "s_dp": context_info["s_dp"],
            "s_tree": context_info["s_tree"],
            "s_greedy": context_info["s_greedy"],
            "contest_rating": context_info["contest_rating"],
            "z_speed": context_info["z_speed"],
            "decay_factor": context_info["decay_factor"],
            "raw_vector": x_ut.tolist(),
        },
    }