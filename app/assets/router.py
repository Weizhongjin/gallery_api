import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.assets.models import Asset
from app.assets.schemas import AssetOut, AssetTagPatch, AssetWithTags, TagOut
from app.assets.service import get_asset_tags, list_assets_filtered, patch_human_tags, upload_asset
from app.auth.deps import get_current_user, require_role
from app.auth.models import User, UserRole
from app.database import get_db

router = APIRouter(prefix="/assets", tags=["assets"])

_UPLOAD_ROLES = (UserRole.admin, UserRole.editor)


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
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    if tag_ids:
        return list_assets_filtered(db, tag_ids, page, page_size)
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
        created_at=asset.created_at,
        tags=[TagOut(node_id=t.node_id, source=t.source, confidence=t.confidence) for t in tags],
    )
