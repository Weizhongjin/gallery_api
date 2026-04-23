import base64
import time
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.aigc.models import (
    AigcAuthorizationLog,
    AigcCandidateFeedback,
    AigcPromptLog,
    AigcPromptTemplate,
    AigcPromptTemplateStatus,
    AigcPromptTemplateVersion,
    AigcTask,
    AigcTaskCandidate,
    AigcTaskStatus,
)
from app.aigc.schemas import AigcCandidateFeedbackIn, AigcOptimizeCreateIn, AigcTaskCreateIn
from app.assets.models import Asset, AssetProduct, AssetProductRole, AssetType
from app.auth.models import User
from app.config import settings
from app.storage import get_storage, uri_to_key

_FALLBACK_PROMPT = "virtual try-on"
_EMPTY_RESULT_ERROR = "AIGC provider returned no images"
_GENERATION_ERROR_CODE = "GENERATION_PROVIDER_ERROR"
_EMPTY_GENERATION_RESULT_CODE = "EMPTY_GENERATION_RESULT"
_OPTIMIZE_QUALITY_BASELINE = (
    "优化质量要求：突出服装纹理，保证脸部自然清晰，修复手部结构，保持鞋子完整真实，"
    "确保配饰细节准确协调。"
)

_AIGC_PRODUCT_ROLE_PRIORITY: dict[AssetProductRole, int] = {
    AssetProductRole.flatlay_primary: 0,
    AssetProductRole.manual: 1,
    AssetProductRole.model_ref: 2,
    AssetProductRole.advertising_ref: 3,
}


def _list_product_ids_from_flatlay(db: Session, flatlay_asset_id: uuid.UUID) -> list[uuid.UUID]:
    rows = (
        db.query(AssetProduct.product_id, AssetProduct.relation_role)
        .filter(AssetProduct.asset_id == flatlay_asset_id)
        .all()
    )
    if not rows:
        return []
    rows.sort(key=lambda x: (_AIGC_PRODUCT_ROLE_PRIORITY.get(x[1], 99), str(x[0])))
    return [row[0] for row in rows]


def create_aigc_task(db: Session, *, user: User, body: AigcTaskCreateIn) -> AigcTask:
    flatlay_asset = db.get(Asset, body.flatlay_asset_id)
    if not flatlay_asset:
        raise HTTPException(status_code=404, detail="flatlay asset not found")
    linked_product_ids = _list_product_ids_from_flatlay(db, body.flatlay_asset_id)
    if not linked_product_ids:
        raise HTTPException(status_code=422, detail="flatlay asset is not bound to any product")
    if body.product_id not in linked_product_ids:
        raise HTTPException(status_code=422, detail="product_id must match flatlay-linked product")

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

    default_template_id = (
        db.query(AigcPromptTemplate.id)
        .filter(
            AigcPromptTemplate.is_default.is_(True),
            AigcPromptTemplate.status == AigcPromptTemplateStatus.active,
        )
        .first()
    )
    default_template_id = default_template_id[0] if default_template_id else None

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
        template_id=default_template_id,
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


