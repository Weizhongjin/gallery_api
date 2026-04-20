import base64
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.aigc.models import (
    AigcAuthorizationLog,
    AigcCandidateFeedback,
    AigcPromptLog,
    AigcPromptTemplate,
    AigcPromptTemplateVersion,
    AigcTask,
    AigcTaskCandidate,
    AigcTaskStatus,
)
from app.aigc.schemas import AigcCandidateFeedbackIn, AigcTaskCreateIn
from app.assets.models import Asset, AssetType
from app.auth.models import User
from app.config import settings
from app.storage import get_storage, uri_to_key


def create_aigc_task(db: Session, *, user: User, body: AigcTaskCreateIn) -> AigcTask:
    flatlay_asset = db.get(Asset, body.flatlay_asset_id)
    if not flatlay_asset:
        raise HTTPException(status_code=404, detail="flatlay asset not found")

    if body.reference_source == "library":
        if not body.reference_asset_id:
            raise HTTPException(status_code=422, detail="reference_asset_id required for library source")
        ref_asset = db.get(Asset, body.reference_asset_id)
        if not ref_asset:
            raise HTTPException(status_code=404, detail="reference asset not found")
        reference_original_uri = ref_asset.original_uri
        reference_upload_uri = None
    elif body.reference_source == "upload":
        if not body.reference_upload_uri:
            raise HTTPException(status_code=422, detail="reference_upload_uri required for upload source")
        reference_original_uri = None
        reference_upload_uri = body.reference_upload_uri
    else:
        raise HTTPException(status_code=422, detail="invalid reference_source")

    task = AigcTask(
        product_id=body.product_id,
        flatlay_asset_id=body.flatlay_asset_id,
        flatlay_original_uri=flatlay_asset.original_uri,
        reference_source=body.reference_source,
        reference_asset_id=body.reference_asset_id,
        reference_original_uri=reference_original_uri,
        reference_upload_uri=reference_upload_uri,
        face_deidentify_enabled=body.face_deidentify_enabled,
        candidate_count=body.candidate_count,
        template_version=body.template_version,
        provider=settings.aigc_default_provider,
        model_name=settings.aigc_model_name,
        timeout_seconds=settings.aigc_soft_timeout_seconds,
        created_by=user.id,
    )
    db.add(task)
    db.flush()

    auth_log = AigcAuthorizationLog(
        task_id=task.id,
        uploader_user_id=user.id,
        consent_text_version="v1",
        consent_checked=body.consent_checked,
    )
    db.add(auth_log)
    db.flush()

    return task


def get_aigc_task(db: Session, task_id: uuid.UUID) -> AigcTask:
    task = db.get(AigcTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="AIGC task not found")
    return task


def list_aigc_tasks(
    db: Session,
    *,
    status: AigcTaskStatus | None = None,
    product_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AigcTask]:
    q = db.query(AigcTask)
    if status:
        q = q.filter(AigcTask.status == status)
    if product_id:
        q = q.filter(AigcTask.product_id == product_id)
    q = q.order_by(AigcTask.created_at.desc())
    return q.offset(offset).limit(limit).all()


def approve_aigc_task(
    db: Session,
    *,
    task_id: uuid.UUID,
    selected_candidate_id: uuid.UUID,
    target_asset_type: AssetType,
    reviewer: User,
) -> AigcTask:
    task = get_aigc_task(db, task_id)

    if task.status != AigcTaskStatus.review_pending:
        raise HTTPException(status_code=409, detail="task is not in review_pending status")

    candidate = db.get(AigcTaskCandidate, selected_candidate_id)
    if not candidate or candidate.task_id != task.id:
        raise HTTPException(status_code=404, detail="candidate not found in this task")

    candidate.is_selected = True

    storage = get_storage()

    image_uri = candidate.image_uri
    thumb_uri = candidate.thumb_uri

    new_asset = Asset(
        original_uri=image_uri or "",
        display_uri=image_uri or "",
        thumb_uri=thumb_uri or "",
        filename=f"aigc_{task.id}_{candidate.seq_no}.jpg",
        width=candidate.width or 1024,
        height=candidate.height or 1536,
        file_size=candidate.file_size or 0,
        feature_status={},
        asset_type=target_asset_type,
        is_ai_generated=True,
    )
    db.add(new_asset)
    db.flush()

    from app.assets.models import AssetProduct, AssetProductRole
    asset_product = AssetProduct(
        asset_id=new_asset.id,
        product_id=task.product_id,
        relation_role=AssetProductRole.manual,
    )
    db.add(asset_product)

    task.status = AigcTaskStatus.approved
    task.reviewed_by = reviewer.id
    task.reviewed_at = datetime.now(timezone.utc)
    db.flush()

    return task


