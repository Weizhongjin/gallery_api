import mimetypes
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.aigc.models import AigcTaskCandidate, AigcTaskStatus
from app.aigc.provider_registry import list_available_providers
from app.aigc.schemas import (
    AigcApproveIn,
    AigcCandidateFeedbackIn,
    AigcOptimizeCreateIn,
    AigcProviderOut,
    AigcRejectIn,
    AigcTaskCreateIn,
    AigcTaskOut,
)
from app.aigc.service import (
    add_candidate_feedback,
    approve_aigc_task,
    create_aigc_optimization_task,
    create_aigc_task,
    get_aigc_task,
    list_aigc_tasks,
    mark_aigc_task_failed,
    reject_aigc_task,
)
from app.auth.deps import get_current_user_with_query_token, require_role
from app.auth.models import User, UserRole
from app.config import settings
from app.database import get_db
from app.storage import get_storage, uri_to_key

router = APIRouter(prefix="/aigc", tags=["aigc"])

_ENQUEUE_ERROR_CODE = "AIGC_ENQUEUE_FAILED"


def _enqueue_aigc_generation(background_tasks: BackgroundTasks, task_id: uuid.UUID) -> None:
    if settings.async_mode == "celery":
        from app.ai.tasks import celery_aigc_generate

        celery_aigc_generate.apply_async(
            args=[str(task_id)],
            queue=settings.celery_aigc_queue,
        )
    else:
        background_tasks.add_task(_run_aigc_background, str(task_id))


def _compensate_enqueue_failure(db: Session, task_id: uuid.UUID, exc: Exception) -> None:
    mark_aigc_task_failed(
        db,
        task_id,
        error_code=_ENQUEUE_ERROR_CODE,
        error_message=str(exc),
    )
    db.commit()


def _enqueue_aigc_generation_or_502(
    *,
    db: Session,
    background_tasks: BackgroundTasks,
    task_id: uuid.UUID,
) -> None:
    try:
        _enqueue_aigc_generation(background_tasks, task_id)
    except Exception as exc:
        _compensate_enqueue_failure(db, task_id, exc)
        raise HTTPException(status_code=502, detail="Failed to enqueue AIGC generation") from exc


@router.post("/tasks", response_model=AigcTaskOut, status_code=201)
def create_task(
    body: AigcTaskCreateIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    task = create_aigc_task(db, user=user, body=body)
    db.commit()
    db.refresh(task)
    _enqueue_aigc_generation_or_502(db=db, background_tasks=background_tasks, task_id=task.id)
    db.refresh(task)
    return task


def _run_aigc_background(task_id: str):
    from app.database import SessionLocal
    from app.aigc.service import run_aigc_generation, mark_aigc_task_failed

    db = SessionLocal()
    try:
        run_aigc_generation(db, uuid.UUID(task_id))
        db.commit()
    except Exception:
        db.rollback()
        try:
            mark_aigc_task_failed(db, uuid.UUID(task_id), error_code="GENERATION_FAILED")
            db.commit()
        except Exception:
            db.rollback()
        raise
    finally:
        db.close()


@router.get("/tasks", response_model=list[AigcTaskOut])
def get_tasks(
    status: AigcTaskStatus | None = None,
    product_id: uuid.UUID | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor, UserRole.viewer)),
):
    tasks = list_aigc_tasks(db, status=status, product_id=product_id, limit=limit, offset=offset)
    db.commit()
    return tasks


@router.get("/tasks/{task_id}", response_model=AigcTaskOut)
def get_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor, UserRole.viewer)),
):
    task = get_aigc_task(db, task_id, normalize_empty=True)
    db.commit()
    return task


@router.post("/tasks/{task_id}/approve", response_model=AigcTaskOut)
def approve_task(
    task_id: uuid.UUID,
    body: AigcApproveIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    task = approve_aigc_task(
        db,
        task_id=task_id,
        selected_candidate_id=body.selected_candidate_id,
        target_asset_type=body.target_asset_type,
        reviewer=user,
    )
    db.commit()
    db.refresh(task)
    return task


@router.post("/tasks/{task_id}/reject", response_model=AigcTaskOut)
def reject_task(
    task_id: uuid.UUID,
    body: AigcRejectIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    task = reject_aigc_task(db, task_id=task_id, reason=body.reason, reviewer=user)
    db.commit()
    db.refresh(task)
    return task


@router.post("/candidates/{candidate_id}/optimize", response_model=AigcTaskOut, status_code=201)
def optimize_candidate(
    candidate_id: uuid.UUID,
    body: AigcOptimizeCreateIn,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    task = create_aigc_optimization_task(db, candidate_id=candidate_id, user=user, body=body)
    db.commit()
    db.refresh(task)
    _enqueue_aigc_generation_or_502(db=db, background_tasks=background_tasks, task_id=task.id)
    db.refresh(task)
    return task


@router.post("/candidates/{candidate_id}/feedback", status_code=201)
def submit_feedback(
    candidate_id: uuid.UUID,
    body: AigcCandidateFeedbackIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    feedback = add_candidate_feedback(db, candidate_id=candidate_id, user=user, body=body)
    db.commit()
    db.refresh(feedback)
    return {"id": str(feedback.id), "candidate_id": str(feedback.candidate_id)}


@router.get("/providers", response_model=list[AigcProviderOut])
def providers(
    _: User = Depends(require_role(UserRole.admin, UserRole.editor, UserRole.viewer)),
):
    return list_available_providers()


@router.get("/candidates/{candidate_id}/file")
def get_candidate_file(
    candidate_id: uuid.UUID,
    kind: str = Query(default="thumb", pattern="^(thumb|original)$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user_with_query_token),
):
    candidate = db.get(AigcTaskCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="candidate not found")

    uri = candidate.thumb_uri if kind == "thumb" else candidate.image_uri
    if not uri:
        raise HTTPException(status_code=404, detail=f"candidate {kind} uri not available")

    if uri.startswith("http://") or uri.startswith("https://"):
        return RedirectResponse(url=uri)

    try:
        content = get_storage().get_object(uri_to_key(uri))
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to read candidate object")

    media_type = mimetypes.guess_type(uri)[0] or "application/octet-stream"
    return Response(content=content, media_type=media_type)
