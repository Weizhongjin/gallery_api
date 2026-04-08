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
