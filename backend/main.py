import os
import sys
import uuid
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import func
import jwt

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.database import get_db, SessionLocal, engine, ACTIVE_DATABASE_URL, verify_database_connection
from backend.db.models import (
    Base,
    User,
    Problem,
    Topic,
    ProblemTopic,
    UserSkill,
    Attempt,
    MockInterview,
    MockInterviewTranscript,
    DifficultyLevel,
    UserSolvedProblem,
)
from backend.services.auth_service import (
    register_user,
    verify_user_otp,
    login_user,
    SECRET_KEY,
    ALGORITHM,
)
from backend.services.recommendation_service import recommend_next_problem, get_user_context_vector
from backend.services.attempt_service import record_problem_attempt
from backend.services.leetcode_sync import sync_leetcode_activity, sync_leetcode_catalog
from backend.services.mock_interview_service import (
    create_mock_interview,
    generate_socratic_response,
    complete_mock_interview,
)
from backend.services.roadmap_service import generate_personalized_roadmap
from backend.services.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MainApp")


# ------------------------------------------------------------------
# FastAPI Lifespan (Replaces Deprecated Startup/Shutdown Events)
# ------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    verify_database_connection()
    logger.info(f"Initializing database tables on startup. Active DATABASE_URL: {ACTIVE_DATABASE_URL}")
    Base.metadata.create_all(bind=engine)

    # Seed initial taxonomy and catalog if database is fresh
    db = SessionLocal()
    try:
        topic_count = db.query(Topic).count()
        if topic_count == 0:
            logger.info("Database taxonomy empty. Initializing DB schema and seeding LeetCode catalog...")
            from backend.db.seed_db import init_and_seed_db
            init_and_seed_db()
    except Exception as e:
        logger.error(f"Startup init check error: {e}")
    finally:
        db.close()

    start_scheduler(interval_minutes=15)
    yield
    stop_scheduler()


