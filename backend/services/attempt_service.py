import uuid
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union
from sqlalchemy.orm import Session

from backend.db.models import User, Problem, Topic, ProblemTopic, UserSkill, Attempt, BanditParam, UserSolvedProblem
from backend.services.recommendation_service import get_user_context_vector
from app.ml.reward_engine import compute_composite_reward
from app.ml.bandit import LinUCB


def get_consecutive_failures(
    user_id: uuid.UUID,
    frontend_question_id: int,
    session: Session,
) -> int:
    """Count consecutive failed attempts, starting from the latest attempt."""
    attempts = (
        session.query(Attempt.success)
        .filter_by(
            user_id=user_id,
            frontend_question_id=frontend_question_id,
        )
        .order_by(Attempt.created_at.desc(), Attempt.id.desc())
        .all()
    )

    failures = 0

    for (success,) in attempts:
        if success:
            break
        failures += 1

    return failures


def record_problem_attempt(
    user_id: Union[User, uuid.UUID, str],
    frontend_question_id: int,
    time_spent_seconds: int,
    success: bool,
    submission_count: int = 1,
    hints_used: int = 0,
    session: Session = None,
) -> Dict[str, Any]:
    """
    Logs problem attempt, computes composite reward R_total, updates user skills & LinUCB parameters.
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
        user = session.query(User).first()

    if not user:
        raise ValueError(f"User '{user_id}' not found.")

    problem = session.query(Problem).filter_by(frontend_question_id=frontend_question_id).first()
    if not problem:
        raise ValueError(f"Problem with frontend_question_id={frontend_question_id} not found.")

    # 1. Compute user context vector BEFORE update
    context_info = get_user_context_vector(user, session)
    x_ut = context_info["context_vector"]

    # 2. Check if repeat attempt
    prev_attempt = (
        session.query(Attempt)
        .filter_by(user_id=user.id, frontend_question_id=frontend_question_id)
        .first()
    )
    is_repeat = prev_attempt is not None

    # 3. Compute Composite Learning Gain Reward
    reward_dict = compute_composite_reward(
        success=success,
        time_spent_seconds=time_spent_seconds,
        expected_time_minutes=problem.expected_time_minutes,
        submission_count=submission_count,
        hints_used=hints_used,
        is_repeat=is_repeat,
    )
    r_total = reward_dict["r_total"]

    # 4. Log attempt record in PostgreSQL
    attempt = Attempt(
        user_id=user.id,
        frontend_question_id=frontend_question_id,
        time_spent_seconds=time_spent_seconds,
        success=success,
        submission_count=submission_count,
        hints_used=hints_used,
        computed_reward=r_total,
    )
    session.add(attempt)

    if success:
        existing_sp = (
            session.query(UserSolvedProblem)
            .filter_by(user_id=user.id, frontend_question_id=frontend_question_id)
            .first()
        )
        if not existing_sp:
            sp = UserSolvedProblem(
                user_id=user.id,
                frontend_question_id=frontend_question_id,
                source="PLATFORM_ATTEMPT",
            )
            session.add(sp)

    # 5. Update user topic skills
    prob_topics = (
        session.query(Topic)
        .join(ProblemTopic, Topic.id == ProblemTopic.topic_id)
        .filter(ProblemTopic.frontend_question_id == frontend_question_id)
        .all()
    )

    now = datetime.now(timezone.utc)
    for topic in prob_topics:
        us = session.query(UserSkill).filter_by(user_id=user.id, topic_id=topic.id).first()
        if not us:
            us = UserSkill(user_id=user.id, topic_id=topic.id, skill_score=0.35)
            session.add(us)

        # Skill adjustment
        if success:
            delta = 0.05
        else:
            delta = -0.02
        us.skill_score = float(max(0.0, min(1.0, us.skill_score + delta)))
        us.last_practiced_at = now

    # 6. Retrieve LinUCB Bandit Params for this problem arm
    bp = session.query(BanditParam).filter_by(arm_id=frontend_question_id).first()
    if not bp:
        A_orig = np.eye(8, dtype=np.float64)
        b_orig = np.zeros((8, 1), dtype=np.float64)
    else:
        A_orig = np.asarray(bp.matrix_a, dtype=np.float64)
        b_orig = np.asarray(bp.vector_b, dtype=np.float64).reshape((8, 1))

    # 7. Update LinUCB model parameters per SRS:
    linucb = LinUCB(d=8)
    updated_A, updated_b = linucb.update_arm(
        arm_id=frontend_question_id,
        user_context=x_ut,
        reward=r_total,
        current_A=A_orig,
        current_b=b_orig,
    )

    # 8. Persist updated matrices in JSONB
    if not bp:
        bp = BanditParam(
            arm_id=frontend_question_id,
            matrix_a=updated_A.tolist(),
            vector_b=updated_b.tolist(),
        )
        session.add(bp)
    else:
        bp.matrix_a = updated_A.tolist()
        bp.vector_b = updated_b.tolist()

    session.commit()

    return {
        "status": "success",
        "attempt_id": str(attempt.id),
        "user_id": str(user.id),
        "leetcode_handle": user.leetcode_handle,
        "frontend_question_id": frontend_question_id,
        "success": success,
        "reward": reward_dict,
        "updated_at": now.isoformat(),
    }
