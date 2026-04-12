import asyncio
import hashlib
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session

from app.assets.models import (
    Asset,
    AssetProduct,
    AssetProductRole,
    AssetType,
    ImageGroup,
    ParseStatus,
    Product,
)
from app.image_processing import process_image
from app.storage import get_storage

_GROUP_CODE_RE = re.compile(r"^[A-Za-z]\d{3,}[A-Za-z0-9_-]*$")
_PRODUCT_TOKEN_RE = re.compile(r"(?:[A-Z]\d{5,}[A-Z]?|\d{8}[A-Z]?)", re.IGNORECASE)
_SINGLE_DIGIT_FOLDER_RE = re.compile(r"^\d$")
_FILENAME_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,}$", re.IGNORECASE)


def _derive_group_from_key(key: str, fallback_prefix: str) -> tuple[str, str]:
    """
    Derive logical group path/name from an object key.

    Rules:
    - Prefer file parent directory as group path.
    - If any path segment matches style-like code (A*** / B*** ...),
      use the last matched segment as group name.
    - Fallback to parent folder basename, then prefix basename.
    """
    normalized = (key or "").strip().strip("/")
    fallback = (fallback_prefix or "").strip().strip("/") or "default"

    if not normalized:
        return fallback, fallback.split("/")[-1] or "default"

    if "/" in normalized:
        group_path = normalized.rsplit("/", 1)[0]
    else:
        group_path = fallback

    parts = [p for p in group_path.split("/") if p]
    code_like = [p for p in parts if _GROUP_CODE_RE.match(p)]
    if code_like:
        group_name = code_like[-1].upper()
    elif parts:
        group_name = parts[-1]
    else:
        group_name = fallback.split("/")[-1] or "default"

    return group_path, group_name


def _extract_product_codes(text: str) -> list[str]:
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for tok in _PRODUCT_TOKEN_RE.findall(text.upper()):
        if tok not in seen:
            seen.add(tok)
            out.append(tok)
    return out


def _build_group_tempuid(dataset: str, category: str, folder: str) -> str:
    seed = f"{dataset}/{category}/{folder}".encode("utf-8")
    digest = hashlib.md5(seed).hexdigest()[:8].upper()
    return f"TMPUID-GRP-{folder}-{digest}"


def _fallback_code_from_name(name: str) -> str | None:
    token = (name or "").strip().upper()
    if not token:
        return None
    if not _FILENAME_CODE_RE.fullmatch(token):
        return None
    # Avoid tiny pure-number camera indices like 1/2/12.
    if token.isdigit() and len(token) < 5:
        return None
    return token


def _infer_asset_type(dataset: str) -> AssetType:
    ds = (dataset or "").strip()
    if "广告" in ds:
        return AssetType.advertising
    if "平铺图" in ds:
        return AssetType.flatlay
    if "季图片" in ds:
        return AssetType.model_set
    return AssetType.unknown


def _split_rel_from_prefix(key: str, prefix: str) -> str:
    k = (key or "").strip().strip("/")
    p = (prefix or "").strip().strip("/")
    if p and k.startswith(p + "/"):
        return k[len(p) + 1:]
    return k


