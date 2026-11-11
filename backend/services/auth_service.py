import os
import random
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import jwt
import bcrypt
from sqlalchemy.orm import Session

from backend.db.models import User, EmailVerification, PasswordReset, RefreshToken, UserSkill, Topic

SECRET_KEY = os.getenv("JWT_SECRET", "dsa-learning-agent-jwt-secret-key-2026-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours for seamless DX
REFRESH_TOKEN_EXPIRE_DAYS = 7


def hash_password(password: str) -> str:
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode('utf-8')[:72]
        hash_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(pwd_bytes, hash_bytes)
    except Exception:
        return False


def generate_otp() -> str:
    return f"{random.randint(100000, 999999)}"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": now})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str, db: Session) -> str:
    token_str = secrets.token_urlsafe(64)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    rt = RefreshToken(
        user_id=user_id,
        token=token_str,
        expires_at=expires_at,
    )
    db.add(rt)
    db.commit()
    return token_str


def register_user(email: str, username: str, password: str, db: Session) -> Dict[str, Any]:
    email_clean = email.strip().lower()
    username_clean = username.strip()

    # Check duplicate email
    if db.query(User).filter_by(email=email_clean).first():
        raise ValueError("An account with this email already exists.")

    # Check duplicate username
    if db.query(User).filter_by(username=username_clean).first():
        raise ValueError("This username is already taken.")

    # Create User
    user = User(
        email=email_clean,
        username=username_clean,
        password_hash=hash_password(password),
        is_email_verified=False,
        leetcode_handle=username_clean,  # Default to username initially
    )
    db.add(user)
    db.flush()

    # Initialize User Skills for 18 topics
    topics = db.query(Topic).all()
    for t in topics:
        db.add(UserSkill(user_id=user.id, topic_id=t.id, skill_score=0.35))

    # Generate OTP Verification
    otp_code = generate_otp()
    v_token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)

    ev = EmailVerification(
        user_id=user.id,
        email=email_clean,
        otp_code=otp_code,
        verification_token=v_token,
        expires_at=expires_at,
    )
    db.add(ev)
    db.commit()

    return {
        "status": "pending_verification",
        "user_id": str(user.id),
        "email": email_clean,
        "username": username_clean,
        "otp_code": otp_code,  # Provided for instant verification in UI
        "verification_token": v_token,
        "message": f"Verification OTP sent to {email_clean}. Please verify your account.",
    }


def verify_user_otp(email: str, otp_code: str, db: Session) -> Dict[str, Any]:
    email_clean = email.strip().lower()
    user = db.query(User).filter_by(email=email_clean).first()
    if not user:
        raise ValueError(f"No account found with email '{email_clean}'.")

    ev = (
        db.query(EmailVerification)
        .filter_by(user_id=user.id, otp_code=otp_code.strip(), is_used=False)
        .order_by(EmailVerification.created_at.desc())
        .first()
    )

    if not ev:
        raise ValueError("Invalid verification OTP code.")

    now = datetime.now(timezone.utc)
    ev_expires = ev.expires_at.replace(tzinfo=timezone.utc) if ev.expires_at.tzinfo is None else ev.expires_at

    if now > ev_expires:
        raise ValueError("Verification OTP code has expired. Please request a new one.")

    # Mark verified
    ev.is_used = True
    user.is_email_verified = True
    db.commit()

    # Create Access & Refresh Tokens
    access_token = create_access_token({"sub": str(user.id), "username": user.username})
    refresh_token = create_refresh_token(str(user.id), db)

    return {
        "status": "verified",
        "user_id": str(user.id),
        "email": user.email,
        "username": user.username,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def login_user(identifier: str, password: str, db: Session) -> Dict[str, Any]:
    ident_clean = identifier.strip()
    # Search by email or username or leetcode_handle
    user = (
        db.query(User)
        .filter((User.email == ident_clean.lower()) | (User.username == ident_clean) | (User.leetcode_handle == ident_clean))
        .first()
    )

    if not user or not verify_password(password, user.password_hash):
        raise ValueError("Invalid username/email or password.")

    if not user.is_email_verified:
        # Generate fresh OTP code for pending verification
        otp_code = generate_otp()
        v_token = secrets.token_hex(32)
        ev = EmailVerification(
            user_id=user.id,
            email=user.email,
            otp_code=otp_code,
            verification_token=v_token,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
        )
        db.add(ev)
        db.commit()
        return {
            "status": "pending_verification",
            "user_id": str(user.id),
            "email": user.email,
            "username": user.username,
            "otp_code": otp_code,
            "message": "Account email is not verified yet. An OTP has been generated for verification.",
        }

    access_token = create_access_token({"sub": str(user.id), "username": user.username})
    refresh_token = create_refresh_token(str(user.id), db)

    return {
        "status": "authenticated",
        "user_id": str(user.id),
        "email": user.email,
        "username": user.username,
        "leetcode_handle": user.leetcode_handle,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }
