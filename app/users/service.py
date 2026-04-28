import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.auth.models import User, UserRegistrationRequest, UserRole
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


def _active_admin_count(db: Session) -> int:
    return db.query(User).filter(User.role == UserRole.admin, User.is_active == True).count()


def update_user(db: Session, user_id: uuid.UUID, **kwargs) -> User | None:
    user = db.get(User, user_id)
    if not user:
        return None
    for k, v in kwargs.items():
        setattr(user, k, v)
    db.commit()
    db.refresh(user)
    return user


def update_user_safe(db: Session, actor_id: uuid.UUID, user_id: uuid.UUID, **kwargs) -> User | None:
    user = db.get(User, user_id)
    if not user:
        return None
    if user.role == UserRole.admin:
        # Prevent downgrade via role change
        if kwargs.get("role") and kwargs["role"] != UserRole.admin:
            if actor_id == user_id:
                raise HTTPException(status_code=409, detail="不能移除当前登录管理员的管理员角色")
            if _active_admin_count(db) <= 1:
                raise HTTPException(status_code=409, detail="系统至少需要保留一个管理员")
        # Prevent deactivation via is_active=False on the PATCH endpoint
        if kwargs.get("is_active") is False and user.is_active:
            if actor_id == user_id:
                raise HTTPException(status_code=409, detail="不能停用当前登录管理员账号")
            if _active_admin_count(db) <= 1:
                raise HTTPException(status_code=409, detail="系统至少需要保留一个管理员")
    return update_user(db, user_id, **kwargs)


def deactivate_user(db: Session, user_id: uuid.UUID) -> bool:
    user = db.get(User, user_id)
    if not user:
        return False
    user.is_active = False
    db.commit()
    return True


def deactivate_user_safe(db: Session, actor_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    user = db.get(User, user_id)
    if not user:
        return False
    if user.role == UserRole.admin and user.is_active:
        if actor_id == user_id:
            raise HTTPException(status_code=409, detail="不能停用当前登录管理员账号")
        if _active_admin_count(db) <= 1:
            raise HTTPException(status_code=409, detail="系统至少需要保留一个管理员")
    return deactivate_user(db, user_id)


def list_registration_requests(db: Session) -> list[UserRegistrationRequest]:
    return db.query(UserRegistrationRequest).order_by(UserRegistrationRequest.created_at.asc()).all()


def approve_registration_request(db: Session, request_id: uuid.UUID) -> User:
    req = db.get(UserRegistrationRequest, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Registration request not found")
    if db.query(User).filter(User.email == req.email).first():
        raise HTTPException(status_code=409, detail="该邮箱已存在正式账号")

    user = User(
        email=req.email,
        password_hash=req.password_hash,
        name=req.name,
        role=UserRole.viewer,
    )
    db.add(user)
    db.flush()
    db.delete(req)
    db.commit()
    db.refresh(user)
    return user


def delete_registration_request(db: Session, request_id: uuid.UUID) -> bool:
    req = db.get(UserRegistrationRequest, request_id)
    if not req:
        return False
    db.delete(req)
    db.commit()
    return True
