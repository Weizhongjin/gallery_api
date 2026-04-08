import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.assets.models import DimensionEnum
from app.auth.deps import get_current_user
from app.auth.models import User
from app.database import get_db
from app.search.schemas import SearchResult
from app.search.service import attribute_search, vector_search
from app.ai.embed_client import get_embedding_client
from app.storage import get_storage
from app.image_processing import process_image

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SearchResult])
def search(
    tag_ids: list[uuid.UUID] = Query(default=[]),
    dimension: Optional[DimensionEnum] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return attribute_search(db, tag_ids, dimension, page, page_size)


class SemanticSearchRequest(BaseModel):
    text: str
    limit: int = 50


def _row_to_result(row) -> dict:
    return {
        "id": str(row.id),
        "filename": row.filename,
        "thumb_uri": row.thumb_uri,
        "display_uri": row.display_uri,
        "width": row.width,
        "height": row.height,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/semantic")
def semantic_search(
    body: SemanticSearchRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    embed_client = get_embedding_client()
    vec = embed_client.embed_text(body.text)
    rows = vector_search(db, vec, body.limit)
    return [_row_to_result(r) for r in rows]


@router.post("/vector")
def image_vector_search(
    file: UploadFile,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    data = file.file.read()
    variants = process_image(data)
    storage = get_storage()
    key = f"search-tmp/{uuid.uuid4()}.jpg"
    storage.upload(key, variants.display, "image/jpeg")
    presigned = storage.get_presigned_url(key)

    embed_client = get_embedding_client()
    vec = embed_client.embed_image(presigned)
    rows = vector_search(db, vec, limit=50)
    return [_row_to_result(r) for r in rows]
