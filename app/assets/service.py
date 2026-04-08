import uuid
from sqlalchemy.orm import Session

from app.assets.models import Asset
from app.image_processing import process_image
from app.storage import get_storage


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
    db.refresh(asset)
    return asset


def get_asset_tags(db: Session, asset_id: uuid.UUID) -> list:
    from app.assets.models import AssetTag
    return db.query(AssetTag).filter(AssetTag.asset_id == asset_id).all()


def list_assets_filtered(db: Session, tag_ids: list[uuid.UUID], page: int, page_size: int) -> list[Asset]:
    from app.assets.models import AssetTag
    query = db.query(Asset)
    for node_id in tag_ids:
        sub = db.query(AssetTag.asset_id).filter(AssetTag.node_id == node_id).scalar_subquery()
        query = query.filter(Asset.id.in_(sub))
    return query.order_by(Asset.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()


import uuid as _uuid


def trigger_asset_processing(db: Session, asset, stages: list[str], background_tasks) -> None:
    """Queue classify/embed stages as background tasks."""
    from app.ai.vlm_client import get_vlm_client
    from app.ai.embed_client import get_embedding_client
    from app.ai.processing import classify_asset, embed_asset

    if "classify" in stages:
        background_tasks.add_task(classify_asset, db, asset, get_vlm_client(), get_storage())
    if "embed" in stages:
        background_tasks.add_task(embed_asset, db, asset, get_embedding_client(), get_storage())


def create_reprocess_job(db: Session, stages: list[str]):
    from app.assets.models import ProcessingJob
    total = db.query(Asset).count()
    job = ProcessingJob(id=_uuid.uuid4(), stages=stages, total=total, status="pending")
    db.add(job)
    db.flush()
    db.refresh(job)
    return job


def run_reprocess_job(db: Session, job_id, stages: list[str]) -> None:
    """Process all assets page by page. Updates job status as it goes."""
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
