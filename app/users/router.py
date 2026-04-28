import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import require_role
from app.auth.models import User, UserRole
from app.database import get_db
from app.users.schemas import RegistrationRequestOut, UserCreate, UserOut, UserUpdate
from app.users.service import (
    approve_registration_request,
    create_user,
    deactivate_user_safe,
    delete_registration_request,
    list_registration_requests,
    list_users,
    update_user_safe,
)

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
    current_user: User = Depends(require_role(UserRole.admin)),
):
    user = update_user_safe(db, current_user.id, user_id, **body.model_dump(exclude_none=True))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
):
    if not deactivate_user_safe(db, current_user.id, user_id):
        raise HTTPException(status_code=404, detail="User not found")


@router.get("/registration-requests", response_model=list[RegistrationRequestOut])
def list_pending(
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    return list_registration_requests(db)


@router.post("/registration-requests/{request_id}/approve", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def approve(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    return approve_registration_request(db, request_id)


@router.delete("/registration-requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def reject(
    request_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin)),
):
    if not delete_registration_request(db, request_id):
        raise HTTPException(status_code=404, detail="Registration request not found")
