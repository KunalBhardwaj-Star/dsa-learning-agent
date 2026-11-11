import uuid
import json
import random
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.db.models import (
    User,
    Problem,
    Topic,
    ProblemTopic,
    MockInterview,
    MockInterviewTranscript,
    InterviewStatus,
    HintLevel,
)
from backend.services.attempt_service import record_problem_attempt


def create_mock_interview(
    user_id: uuid.UUID,
    target_topics: Optional[List[str]] = None,
    time_limit_minutes: int = 45,
    session: Session = None,
) -> Dict[str, Any]:
    """
    Creates a new AI Mock Interview Session per SRS Section 5.
    Dynamically selects 1-2 target questions matching topic competencies.
    """
    user = session.query(User).filter_by(id=user_id).first()
    if not user:
        raise ValueError(f"User with id={user_id} not found.")

    if not target_topics:
        target_topics = ["DP", "Graphs", "Trees"]

    # Select candidate problems for target topics
    probs = (
        session.query(Problem)
        .join(ProblemTopic, Problem.frontend_question_id == ProblemTopic.frontend_question_id)
        .join(Topic, ProblemTopic.topic_id == Topic.id)
        .filter(Topic.name.in_(target_topics))
        .all()
    )

    if not probs:
        probs = session.query(Problem).limit(5).all()

    selected_problems = random.sample(probs, min(2, len(probs)))
    selected_payload = [
        {
            "frontend_question_id": p.frontend_question_id,
            "title": p.title,
            "difficulty": p.difficulty.value,
            "expected_time_minutes": p.expected_time_minutes,
        }
        for p in selected_problems
    ]

    mock = MockInterview(
        user_id=user_id,
        target_topics={"topics": target_topics, "problems": selected_payload},
        status=InterviewStatus.IN_PROGRESS,
        time_limit_minutes=time_limit_minutes,
    )
    session.add(mock)
    session.flush()

    # Initial AI greeting transcript
    display_name = user.username or user.leetcode_handle or "Candidate"
    greeting_text = (
        f"Welcome {display_name} to your AI Socratic Mock Interview!\n"
        f"Target Challenge: #{selected_problems[0].frontend_question_id} {selected_problems[0].title} ({selected_problems[0].difficulty.value}).\n"
        f"Before coding, please explain your proposed approach and time/space complexity."
    )
    transcript = MockInterviewTranscript(
        interview_id=mock.id,
        speaker="SYSTEM_AI",
        message_text=greeting_text,
    )
    session.add(transcript)
    session.commit()

    return {
        "interview_id": str(mock.id),
        "user_id": str(user_id),
        "status": mock.status.value,
        "time_limit_minutes": mock.time_limit_minutes,
        "target_topics": target_topics,
        "problems": selected_payload,
        "initial_message": greeting_text,
    }