def create_aigc_optimization_task(
    db: Session,
    *,
    candidate_id: uuid.UUID,
    user: User,
    body: AigcOptimizeCreateIn,
) -> AigcTask:
    candidate = db.get(AigcTaskCandidate, candidate_id)
    if not candidate:
        raise HTTPException(status_code=404, detail="candidate not found")

    source_task = db.get(AigcTask, candidate.task_id)
    if not source_task:
        raise HTTPException(status_code=404, detail="source task not found")
    if source_task.status not in {AigcTaskStatus.review_pending, AigcTaskStatus.approved}:
        raise HTTPException(
            status_code=409,
            detail="source task must be in review_pending or approved status",
        )

    reference_uri = candidate.image_uri or candidate.thumb_uri
    if not reference_uri:
        raise HTTPException(status_code=422, detail="candidate has no image available for optimization")

    workflow_type = "optimize_custom" if body.mode == "custom" else "optimize_auto"

    task = AigcTask(
        product_id=source_task.product_id,
        flatlay_asset_id=source_task.flatlay_asset_id,
        flatlay_original_uri=source_task.flatlay_original_uri,
        reference_source="upload",
        reference_asset_id=None,
        reference_original_uri=None,
        reference_upload_uri=reference_uri,
        workflow_type=workflow_type,
        source_task_id=source_task.id,
        source_candidate_id=candidate.id,
        optimize_prompt=body.custom_prompt if body.mode == "custom" else None,
        face_deidentify_enabled=source_task.face_deidentify_enabled,
        candidate_count=body.candidate_count,
        template_id=source_task.template_id,
        template_version=source_task.template_version,
        provider=source_task.provider,
        model_name=source_task.model_name,
        provider_profile=source_task.provider_profile,
        timeout_seconds=source_task.timeout_seconds,
        created_by=user.id,
    )
    db.add(task)
    db.flush()
    return task


def get_aigc_task(
    db: Session,
    task_id: uuid.UUID,
    *,
    normalize_empty: bool = False,
) -> AigcTask:
    if normalize_empty:
        _normalize_empty_review_pending_tasks(db, task_id=task_id)
    task = (
        db.query(AigcTask)
        .options(selectinload(AigcTask.candidates))
        .filter(AigcTask.id == task_id)
        .first()
    )
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
    if status in {None, AigcTaskStatus.review_pending, AigcTaskStatus.failed}:
        _normalize_empty_review_pending_tasks(db, product_id=product_id)
    q = db.query(AigcTask).options(selectinload(AigcTask.candidates))
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


def mark_aigc_task_failed(
    db: Session,
    task_id: uuid.UUID,
    error_code: str,
    *,
    error_message: str | None = None,
) -> None:
    task = db.get(AigcTask, task_id)
    if task:
        task.status = AigcTaskStatus.failed
        task.error_code = error_code
        if error_message is not None:
            task.error_message = error_message


def run_aigc_generation(db: Session, task_id: uuid.UUID) -> None:
    from app.aigc.provider_registry import get_provider

    task = db.get(AigcTask, task_id)
    if not task:
        return

    task.status = AigcTaskStatus.running
    # Persist "running" immediately so UI won't keep showing "queued"
    # during a long provider call.
    db.commit()

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

    base_prompt, prompt_template_id, prompt_template_version = _resolve_task_prompt(db, task)
    prompt = _compose_effective_prompt(task, base_prompt)

    provider = get_provider(task.provider, settings)
    resolution = "2K"
    target_count = _normalize_target_candidate_count(task.candidate_count)
    request_payload = _build_generation_request_payload(
        provider=provider,
        prompt=prompt,
        image_data_urls=image_data_urls,
        resolution=resolution,
        target_count=target_count,
    )
    generation_started_at = time.monotonic()
    generation_meta: dict = {
        "target_candidate_count": target_count,
        "timeout_seconds": task.timeout_seconds,
        "attempts": [],
    }

    try:
        images = _generate_images_with_topup(
            provider=provider,
            prompt=prompt,
            image_data_urls=image_data_urls,
            resolution=resolution,
            target_count=target_count,
            timeout_seconds=task.timeout_seconds,
            attempts_meta=generation_meta["attempts"],
        )
    except Exception as exc:
        task.status = AigcTaskStatus.failed
        task.error_code = _GENERATION_ERROR_CODE
        task.error_message = str(exc)
        generation_meta["generated_candidate_count"] = 0
        generation_meta["error_code"] = _GENERATION_ERROR_CODE
        generation_meta["error_message"] = str(exc)
        generation_meta["total_elapsed_ms"] = int((time.monotonic() - generation_started_at) * 1000)
        _save_prompt_log(
            db=db,
            task_id=task.id,
            template_id=prompt_template_id,
            template_version=prompt_template_version,
            prompt=prompt,
            request_payload=request_payload,
            response_meta=generation_meta,
        )
        return

    if not images:
        task.status = AigcTaskStatus.failed
        task.error_code = _EMPTY_GENERATION_RESULT_CODE
        task.error_message = _EMPTY_RESULT_ERROR
        generation_meta["generated_candidate_count"] = 0
        generation_meta["error_code"] = _EMPTY_GENERATION_RESULT_CODE
        generation_meta["error_message"] = _EMPTY_RESULT_ERROR
        generation_meta["total_elapsed_ms"] = int((time.monotonic() - generation_started_at) * 1000)
        _save_prompt_log(
            db=db,
            task_id=task.id,
            template_id=prompt_template_id,
            template_version=prompt_template_version,
            prompt=prompt,
            request_payload=request_payload,
            response_meta=generation_meta,
        )
        return

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

    generation_meta["generated_candidate_count"] = len(images)
    generation_meta["partial_result"] = len(images) < target_count
    generation_meta["total_elapsed_ms"] = int((time.monotonic() - generation_started_at) * 1000)
    _save_prompt_log(
        db=db,
        task_id=task.id,
        template_id=prompt_template_id,
        template_version=prompt_template_version,
        prompt=prompt,
        request_payload=request_payload,
        response_meta=generation_meta,
    )
    task.status = AigcTaskStatus.review_pending


