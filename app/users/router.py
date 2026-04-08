import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import require_role
from app.auth.models import User, UserRole
from app.database import get_db
from app.users.schemas import UserCreate, UserOut, UserUpdate
from app.users.service import create_user, deactivate_user, list_users, update_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create(
    body: UserCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    return create_user(db, body.email, body.password, body.name, body.role, body.company)


@router.get("", response_model=list[UserOut])
def list_all(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    return list_users(db)


@router.patch("/{user_id}", response_model=UserOut)
def patch(
    user_id: uuid.UUID,
    body: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    user = update_user(db, user_id, **body.model_dump(exclude_none=True))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    if not deactivate_user(db, user_id):
        raise HTTPException(status_code=404, detail="User not found")
