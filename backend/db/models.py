import enum
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    Boolean,
    Float,
    Text,
    DateTime,
    ForeignKey,
    Enum as SQLEnum,
    JSON,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class DifficultyLevel(str, enum.Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    HARD = "Hard"


class InterviewStatus(str, enum.Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class HintLevel(str, enum.Enum):
    CLARIFICATION = "CLARIFICATION"
    SMALL_NUDGE = "SMALL_NUDGE"
    APPROACH_OUTLINE = "APPROACH_OUTLINE"
    FULL_SOLUTION = "FULL_SOLUTION"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    is_email_verified = Column(Boolean, default=False)
    leetcode_handle = Column(String(100), unique=True, nullable=True, index=True)
    preferred_language = Column(String(20), default="Java")
    contest_rating = Column(Integer, default=1500)
    global_ranking = Column(Integer, nullable=True)
    user_avatar = Column(Text, nullable=True)
    easy_solved = Column(Integer, default=0)
    medium_solved = Column(Integer, default=0)
    hard_solved = Column(Integer, default=0)
    total_solved = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    email_verifications = relationship("EmailVerification", back_populates="user", cascade="all, delete-orphan")
    password_resets = relationship("PasswordReset", back_populates="user", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    skills = relationship("UserSkill", back_populates="user", cascade="all, delete-orphan")
    attempts = relationship("Attempt", back_populates="user", cascade="all, delete-orphan")
    solved_problems = relationship("UserSolvedProblem", back_populates="user", cascade="all, delete-orphan")
    interviews = relationship("MockInterview", back_populates="user", cascade="all, delete-orphan")


class EmailVerification(Base):
    __tablename__ = "email_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), nullable=False)
    otp_code = Column(String(6), nullable=False)
    verification_token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="email_verifications")


class PasswordReset(Base):
    __tablename__ = "password_resets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reset_token = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="password_resets")


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(Text, unique=True, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="refresh_tokens")


class Problem(Base):
    __tablename__ = "problems"

    frontend_question_id = Column(Integer, primary_key=True)
    title = Column(String(255), nullable=False)
    title_slug = Column(String(255), nullable=False)
    difficulty = Column(SQLEnum(DifficultyLevel, values_callable=lambda obj: [e.value for e in obj]), nullable=False)
    expected_time_minutes = Column(Integer, default=30)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    topics = relationship("ProblemTopic", back_populates="problem", cascade="all, delete-orphan")
    attempts = relationship("Attempt", back_populates="problem", cascade="all, delete-orphan")
    solved_by_users = relationship("UserSolvedProblem", back_populates="problem", cascade="all, delete-orphan")
    bandit_params = relationship("BanditParam", back_populates="problem", uselist=False, cascade="all, delete-orphan")


class Topic(Base):
    __tablename__ = "topics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)

    problems = relationship("ProblemTopic", back_populates="topic", cascade="all, delete-orphan")
    user_skills = relationship("UserSkill", back_populates="topic", cascade="all, delete-orphan")


class ProblemTopic(Base):
    __tablename__ = "problem_topics"

    frontend_question_id = Column(Integer, ForeignKey("problems.frontend_question_id", ondelete="CASCADE"), primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)

    problem = relationship("Problem", back_populates="topics")
    topic = relationship("Topic", back_populates="problems")


class UserSkill(Base):
    __tablename__ = "user_skills"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    topic_id = Column(Integer, ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True)
    skill_score = Column(Float, default=0.5)
    last_practiced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="skills")
    topic = relationship("Topic", back_populates="user_skills")


class Attempt(Base):
    __tablename__ = "attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    frontend_question_id = Column(Integer, ForeignKey("problems.frontend_question_id", ondelete="CASCADE"), nullable=False)
    time_spent_seconds = Column(Integer, nullable=False)
    success = Column(Boolean, nullable=False)
    submission_count = Column(Integer, default=1)
    hints_used = Column(Integer, default=0)
    computed_reward = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="attempts")
    problem = relationship("Problem", back_populates="attempts")


class BanditParam(Base):
    __tablename__ = "bandit_params"

    arm_id = Column(Integer, ForeignKey("problems.frontend_question_id", ondelete="CASCADE"), primary_key=True)
    matrix_a = Column(JSONB, nullable=False)
    vector_b = Column(JSONB, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    problem = relationship("Problem", back_populates="bandit_params")


class MockInterview(Base):
    __tablename__ = "mock_interviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    interview_type = Column(String(50), default="DSA")
    difficulty = Column(SQLEnum(DifficultyLevel, values_callable=lambda obj: [e.value for e in obj]), default=DifficultyLevel.MEDIUM)
    target_topics = Column(JSONB, nullable=False)
    status = Column(SQLEnum(InterviewStatus, values_callable=lambda obj: [e.value for e in obj]), default=InterviewStatus.IN_PROGRESS)
    time_limit_minutes = Column(Integer, default=45)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
    communication_score = Column(Float, nullable=True)
    code_quality_score = Column(Float, nullable=True)
    time_management_score = Column(Float, nullable=True)
    overall_performance_index = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="interviews")
    transcripts = relationship("MockInterviewTranscript", back_populates="interview", cascade="all, delete-orphan")


class MockInterviewTranscript(Base):
    __tablename__ = "mock_interview_transcripts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    interview_id = Column(UUID(as_uuid=True), ForeignKey("mock_interviews.id", ondelete="CASCADE"), nullable=False)
    speaker = Column(String(20), nullable=False)
    message_text = Column(Text, nullable=False)
    hint_given = Column(SQLEnum(HintLevel, values_callable=lambda obj: [e.value for e in obj]), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    interview = relationship("MockInterview", back_populates="transcripts")


class UserSolvedProblem(Base):
    __tablename__ = "user_solved_problems"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    frontend_question_id = Column(Integer, ForeignKey("problems.frontend_question_id", ondelete="CASCADE"), nullable=False, index=True)
    solved_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    synced_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    source = Column(String(50), default="LEETCODE_SYNC")

    __table_args__ = (
        UniqueConstraint("user_id", "frontend_question_id", name="uq_user_solved_problem"),
    )

    user = relationship("User", back_populates="solved_problems")
    problem = relationship("Problem", back_populates="solved_by_users")