def _infer_from_storage_key(key: str, prefix: str) -> tuple[AssetType, str | None, str | None, ParseStatus, list[str]]:
    rel = _split_rel_from_prefix(key, prefix)
    parts = [x for x in rel.split("/") if x]
    if not parts:
        return AssetType.unknown, None, rel or None, ParseStatus.unresolved, []

    dataset = parts[0]
    asset_type = _infer_asset_type(dataset)
    filename = parts[-1]
    stem = filename.rsplit(".", 1)[0]

    product_codes: list[str] = []
    if asset_type == AssetType.flatlay:
        product_codes = _extract_product_codes(stem)
        if not product_codes:
            fallback = _fallback_code_from_name(stem)
            if fallback:
                product_codes = [fallback]
    elif asset_type == AssetType.advertising:
        # Expected: dataset/category/product-folder/image.jpg
        category = parts[1] if len(parts) >= 3 else ""
        product_folder = parts[2] if len(parts) >= 4 else ""
        if category == "套装" and _SINGLE_DIGIT_FOLDER_RE.fullmatch(product_folder):
            product_codes = [_build_group_tempuid(dataset, category, product_folder)]
        else:
            product_codes = _extract_product_codes(product_folder)
            if not product_codes:
                fallback = _fallback_code_from_name(product_folder)
                if fallback:
                    product_codes = [fallback]
    elif asset_type == AssetType.model_set:
        # Expected: dataset/product-folder/image.jpg
        product_folder = parts[1] if len(parts) >= 3 else ""
        product_codes = _extract_product_codes(product_folder)
        if not product_codes:
            fallback_folder = _fallback_code_from_name(product_folder)
            if fallback_folder:
                product_codes = [fallback_folder]
        if not product_codes:
            product_codes = _extract_product_codes(stem)
        if not product_codes:
            fallback_stem = _fallback_code_from_name(stem)
            if fallback_stem:
                product_codes = [fallback_stem]
    else:
        # Fallback for unknown datasets: parse from filename and parent dir.
        product_codes = _extract_product_codes(stem)
        if not product_codes and len(parts) >= 2:
            product_codes = _extract_product_codes(parts[-2])
        if not product_codes:
            fallback = _fallback_code_from_name(stem)
            if fallback:
                product_codes = [fallback]

    parse_status = ParseStatus.parsed if product_codes else ParseStatus.unresolved
    return asset_type, dataset, rel or None, parse_status, product_codes


def _upsert_product_by_code(db: Session, product_code: str) -> Product:
    code = (product_code or "").strip().upper()
    product = db.query(Product).filter(Product.product_code == code).first()
    if product:
        return product
    product = Product(product_code=code)
    db.add(product)
    db.flush()
    return product


def _relation_role_for_asset_type(asset_type: AssetType) -> AssetProductRole:
    if asset_type == AssetType.flatlay:
        return AssetProductRole.flatlay_primary
    if asset_type == AssetType.advertising:
        return AssetProductRole.advertising_ref
    if asset_type == AssetType.model_set:
        return AssetProductRole.model_ref
    return AssetProductRole.manual


