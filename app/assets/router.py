import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.assets.models import Asset
from app.assets.schemas import AssetOut
from app.assets.service import upload_asset
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
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
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