def _bytes_to_data_url(data: bytes) -> str:
    b64 = base64.b64encode(data).decode()
    return f"data:image/jpeg;base64,{b64}"


def _resolve_task_prompt(
    db: Session,
    task: AigcTask,
) -> tuple[str, uuid.UUID | None, int | None]:
    # Prefer explicit template/version on task.
    if task.template_id:
        row = (
            db.query(AigcPromptTemplateVersion)
            .filter(
                AigcPromptTemplateVersion.template_id == task.template_id,
                AigcPromptTemplateVersion.version == task.template_version,
            )
            .first()
        )
        if row and row.content:
            return row.content, task.template_id, task.template_version

    # Fallback to current default published template.
    default_tpl = (
        db.query(AigcPromptTemplate)
        .filter(
            AigcPromptTemplate.is_default.is_(True),
            AigcPromptTemplate.status == AigcPromptTemplateStatus.active,
        )
        .first()
    )
    if default_tpl:
        row = (
            db.query(AigcPromptTemplateVersion)
            .filter(
                AigcPromptTemplateVersion.template_id == default_tpl.id,
                AigcPromptTemplateVersion.version == task.template_version,
            )
            .first()
        )
        if row and row.content:
            if not task.template_id:
                task.template_id = default_tpl.id
            return row.content, default_tpl.id, task.template_version

    # Last fallback keeps previous behavior.
    return _FALLBACK_PROMPT, None, task.template_version


def _compose_effective_prompt(task: AigcTask, base_prompt: str) -> str:
    prompt_parts = [base_prompt.strip()]
    if task.workflow_type in {"optimize_auto", "optimize_custom"}:
        prompt_parts.append(_OPTIMIZE_QUALITY_BASELINE)
    if task.workflow_type == "optimize_custom" and task.optimize_prompt:
        prompt_parts.append(task.optimize_prompt.strip())
    return "\n\n".join(part for part in prompt_parts if part)


def _normalize_empty_review_pending(task: AigcTask) -> None:
    if task.status != AigcTaskStatus.review_pending:
        return
    if task.candidates:
        return
    task.status = AigcTaskStatus.failed
    if not task.error_code:
        task.error_code = _EMPTY_GENERATION_RESULT_CODE
    if not task.error_message:
        task.error_message = _EMPTY_RESULT_ERROR


