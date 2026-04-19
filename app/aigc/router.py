import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.aigc.models import AigcTaskStatus
from app.aigc.provider_registry import list_available_providers
from app.aigc.schemas import (
    AigcApproveIn,
    AigcCandidateFeedbackIn,
    AigcProviderOut,
    AigcRejectIn,
    AigcTaskCreateIn,
    AigcTaskOut,
)
from app.aigc.service import (
    add_candidate_feedback,
    approve_aigc_task,
    create_aigc_task,
    get_aigc_task,
    list_aigc_tasks,
    reject_aigc_task,
)
from app.auth.deps import require_role
from app.auth.models import User, UserRole
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/aigc", tags=["aigc"])


@router.post("/tasks", response_model=AigcTaskOut, status_code=201)
def create_task(
    body: AigcTaskCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    task = create_aigc_task(db, user=user, body=body)
    if settings.async_mode == "celery":
        from app.ai.tasks import celery_aigc_generate

        celery_aigc_generate.delay(str(task.id))
    return task


@router.get("/tasks", response_model=list[AigcTaskOut])
def get_tasks(
    status: AigcTaskStatus | None = None,
    product_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor, UserRole.viewer)),
):
    return list_aigc_tasks(db, status=status, product_id=product_id, limit=limit, offset=offset)


@router.get("/tasks/{task_id}", response_model=AigcTaskOut)
def get_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor, UserRole.viewer)),
):
    return get_aigc_task(db, task_id)


@router.post("/tasks/{task_id}/approve", response_model=AigcTaskOut)
def approve_task(
    task_id: uuid.UUID,
    body: AigcApproveIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    return approve_aigc_task(
        db,
        task_id=task_id,
        selected_candidate_id=body.selected_candidate_id,
        target_asset_type=body.target_asset_type,
        reviewer=user,
    )


@router.post("/tasks/{task_id}/reject", response_model=AigcTaskOut)
def reject_task(
    task_id: uuid.UUID,
    body: AigcRejectIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    return reject_aigc_task(db, task_id=task_id, reason=body.reason, reviewer=user)


@router.post("/candidates/{candidate_id}/feedback", status_code=201)
def submit_feedback(
    candidate_id: uuid.UUID,
    body: AigcCandidateFeedbackIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    feedback = add_candidate_feedback(db, candidate_id=candidate_id, user=user, body=body)
    return {"id": str(feedback.id), "candidate_id": str(feedback.candidate_id)}


@router.get("/providers", response_model=list[AigcProviderOut])
def providers(
    _: User = Depends(require_role(UserRole.admin, UserRole.editor, UserRole.viewer)),
):
    return list_available_providers()