app = FastAPI(
    title="DSA Learning Agent API",
    description="Production-Ready Adaptive DSA Platform with Dynamic Database Context, LinUCB Bandits & AI Interview Studio",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Request / Response Schemas
# ------------------------------------------------------------------

class LiveSolvedQuestion(BaseModel):
    question_id: str
    title_slug: Optional[str] = None
    title: Optional[str] = None
    difficulty: Optional[str] = None


class LiveRecommendationRequest(BaseModel):
    solved_questions: List[LiveSolvedQuestion]


class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str


class VerifyOTPRequest(BaseModel):
    email: str
    otp_code: str


class LoginRequest(BaseModel):
    identifier: str
    password: str


class UpdateProfileRequest(BaseModel):
    leetcode_handle: Optional[str] = None
    preferred_language: Optional[str] = None


class RecommendationFeedbackRequest(BaseModel):
    user_id: Optional[str] = None
    frontend_question_id: int
    action: str  # 'solve', 'mark_solved', 'mark_failed', 'skip', 'not_attempted'
    time_spent_seconds: Optional[int] = 900


class StartInterviewRequest(BaseModel):
    interview_type: Optional[str] = "DSA"
    difficulty: Optional[str] = "Medium"
    duration_minutes: Optional[int] = 45
    target_topics: Optional[List[str]] = None


# ------------------------------------------------------------------
# Auth Dependency & Rigid User Resolver
# ------------------------------------------------------------------

def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authentication credentials required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[len("Bearer "):].strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication token is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Token has no subject.")
        user_uuid = uuid.UUID(str(user_id))
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter_by(id=user_uuid).first()
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def resolve_user_flexible(identifier: str, db: Session) -> User:
    """Strictly resolves target user by UUID, leetcode_handle, or email without static fallback."""
    user = None
    try:
        uid = uuid.UUID(identifier)
        user = db.query(User).filter_by(id=uid).first()
    except Exception:
        user = (
            db.query(User)
            .filter(
                (User.leetcode_handle == identifier)
                | (User.username == identifier)
                | (User.email == identifier.lower())
            )
            .first()
        )

    if not user:
        raise HTTPException(
            status_code=404,
            detail=f"User identifier '{identifier}' could not be resolved.",
        )

    return user


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------

@app.get("/health")
@app.get("/api/v1/health")
def health_check(db: Session = Depends(get_db)):
    try:
        user_count = db.query(User).count()
        problem_count = db.query(Problem).count()
        db_status = f"healthy (registered_users: {user_count}, problems: {problem_count})"
    except Exception as e:
        db_status = f"unhealthy: {e}"

    return {"status": "ok", "database": db_status}


# --- AUTHENTICATION & ONBOARDING APIs ---

@app.post("/auth/register")
@app.post("/api/v1/auth/register")
def register_endpoint(req: RegisterRequest, db: Session = Depends(get_db)):
    try:
        res = register_user(email=req.email, username=req.username, password=req.password, db=db)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/verify-otp")
@app.post("/auth/verify-email")
@app.post("/api/v1/auth/verify-otp")
def verify_otp_endpoint(req: VerifyOTPRequest, db: Session = Depends(get_db)):
    try:
        res = verify_user_otp(email=req.email, otp_code=req.otp_code, db=db)
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/auth/login")
@app.post("/api/v1/auth/login")
def login_endpoint(req: LoginRequest, db: Session = Depends(get_db)):
    try:
        res = login_user(identifier=req.identifier, password=req.password, db=db)
        return res
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


# --- USER PROFILE & ONBOARDING APIs ---

@app.get("/users/me")
@app.get("/api/v1/users/me")
def get_current_user_profile(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    skills = (
        db.query(Topic.name, UserSkill.skill_score)
        .join(UserSkill, Topic.id == UserSkill.topic_id)
        .filter(UserSkill.user_id == user.id)
        .all()
    )

    # Dynamic calculation of solved problem counts directly from database tables
    solved_qids = set(
        qid for (qid,) in db.query(UserSolvedProblem.frontend_question_id).filter_by(user_id=user.id).all()
    )
    solved_qids.update(
        qid for (qid,) in db.query(Attempt.frontend_question_id).filter_by(user_id=user.id, success=True).all()
    )

# In backend/main.py -> get_current_user_profile and get_analytics

    if solved_qids:
        solved_problems = db.query(Problem).filter(Problem.frontend_question_id.in_(solved_qids)).all()
        total_solved = max(len(solved_problems), user.total_solved or 0)
        easy_solved = max(sum(1 for p in solved_problems if p.difficulty == DifficultyLevel.EASY), user.easy_solved or 0)
        medium_solved = max(sum(1 for p in solved_problems if p.difficulty == DifficultyLevel.MEDIUM), user.medium_solved or 0)
        hard_solved = max(sum(1 for p in solved_problems if p.difficulty == DifficultyLevel.HARD), user.hard_solved or 0)
    else:
        total_solved = user.total_solved or 0
        easy_solved = user.easy_solved or 0
        medium_solved = user.medium_solved or 0
        hard_solved = user.hard_solved or 0

    return {
        "user_id": str(user.id),
        "email": user.email,
        "username": user.username,
        "is_email_verified": user.is_email_verified,
        "leetcode_handle": user.leetcode_handle,
        "preferred_language": user.preferred_language,
        "user_avatar": user.user_avatar or f"https://ui-avatars.com/api/?name={user.username or user.leetcode_handle}",
        "global_ranking": user.global_ranking,
        "total_solved": total_solved,
        "easy_solved": easy_solved,
        "medium_solved": medium_solved,
        "hard_solved": hard_solved,
        "contest_rating": user.contest_rating or 1500,
        "demolition_points": getattr(user, "demolition_points", 0),
        "current_streak": getattr(user, "current_streak", 0),
        "skills": {s[0]: round(s[1], 2) for s in skills},
    }


@app.put("/users/profile")
@app.put("/api/v1/users/profile")
def update_user_profile(req: UpdateProfileRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if req.leetcode_handle:
        user.leetcode_handle = req.leetcode_handle.strip()
        sync_leetcode_activity(username_or_id=user.leetcode_handle, session=db)
    if req.preferred_language:
        user.preferred_language = req.preferred_language.strip()

    db.commit()
    return {
        "status": "updated",
        "leetcode_handle": user.leetcode_handle,
        "preferred_language": user.preferred_language,
        "total_solved": user.total_solved,
        "contest_rating": user.contest_rating,
    }


# --- RECOMMENDATION ENGINE APIs ---

@app.get("/recommendations/next")
@app.post("/recommendations/next")
@app.post("/api/v1/recommendation/next")
def get_next_recommendation(
    user_id: Optional[str] = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target_user = resolve_user_flexible(user_id, db) if user_id else user
    res = recommend_next_problem(user_id=target_user.id, session=db)
    return res


@app.post("/recommendations/feedback")
@app.post("/api/v1/attempts/submit")
def submit_recommendation_feedback(
    req: RecommendationFeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed_actions = {"solve", "mark_solved", "mark_failed", "skip", "not_attempted"}

    if req.action not in allowed_actions:
        raise HTTPException(
            status_code=400,
            detail="Invalid action. Use solve, mark_solved, mark_failed, skip, or not_attempted.",
        )

    if req.action in {"skip", "not_attempted"}:
        return {
            "status": "skipped",
            "frontend_question_id": req.frontend_question_id,
            "attempt_recorded": False,
            "message": "No attempt recorded; failure count unchanged.",
        }

    if req.frontend_question_id <= 0:
        raise HTTPException(status_code=400, detail="Question ID must be a positive integer.")

    target_user = resolve_user_flexible(req.user_id, db) if req.user_id else user
    success = req.action in {"solve", "mark_solved"}

    return record_problem_attempt(
        user_id=target_user.id,
        frontend_question_id=req.frontend_question_id,
        time_spent_seconds=req.time_spent_seconds or 900,
        success=success,
        submission_count=1,
        hints_used=0,
        session=db,
    )


@app.post("/recommendations/next-live")
@app.post("/api/v1/recommendations/next-live")
def recommend_next_problem_live(
    payload: LiveRecommendationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not payload.solved_questions:
        raise HTTPException(status_code=400, detail="No solved question IDs were provided.")

    try:
        solved_ids = {int(q.question_id) for q in payload.solved_questions}
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid solved question ID.")

    if any(qid <= 0 for qid in solved_ids):
        raise HTTPException(status_code=400, detail="Question IDs must be positive integers.")

    try:
        return recommend_next_problem(user_id=user, session=db, live_solved_ids=solved_ids)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# --- AI MOCK INTERVIEW APIs ---

@app.post("/interviews/start")
@app.post("/api/v1/interviews")
def start_interview_session(req: StartInterviewRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Pass target_topics directly (if None, mock_interview_service dynamically selects lowest skills)
    res = create_mock_interview(
        user_id=user.id,
        target_topics=req.target_topics,
        time_limit_minutes=req.duration_minutes or 45,
        session=db,
    )
    res["interview_type"] = req.interview_type or "DSA"
    res["difficulty"] = req.difficulty or "Medium"
    return res


@app.post("/interviews/submit")
@app.post("/api/v1/interviews/{interview_id}/finish")
def submit_interview_session(interview_id: Optional[str] = None, body: Optional[Dict[str, Any]] = None, db: Session = Depends(get_db)):
    target_id = interview_id or (body.get("interview_id") if body else None)
    if not target_id:
        raise HTTPException(status_code=400, detail="interview_id required.")

    code = body.get("submitted_code") if body else ""
    res = complete_mock_interview(interview_id=uuid.UUID(target_id), submitted_code=code, session=db)
    return res


@app.get("/interviews/history")
def get_interview_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    interviews = db.query(MockInterview).filter_by(user_id=user.id).order_by(MockInterview.created_at.desc()).all()
    return {
        "user_id": str(user.id),
        "history": [
            {
                "interview_id": str(m.id),
                "interview_type": m.interview_type,
                "status": m.status.value,
                "overall_performance_index": m.overall_performance_index,
                "communication_score": m.communication_score,
                "code_quality_score": m.code_quality_score,
                "created_at": m.created_at.isoformat(),
            }
            for m in interviews
        ],
    }


# --- ROADMAP & ANALYTICS APIs ---

@app.get("/roadmap/me")
@app.get("/api/v1/roadmap/me")
def get_my_roadmap(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return generate_personalized_roadmap(user=user, session=db)


@app.get("/analytics/me")
@app.get("/api/v1/analytics/{user_id}")
def get_analytics(user_id: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target_user = resolve_user_flexible(user_id, db) if user_id else user

    skills = (
        db.query(Topic.name, UserSkill.skill_score)
        .join(UserSkill, Topic.id == UserSkill.topic_id)
        .filter(UserSkill.user_id == target_user.id)
        .all()
    )

    attempts = db.query(Attempt).filter_by(user_id=target_user.id).all()
    total_attempts = len(attempts)
    total_correct = sum(1 for a in attempts if a.success)
    overall_accuracy = (total_correct / total_attempts) if total_attempts > 0 else 0.0

    # Real solved counts calculated directly from user solved records
    solved_qids = set(
        qid for (qid,) in db.query(UserSolvedProblem.frontend_question_id).filter_by(user_id=target_user.id).all()
    )
    solved_qids.update(
        qid for (qid,) in db.query(Attempt.frontend_question_id).filter_by(user_id=target_user.id, success=True).all()
    )

    if solved_qids:
        solved_problems = db.query(Problem).filter(Problem.frontend_question_id.in_(solved_qids)).all()
        total_solved = len(solved_problems)
        easy_solved = sum(1 for p in solved_problems if p.difficulty == DifficultyLevel.EASY)
        medium_solved = sum(1 for p in solved_problems if p.difficulty == DifficultyLevel.MEDIUM)
        hard_solved = sum(1 for p in solved_problems if p.difficulty == DifficultyLevel.HARD)
    else:
        total_solved = target_user.total_solved or 0
        easy_solved = target_user.easy_solved or 0
        medium_solved = target_user.medium_solved or 0
        hard_solved = target_user.hard_solved or 0

    radar_data = [{"topic": s[0], "score": round(s[1], 2)} for s in skills]

    return {
        "user_id": str(target_user.id),
        "username": target_user.username,
        "leetcode_handle": target_user.leetcode_handle,
        "user_avatar": target_user.user_avatar or f"https://ui-avatars.com/api/?name={target_user.username or target_user.leetcode_handle}",
        "global_ranking": target_user.global_ranking,
        "total_solved": total_solved,
        "easy_solved": easy_solved,
        "medium_solved": medium_solved,
        "hard_solved": hard_solved,
        "contest_rating": target_user.contest_rating or 1500,
        "total_attempts": total_attempts,
        "total_correct": total_correct,
        "overall_accuracy": round(overall_accuracy, 3),
        "radar_data": radar_data,
        "skills": {s[0]: round(s[1], 2) for s in skills},
    }


# --- LEETCODE SYNC & AUDIT ENDPOINTS ---

@app.post("/admin/sync-catalog")
@app.post("/api/v1/admin/sync-catalog")
def trigger_catalog_sync(db: Session = Depends(get_db)):
    res = sync_leetcode_catalog(db)
    return res


@app.post("/leetcode/sync")
@app.post("/api/v1/leetcode/sync")
def trigger_leetcode_sync(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    res = sync_leetcode_activity(username_or_id=user.leetcode_handle, session=db)
    return res


@app.get("/users/me/sync-audit")
@app.get("/users/{user_id}/sync-audit")
@app.get("/api/v1/users/{user_id}/sync-audit")
def get_user_sync_audit(
    user_id: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user_id and user_id != "me":
        try:
            requested_user_id = uuid.UUID(user_id)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(status_code=400, detail="Invalid user ID.")

        if requested_user_id != user.id:
            raise HTTPException(status_code=403, detail="You can only access your own sync audit.")

    total_catalog_problems = db.query(Problem).count()
    solved_ids = {
        row[0] for row in db.query(UserSolvedProblem.frontend_question_id).filter_by(user_id=user.id).all()
    }
    catalog_ids = {row[0] for row in db.query(Problem.frontend_question_id).all()}

    solved_present_in_catalog = len(solved_ids & catalog_ids)
    solved_missing_from_catalog = len(solved_ids - catalog_ids)
    final_recommendation_candidate_count = len(catalog_ids - solved_ids)

    return {
        "user_id": str(user.id),
        "leetcode_handle": user.leetcode_handle,
        "total_catalog_problems": total_catalog_problems,
        "current_user_total_solved": len(solved_ids),
        "solved_problems_present_in_catalog": solved_present_in_catalog,
        "solved_problems_missing_from_catalog": solved_missing_from_catalog,
        "final_recommendation_candidate_count": final_recommendation_candidate_count,
    }


# --- WEBSOCKET LIVE AI MOCK INTERVIEW STREAMING ---

@app.websocket("/ws/v1/interview/{interview_id}")
async def websocket_interview_endpoint(websocket: WebSocket, interview_id: str):
    await websocket.accept()
    db = SessionLocal()
    try:
        iid = uuid.UUID(interview_id)
        await websocket.send_json({
            "event": "connected",
            "interview_id": interview_id,
            "message": "Connected to Socratic AI Interviewer stream.",
        })

        while True:
            data = await websocket.receive_json()
            user_msg = data.get("message", "")
            hint_req = data.get("hint_requested", None)

            if not user_msg and not hint_req:
                continue

            response = generate_socratic_response(
                interview_id=iid,
                user_message=user_msg,
                requested_hint=hint_req,
                session=db,
            )

            await websocket.send_json({
                "event": "message",
                "speaker": "SYSTEM_AI",
                "message_text": response["message_text"],
                "hint_given": response["hint_given"],
                "timestamp": response["timestamp"],
            })
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for interview={interview_id}")
    except Exception as e:
        logger.error(f"WebSocket error for interview={interview_id}: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)