def _normalize_empty_review_pending_tasks(
    db: Session,
    *,
    task_id: uuid.UUID | None = None,
    product_id: uuid.UUID | None = None,
) -> int:
    q = (
        db.query(AigcTask)
        .outerjoin(AigcTaskCandidate, AigcTaskCandidate.task_id == AigcTask.id)
        .filter(
            AigcTask.status == AigcTaskStatus.review_pending,
            AigcTaskCandidate.id.is_(None),
        )
    )
    if task_id:
        q = q.filter(AigcTask.id == task_id)
    if product_id:
        q = q.filter(AigcTask.product_id == product_id)

    tasks = q.all()
    for task in tasks:
        task.status = AigcTaskStatus.failed
        if not task.error_code:
            task.error_code = _EMPTY_GENERATION_RESULT_CODE
        if not task.error_message:
            task.error_message = _EMPTY_RESULT_ERROR

    if tasks:
        db.flush()
    return len(tasks)


def _normalize_target_candidate_count(raw_count: int | None) -> int:
    if raw_count is None:
        return max(1, settings.aigc_default_candidate_count)
    return max(1, int(raw_count))


def _build_generation_request_payload(
    *,
    provider,
    prompt: str,
    image_data_urls: list[str],
    resolution: str,
    target_count: int,
) -> dict:
    provider_payload: dict | str
    if hasattr(provider, "build_request_payload"):
        payload = provider.build_request_payload(
            prompt=prompt,
            image_data_urls=image_data_urls,
            resolution=resolution,
            candidate_count=target_count,
        )
        provider_payload = payload if isinstance(payload, dict) else repr(payload)
    else:
        provider_payload = {
            "prompt": prompt,
            "resolution": resolution,
            "candidate_count": target_count,
            "input_image_count": len(image_data_urls),
        }
    return {
        "prompt": prompt,
        "resolution": resolution,
        "target_candidate_count": target_count,
        "input_image_count": len(image_data_urls),
        "strategy": "top_up_until_target_or_timeout",
        "provider_payload": provider_payload,
    }


def _generate_images_with_topup(
    *,
    provider,
    prompt: str,
    image_data_urls: list[str],
    resolution: str,
    target_count: int,
    timeout_seconds: int,
    attempts_meta: list[dict],
) -> list[bytes]:
    images: list[bytes] = []
    start = time.monotonic()
    deadline = start + max(1, timeout_seconds)
    max_attempts = max(1, target_count)

    for attempt_no in range(1, max_attempts + 1):
        if len(images) >= target_count:
            break
        if attempt_no > 1 and time.monotonic() >= deadline:
            attempts_meta.append(
                {
                    "attempt_no": attempt_no,
                    "requested_candidate_count": target_count - len(images),
                    "returned_candidate_count": 0,
                    "timed_out_before_call": True,
                }
            )
            break

        requested_count = target_count - len(images)
        call_started_at = time.monotonic()
        batch = provider.generate(
            prompt=prompt,
            image_data_urls=image_data_urls,
            resolution=resolution,
            candidate_count=requested_count,
        )
        elapsed_ms = int((time.monotonic() - call_started_at) * 1000)
        returned_count = len(batch)
        attempts_meta.append(
            {
                "attempt_no": attempt_no,
                "requested_candidate_count": requested_count,
                "returned_candidate_count": returned_count,
                "elapsed_ms": elapsed_ms,
            }
        )
        if returned_count == 0:
            break
        images.extend(batch)

    return images[:target_count]


def _save_prompt_log(
    *,
    db: Session,
    task_id: uuid.UUID,
    template_id: uuid.UUID | None,
    template_version: int | None,
    prompt: str,
    request_payload: dict,
    response_meta: dict,
) -> None:
    prompt_log = AigcPromptLog(
        task_id=task_id,
        template_id=template_id,
        template_version=template_version,
        user_prompt=prompt,
        request_payload_json=request_payload,
        response_meta_json=response_meta,
    )
    db.add(prompt_log)