def reject_aigc_task(
    db: Session,
    *,
    task_id: uuid.UUID,
    reason: str | None,
    reviewer: User,
) -> AigcTask:
    task = get_aigc_task(db, task_id)

    if task.status != AigcTaskStatus.review_pending:
        raise HTTPException(status_code=409, detail="task is not in review_pending status")

    task.status = AigcTaskStatus.rejected
    task.reviewed_by = reviewer.id
    task.reviewed_at = datetime.now(timezone.utc)
    task.error_message = reason
    db.flush()

    return task


def add_candidate_feedback(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    user: User,
    body: AigcCandidateFeedbackIn,
) -> AigcCandidateFeedback:
    candidate = db.get(AigcTaskCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="candidate not found")

    feedback = AigcCandidateFeedback(
        candidate_id=candidate_id,
        score=body.score,
        comment=body.comment,
        user_id=user.id,
    )
    db.add(feedback)
    db.flush()
    return feedback


def mark_aigc_task_failed(db: Session, task_id: uuid.UUID, error_code: str) -> None:
    task = db.get(AigcTask, task_id)
    if task:
        task.status = AigcTaskStatus.failed
        task.error_code = error_code


def run_aigc_generation(db: Session, task_id: uuid.UUID) -> None:
    from app.aigc.provider_registry import get_provider

    task = db.get(AigcTask, task_id)
    if not task:
        return

    task.status = AigcTaskStatus.running
    db.flush()

    storage = get_storage()

    image_data_urls: list[str] = []
    if task.reference_original_uri:
        ref_bytes = storage.get_object(uri_to_key(task.reference_original_uri))
        image_data_urls.append(_bytes_to_data_url(ref_bytes))
    if task.reference_upload_uri:
        ref_bytes = storage.get_object(uri_to_key(task.reference_upload_uri))
        image_data_urls.append(_bytes_to_data_url(ref_bytes))

    flat_bytes = storage.get_object(uri_to_key(task.flatlay_original_uri))
    image_data_urls.append(_bytes_to_data_url(flat_bytes))

    provider = get_provider(task.provider, settings)
    images = provider.generate(
        prompt="virtual try-on",
        image_data_urls=image_data_urls,
        resolution="2K",
    )

    for idx, img_bytes in enumerate(images):
        suffix = f"aigc_{task.id}_{idx + 1}.jpg"
        uri = storage.upload(f"aigc/{suffix}", img_bytes, content_type="image/jpeg")
        thumb_suffix = f"aigc_{task.id}_{idx + 1}_thumb.jpg"
        thumb_uri = storage.upload(f"aigc/thumb_{thumb_suffix}", img_bytes, content_type="image/jpeg")

        candidate = AigcTaskCandidate(
            task_id=task.id,
            seq_no=idx + 1,
            image_uri=uri,
            thumb_uri=thumb_uri,
            width=1024,
            height=1536,
            file_size=len(img_bytes),
        )
        db.add(candidate)

    prompt_log = AigcPromptLog(
        task_id=task.id,
        template_version=task.template_version,
        user_prompt="virtual try-on",
    )
    db.add(prompt_log)

    task.status = AigcTaskStatus.review_pending


def _bytes_to_data_url(data: bytes) -> str:
    b64 = base64.b64encode(data).decode()
    return f"data:image/jpeg;base64,{b64}"
