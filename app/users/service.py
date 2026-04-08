import uuid
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.auth.service import hash_password


def create_user(db: Session, email: str, password: str, name: str, role: UserRole, company: str | None = None) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
        role=role,
        company=company,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def list_users(db: Session) -> list[User]:
    return db.query(User).order_by(User.created_at.desc()).all()


def update_user(db: Session, user_id: uuid.UUID, **kwargs) -> User | None:
    user = db.get(User, user_id)
    if not user:
        return None
    for k, v in kwargs.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


def deactivate_user(db: Session, user_id: uuid.UUID) -> bool:
    user = db.get(User, user_id)
    if not user:
        return False
    user.is_active = False
    db.commit()
    return True
