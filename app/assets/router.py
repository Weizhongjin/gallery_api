import uuid
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.assets.models import Asset, AssetType, AssetProductRole, ProcessingJob
from app.assets.schemas import AssetOut, AssetTagPatch, AssetWithTags, TagOut
from app.assets.service import (
    batch_ingest_from_storage, create_reprocess_job, get_asset_tags, list_assets_filtered,
    patch_human_tags, run_reprocess_job, trigger_asset_processing, upload_asset,
    bind_asset_to_product, unbind_asset_product, list_asset_products,
)
from app.auth.deps import get_current_user, require_role
from app.auth.models import User, UserRole
from app.database import get_db

router = APIRouter(prefix="/assets", tags=["assets"])


class ProcessRequest(BaseModel):
    stages: list[str] = ["classify", "embed"]


class BatchIngestStorageRequest(BaseModel):
    prefix: str
    stages: list[str] = ["classify", "embed"]


class AssetProductBindRequest(BaseModel):
    product_code: str
    relation_role: AssetProductRole = AssetProductRole.manual
    source: str = "manual"


_UPLOAD_ROLES = (UserRole.admin, UserRole.editor)


@router.post("/batch-ingest/storage", status_code=202)
def batch_ingest_storage(
    body: BatchIngestStorageRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    job = batch_ingest_from_storage(db, body.prefix, body.stages, background_tasks)
    return {"job_id": str(job.id), "prefix": body.prefix, "stages": body.stages}


@router.post("/reprocess", status_code=202)
def reprocess_all(
    body: ProcessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    job = create_reprocess_job(db, body.stages)
    background_tasks.add_task(run_reprocess_job, db, job.id, body.stages)
    return {"job_id": str(job.id), "stages": body.stages, "total": job.total}


@router.post("/upload", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
def upload(
    file: UploadFile,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(*_UPLOAD_ROLES)),
):
    data = file.file.read()
    return upload_asset(db, file.filename or "upload.jpg", data)


@router.get("", response_model=list[AssetOut])
def list_assets(
    page: int = 1,
    page_size: int = 50,
    tag_ids: list[uuid.UUID] = Query(default=[]),
    asset_type: Optional[AssetType] = None,
    product_code: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if tag_ids or asset_type or product_code:
        return list_assets_filtered(
            db,
            tag_ids=tag_ids,
            page=page,
            page_size=page_size,
            asset_type=asset_type,
            product_code=product_code,
        )
    offset = (page - 1) * page_size
    return db.query(Asset).order_by(Asset.created_at.desc()).offset(offset).limit(page_size).all()


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.patch("/{asset_id}/tags", response_model=AssetWithTags)
def patch_tags(
    asset_id: uuid.UUID,
    body: AssetTagPatch,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    asset = patch_human_tags(db, asset_id, body.add, body.remove)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    tags = get_asset_tags(db, asset_id)
    return AssetWithTags(
        id=asset.id,
        filename=asset.filename,
        original_uri=asset.original_uri,
        display_uri=asset.display_uri,
        thumb_uri=asset.thumb_uri,
        width=asset.width,
        height=asset.height,
        file_size=asset.file_size,
        feature_status=asset.feature_status,
        asset_type=asset.asset_type,
        parse_status=asset.parse_status,
        source_dataset=asset.source_dataset,
        source_relpath=asset.source_relpath,
        created_at=asset.created_at,
        tags=[TagOut(node_id=t.node_id, source=t.source, confidence=t.confidence) for t in tags],
    )


@router.post("/{asset_id}/process", status_code=202)
def process_asset(
    asset_id: uuid.UUID,
    body: ProcessRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    trigger_asset_processing(db, asset, body.stages, background_tasks)
    return {"asset_id": str(asset_id), "stages": body.stages}


@router.get("/{asset_id}/products")
def get_asset_products(
    asset_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return list_asset_products(db, asset_id)


@router.post("/{asset_id}/products/bind", status_code=status.HTTP_201_CREATED)
def bind_product(
    asset_id: uuid.UUID,
    body: AssetProductBindRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    out = bind_asset_to_product(
        db,
        asset_id=asset_id,
        product_code=body.product_code,
        relation_role=body.relation_role,
        source=body.source,
    )
    if not out:
        raise HTTPException(status_code=404, detail="Asset not found")
    return out


@router.delete("/{asset_id}/products/{product_code}", status_code=status.HTTP_204_NO_CONTENT)
def unbind_product(
    asset_id: uuid.UUID,
    product_code: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.admin, UserRole.editor)),
):
    ok = unbind_asset_product(db, asset_id=asset_id, product_code=product_code)
    if not ok:
        raise HTTPException(status_code=404, detail="Binding not found")