def generate_socratic_response(
    interview_id: uuid.UUID,
    user_message: str,
    requested_hint: Optional[str] = None,
    session: Session = None,
) -> Dict[str, Any]:
    """
    Generates Socratic interviewer response per SRS Section 5.
    Asks probing questions, provides hints when explicitly requested, logs transcript.
    """
    mock = session.query(MockInterview).filter_by(id=interview_id).first()
    if not mock:
        raise ValueError(f"Mock interview id={interview_id} not found.")

    # 1. Log User Message Transcript
    user_tx = MockInterviewTranscript(
        interview_id=interview_id,
        speaker="USER",
        message_text=user_message,
        hint_given=HintLevel(requested_hint) if requested_hint and requested_hint in HintLevel.__members__ else None,
    )
    session.add(user_tx)

    # 2. Determine Socratic LLM response
    response_text = ""
    hint_enum = None

    if requested_hint == "CLARIFICATION":
        hint_enum = HintLevel.CLARIFICATION
        response_text = "Clarification: Consider constraints on input size and potential negative bounds. What edge cases could break your initial assumption?"
    elif requested_hint == "SMALL_NUDGE":
        hint_enum = HintLevel.SMALL_NUDGE
        response_text = "Nudge: How might a hash map or two-pointer technique reduce your search time from quadratic O(N^2) to linear O(N)?"
    elif requested_hint == "APPROACH_OUTLINE":
        hint_enum = HintLevel.APPROACH_OUTLINE
        response_text = "Approach Outline: 1. Initialize lookup state. 2. Iterate through elements storing visited complements. 3. Return matching indices."
    elif requested_hint == "FULL_SOLUTION":
        hint_enum = HintLevel.FULL_SOLUTION
        response_text = "Solution Outline: Use a map to store value -> index pairs. In a single pass, check if (target - num) is in map."
    else:
        # Socratic probing based on message content
        lower_msg = user_message.lower()
        if "o(n)" in lower_msg or "complexity" in lower_msg or "space" in lower_msg:
            response_text = "Solid complexity analysis! How does your space complexity scale if auxiliary memory cannot be allocated?"
        elif "dp" in lower_msg or "recursion" in lower_msg or "memo" in lower_msg:
            response_text = "Good subproblem identification. What are your state transition equations and base case boundary conditions?"
        elif "class" in lower_msg or "def " in lower_msg or "public" in lower_msg:
            response_text = "Your implementation structure looks clear. Have you considered null pointers or out-of-bounds indexing?"
        else:
            response_text = "Could you explain why this choice of data structure is superior to a simpler alternative here?"

    ai_tx = MockInterviewTranscript(
        interview_id=interview_id,
        speaker="SYSTEM_AI",
        message_text=response_text,
        hint_given=hint_enum,
    )
    session.add(ai_tx)
    session.commit()

    return {
        "interview_id": str(interview_id),
        "speaker": "SYSTEM_AI",
        "message_text": response_text,
        "hint_given": hint_enum.value if hint_enum else None,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def complete_mock_interview(
    interview_id: uuid.UUID,
    submitted_code: Optional[str] = None,
    session: Session = None,
) -> Dict[str, Any]:
    """
    Finalizes interview session, computes REAL evaluation scores from actual transcripts and events,
    and feeds overall_performance_index back to LinUCB.
    """
    mock = session.query(MockInterview).filter_by(id=interview_id).first()
    if not mock:
        raise ValueError(f"Mock interview id={interview_id} not found.")

    transcripts = session.query(MockInterviewTranscript).filter_by(interview_id=interview_id).all()
    hints_count = sum(1 for t in transcripts if t.hint_given is not None)
    user_transcripts = [t for t in transcripts if t.speaker == "USER"]
    user_turns = len(user_transcripts)

    # 1. Real Communication Score Calculation
    total_user_words = sum(len(t.message_text.split()) for t in user_transcripts)
    avg_words_per_turn = (total_user_words / user_turns) if user_turns > 0 else 0.0

    complexity_mentions = sum(
        1 for t in user_transcripts if any(kw in t.message_text.lower() for kw in ["o(n)", "complexity", "space", "time", "dp", "tree", "graph"])
    )

    comm_score = min(1.0, max(0.35, 0.4 + (avg_words_per_turn * 0.02) + (complexity_mentions * 0.1) - (hints_count * 0.05)))

    # 2. Real Code Quality Score Calculation
    code_text = submitted_code or ""
    code_length = len(code_text.strip())
    has_structure = any(kw in code_text for kw in ["class", "def", "public", "return", "for", "while", "if"])

    if code_length > 50 and has_structure:
        code_score = min(0.98, 0.65 + (min(code_length, 300) / 1000.0) + (0.1 if "return" in code_text else 0.0))
    elif code_length > 0:
        code_score = 0.50
    else:
        code_score = 0.30

    # 3. Real Time Management Score Calculation
    now = datetime.now(timezone.utc)
    started_at = mock.started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    elapsed_minutes = max(1.0, (now - started_at).total_seconds() / 60.0)
    target_time = float(mock.time_limit_minutes or 45)

    if elapsed_minutes <= target_time:
        time_score = max(0.7, 1.0 - (elapsed_minutes / (target_time * 2.0)))
    else:
        time_score = max(0.4, 1.0 - (elapsed_minutes / target_time))

    # 4. Composite Performance Index
    overall_idx = round((0.35 * comm_score) + (0.45 * code_score) + (0.20 * time_score), 3)

    mock.status = InterviewStatus.COMPLETED
    mock.completed_at = now
    mock.communication_score = round(comm_score, 2)
    mock.code_quality_score = round(code_score, 2)
    mock.time_management_score = round(time_score, 2)
    mock.overall_performance_index = overall_idx

    # Record target problem attempt to feed LinUCB
    problems = mock.target_topics.get("problems", [])
    if problems:
        target_qid = problems[0]["frontend_question_id"]
        record_problem_attempt(
            user_id=mock.user_id,
            frontend_question_id=target_qid,
            time_spent_seconds=int(elapsed_minutes * 60),
            success=(overall_idx >= 0.60),
            submission_count=1,
            hints_used=hints_count,
            session=session,
        )

    session.commit()

    return {
        "interview_id": str(interview_id),
        "status": mock.status.value,
        "communication_score": mock.communication_score,
        "code_quality_score": mock.code_quality_score,
        "time_management_score": mock.time_management_score,
        "overall_performance_index": mock.overall_performance_index,
        "completed_at": mock.completed_at.isoformat(),
    }