def upload_asset(db: Session, filename: str, data: bytes) -> Asset:
    variants = process_image(data)
    storage = get_storage()

    key_base = f"assets/{uuid.uuid4()}"
    original_uri = storage.upload(f"{key_base}/original/{filename}", data, "image/jpeg")
    display_uri = storage.upload(f"{key_base}/display/{filename}", variants.display, "image/jpeg")
    thumb_uri = storage.upload(f"{key_base}/thumb/{filename}", variants.thumb, "image/jpeg")

    asset = Asset(
        original_uri=original_uri,
        display_uri=display_uri,
        thumb_uri=thumb_uri,
        filename=filename,
        width=variants.original_width,
        height=variants.original_height,
        file_size=len(data),
        feature_status={"classify": "pending", "embed": "pending"},
        asset_type=AssetType.unknown,
        parse_status=ParseStatus.unresolved,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def patch_human_tags(db: Session, asset_id: uuid.UUID, add: list[uuid.UUID], remove: list[uuid.UUID]):
    from app.assets.models import AssetTag, TagSource
    asset = db.get(Asset, asset_id)
    if not asset:
        return None

    if remove:
        db.query(AssetTag).filter(
            AssetTag.asset_id == asset_id,
            AssetTag.node_id.in_(remove),
            AssetTag.source == TagSource.human,
        ).delete(synchronize_session=False)

    for node_id in add:
        existing = db.query(AssetTag).filter(
            AssetTag.asset_id == asset_id,
            AssetTag.node_id == node_id,
        ).first()
        if not existing:
            db.add(AssetTag(asset_id=asset_id, node_id=node_id, source=TagSource.human))

    db.commit()
    try:
        from app.products.service import rebuild_product_tags_for_asset
        rebuild_product_tags_for_asset(db, asset_id)
        db.commit()
    except Exception:
        # Keep tag patch robust; product aggregation can be triggered later if needed.
        pass
    db.refresh(asset)
    return asset


def get_asset_tags(db: Session, asset_id: uuid.UUID) -> list:
    from app.assets.models import AssetTag
    return db.query(AssetTag).filter(AssetTag.asset_id == asset_id).all()


def list_assets_filtered(
    db: Session,
    tag_ids: list[uuid.UUID],
    page: int,
    page_size: int,
    asset_type: AssetType | None = None,
    product_code: str | None = None,
) -> list[Asset]:
    from app.assets.models import AssetTag
    query = db.query(Asset)
    for node_id in tag_ids:
        sub = db.query(AssetTag.asset_id).filter(AssetTag.node_id == node_id).scalar_subquery()
        query = query.filter(Asset.id.in_(sub))
    if asset_type:
        query = query.filter(Asset.asset_type == asset_type)
    if product_code:
        code = product_code.strip().upper()
        query = query.join(AssetProduct, AssetProduct.asset_id == Asset.id).join(
            Product, Product.id == AssetProduct.product_id
        ).filter(Product.product_code == code).distinct()
    return query.order_by(Asset.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()


def list_asset_products(db: Session, asset_id: uuid.UUID) -> list[dict]:
    rows = (
        db.query(Product, AssetProduct)
        .join(AssetProduct, AssetProduct.product_id == Product.id)
        .filter(AssetProduct.asset_id == asset_id)
        .all()
    )
    return [
        {
            "product_code": p.product_code,
            "relation_role": ap.relation_role.value,
            "source": ap.source,
            "confidence": ap.confidence,
        }
        for p, ap in rows
    ]


def bind_asset_to_product(
    db: Session,
    asset_id: uuid.UUID,
    product_code: str,
    relation_role: AssetProductRole = AssetProductRole.manual,
    source: str = "manual",
) -> dict | None:
    asset = db.get(Asset, asset_id)
    if not asset:
        return None

    product = _upsert_product_by_code(db, product_code)
    link = (
        db.query(AssetProduct)
        .filter(AssetProduct.asset_id == asset_id, AssetProduct.product_id == product.id)
        .first()
    )
    if not link:
        link = AssetProduct(
            asset_id=asset_id,
            product_id=product.id,
            relation_role=relation_role,
            source=source,
        )
        db.add(link)
    else:
        link.relation_role = relation_role
        link.source = source

    db.commit()
    try:
        from app.products.service import rebuild_product_tags_for_product
        rebuild_product_tags_for_product(db, product.id)
        db.commit()
    except Exception:
        pass
    return {
        "asset_id": str(asset_id),
        "product_code": product.product_code,
        "relation_role": link.relation_role.value,
        "source": link.source,
    }


def unbind_asset_product(db: Session, asset_id: uuid.UUID, product_code: str) -> bool:
    code = (product_code or "").strip().upper()
    product = db.query(Product).filter(Product.product_code == code).first()
    if not product:
        return False
    link = (
        db.query(AssetProduct)
        .filter(AssetProduct.asset_id == asset_id, AssetProduct.product_id == product.id)
        .first()
    )
    if not link:
        return False
    db.delete(link)
    db.commit()
    try:
        from app.products.service import rebuild_product_tags_for_product
        rebuild_product_tags_for_product(db, product.id)
        db.commit()
    except Exception:
        pass
    return True


import uuid as _uuid


def _run_classify_standalone(asset_id: str) -> None:
    """Open own session, run VLM classification, commit. Safe to run in a thread."""
    from app.database import SessionLocal
    from app.ai.vlm_client import get_vlm_client
    from app.ai.processing import classify_asset

    db = SessionLocal()
    try:
        asset = db.get(Asset, _uuid.UUID(asset_id))
        if asset:
            classify_asset(db, asset, get_vlm_client(), get_storage())
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _run_embed_standalone(asset_id: str) -> None:
    """Open own session, generate embedding, commit. Safe to run in a thread."""
    from app.database import SessionLocal
    from app.ai.embed_client import get_embedding_client
    from app.ai.processing import embed_asset

    db = SessionLocal()
    try:
        asset = db.get(Asset, _uuid.UUID(asset_id))
        if asset:
            embed_asset(db, asset, get_embedding_client(), get_storage())
            db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def _process_asset_parallel(asset_id: str, stages: list[str]) -> None:
    """Run classify and embed concurrently in a thread pool.

    Each stage gets its own DB session. VLM (slow) and embedding (fast)
    are dispatched simultaneously — neither waits for the other.
    """
    loop = asyncio.get_running_loop()
    with ThreadPoolExecutor(max_workers=2) as executor:
        coros = []
        if "classify" in stages:
            coros.append(loop.run_in_executor(executor, _run_classify_standalone, asset_id))
        if "embed" in stages:
            coros.append(loop.run_in_executor(executor, _run_embed_standalone, asset_id))
        if coros:
            await asyncio.gather(*coros, return_exceptions=True)


def trigger_asset_processing(db: Session, asset, stages: list[str], background_tasks, async_mode: str = None) -> None:
    """Queue classify/embed stages. Uses BackgroundTasks or Celery based on async_mode.

    Both modes run classify and embed independently and concurrently:
    - background: single async BackgroundTask fans out to a ThreadPoolExecutor
    - celery: one task dispatched per stage, run on separate workers
    """
    from app.config import settings
    mode = async_mode or settings.async_mode

    if mode == "celery":
        from app.ai.tasks import celery_process_asset
        # One task per stage — Celery scheduler assigns them to separate workers
        for stage in stages:
            celery_process_asset.delay(str(asset.id), [stage])
    else:
        # Single async background task runs both stages concurrently via thread pool
        background_tasks.add_task(_process_asset_parallel, str(asset.id), stages)


def create_reprocess_job(db: Session, stages: list[str]):
    from app.assets.models import ProcessingJob
    total = db.query(Asset).count()
    job = ProcessingJob(id=_uuid.uuid4(), stages=stages, total=total, status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def run_reprocess_job(db: Session, job_id, stages: list[str], async_mode: str = None) -> None:
    """Process all assets page by page. Updates job status as it goes."""
    from app.config import settings
    mode = async_mode or settings.async_mode

    if mode == "celery":
        from app.ai.tasks import celery_run_reprocess_job
        celery_run_reprocess_job.delay(str(job_id), stages)
        return

    from app.assets.models import ProcessingJob, JobStatus
    from app.ai.vlm_client import get_vlm_client
    from app.ai.embed_client import get_embedding_client
    from app.ai.processing import classify_asset, embed_asset

    job = db.get(ProcessingJob, job_id)
    job.status = JobStatus.running
    db.flush()

    vlm = get_vlm_client() if "classify" in stages else None
    embed = get_embedding_client() if "embed" in stages else None
    storage = get_storage()

    page_size = 50
    offset = 0
    while True:
        batch = db.query(Asset).offset(offset).limit(page_size).all()
        if not batch:
            break
        for asset in batch:
            try:
                if vlm:
                    classify_asset(db, asset, vlm, storage)
                if embed:
                    embed_asset(db, asset, embed, storage)
                job.processed += 1
            except Exception:
                job.failed_count += 1
            db.flush()
        offset += page_size

    job.status = JobStatus.done
    db.flush()
    db.commit()


def run_reprocess_job_standalone(job_id: str, stages: list[str]) -> None:
    """Background entrypoint that owns its DB session."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        run_reprocess_job(db, _uuid.UUID(job_id), stages, async_mode="background")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def batch_ingest_from_storage(
    db: Session,
    prefix: str,
    stages: list[str],
    background_tasks,
    async_mode: str | None = None,
) -> "ProcessingJob":
    """List S3 objects with prefix, create a ProcessingJob, queue background ingest."""
    from app.assets.models import ProcessingJob
    from app.config import settings

    storage = get_storage()
    keys = storage.list_objects(prefix)

    image_exts = {".jpg", ".jpeg", ".png", ".webp"}
    image_keys = [k for k in keys if any(k.lower().endswith(ext) for ext in image_exts)]

    job = ProcessingJob(stages=stages, total=len(image_keys), status="pending")
    db.add(job)
    db.commit()
    db.refresh(job)

    mode = async_mode or settings.async_mode
    if mode == "celery":
        from app.ai.tasks import celery_ingest_storage_batch

        celery_ingest_storage_batch.delay(str(job.id), image_keys, prefix, stages)
    else:
        background_tasks.add_task(_ingest_storage_batch_standalone, str(job.id), image_keys, prefix, stages)

    return job


def _ingest_storage_batch_standalone(job_id: str, keys: list[str], prefix: str, stages: list[str]) -> None:
    """Background entrypoint that owns its DB session."""
    from app.database import SessionLocal
    from app.assets.models import ProcessingJob, JobStatus

    db = SessionLocal()
    try:
        _ingest_storage_batch(db, _uuid.UUID(job_id), keys, prefix, stages)
        db.commit()
    except Exception:
        db.rollback()
        job = db.get(ProcessingJob, _uuid.UUID(job_id))
        if job:
            job.status = JobStatus.failed
            db.commit()
        raise
    finally:
        db.close()


def _ingest_storage_batch(db: Session, job_id, keys: list[str], prefix: str, stages: list[str]) -> None:
    """Background task: download each key, create Asset, optionally run AI processing."""
    import uuid as _uuid2
    from app.assets.models import JobStatus, ProcessingJob
    from app.image_processing import process_image

    job = db.get(ProcessingJob, job_id)
    job.status = JobStatus.running
    db.flush()

    storage = get_storage()
    vlm = None
    embed = None
    if "classify" in stages:
        from app.ai.vlm_client import get_vlm_client
        vlm = get_vlm_client()
    if "embed" in stages:
        from app.ai.embed_client import get_embedding_client
        embed = get_embedding_client()

    groups_by_path: dict[str, ImageGroup] = {}
    products_by_code: dict[str, Product] = {}

    for key in keys:
        try:
            data = storage.get_object(key)
            variants = process_image(data)
            filename = key.split("/")[-1]
            group_path, group_name = _derive_group_from_key(key, fallback_prefix=prefix)
            asset_type, source_dataset, source_relpath, parse_status, product_codes = _infer_from_storage_key(
                key, prefix
            )

            group = groups_by_path.get(group_path)
            if not group:
                group = ImageGroup(name=group_name, path=group_path)
                db.add(group)
                db.flush()
                groups_by_path[group_path] = group

            base = f"assets/{_uuid2.uuid4()}"
            original_uri = storage.upload(f"{base}/original/{filename}", data, "image/jpeg")
            display_uri = storage.upload(f"{base}/display/{filename}", variants.display, "image/jpeg")
            thumb_uri = storage.upload(f"{base}/thumb/{filename}", variants.thumb, "image/jpeg")

            from app.assets.models import Asset
            asset = Asset(
                group_id=group.id,
                original_uri=original_uri,
                display_uri=display_uri,
                thumb_uri=thumb_uri,
                filename=filename,
                width=variants.original_width,
                height=variants.original_height,
                file_size=len(data),
                feature_status={"classify": "pending", "embed": "pending"},
                asset_type=asset_type,
                source_dataset=source_dataset,
                source_relpath=source_relpath,
                parse_status=parse_status,
            )
            db.add(asset)
            db.flush()

            for code in product_codes:
                product = products_by_code.get(code)
                if not product:
                    product = _upsert_product_by_code(db, code)
                    products_by_code[code] = product
                link = (
                    db.query(AssetProduct)
                    .filter(AssetProduct.asset_id == asset.id, AssetProduct.product_id == product.id)
                    .first()
                )
                if not link:
                    db.add(
                        AssetProduct(
                            asset_id=asset.id,
                            product_id=product.id,
                            relation_role=_relation_role_for_asset_type(asset_type),
                            source="folder_or_filename",
                        )
                    )

            if vlm:
                from app.ai.processing import classify_asset
                classify_asset(db, asset, vlm, storage)
            if embed:
                from app.ai.processing import embed_asset
                embed_asset(db, asset, embed, storage)

            job.processed += 1
        except Exception:
            job.failed_count += 1
        db.flush()

    job.status = JobStatus.done
    db.flush()
