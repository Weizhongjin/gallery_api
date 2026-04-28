from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.auth.models import User, UserRegistrationRequest
from app.config import settings


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_token(token: str) -> str:
    """Returns user_id string. Raises JWTError on invalid token."""
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    return payload["sub"]


def create_registration_request(db: Session, *, email: str, password: str, name: str) -> UserRegistrationRequest:
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="该邮箱已存在正式账号")
    if db.query(UserRegistrationRequest).filter(UserRegistrationRequest.email == email).first():
        raise HTTPException(status_code=409, detail="该邮箱已有待审核申请")

    req = UserRegistrationRequest(email=email, password_hash=hash_password(password), name=name)
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


def has_pending_registration_request(db: Session, email: str) -> bool:
    return db.query(UserRegistrationRequest).filter(UserRegistrationRequest.email == email).first() is not None


def check_pending_login(db: Session, email: str, password: str) -> bool:
    """Return True if a pending registration request exists AND the password matches."""
    pending = db.query(UserRegistrationRequest).filter(UserRegistrationRequest.email == email).first()
    if pending and verify_password(password, pending.password_hash):
        return True
    return False
