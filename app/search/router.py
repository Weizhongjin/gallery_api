import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.assets.models import AssetType, DimensionEnum
from app.auth.deps import get_current_user
from app.auth.models import User
from app.database import get_db
from app.search.schemas import ProductSearchPage, SearchResult
from app.search.service import (
    attribute_search,
    product_attribute_search,
    product_vector_search,
    vector_search,
)
from app.ai.embed_client import get_embedding_client
from app.storage import get_storage
from app.image_processing import process_image

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=list[SearchResult])
def search(
    tag_ids: list[uuid.UUID] = Query(default=[]),
    dimension: Optional[DimensionEnum] = None,
    asset_type: Optional[AssetType] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    return attribute_search(db, tag_ids, dimension, page, page_size, asset_type=asset_type)


class SemanticSearchRequest(BaseModel):
    text: str
    limit: int = 50


class ProductSemanticSearchRequest(BaseModel):
    text: str
    limit: int = 300
    page: int = 1
    page_size: int = 50


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
    embed_client = get_embedding_client()
    if getattr(embed_client, "provider", "") == "dashscope":
        vec = embed_client.embed_image_bytes(variants.display, "image/jpeg")
    else:
        storage = get_storage()
        key = f"search-tmp/{uuid.uuid4()}.jpg"
        storage.upload(key, variants.display, "image/jpeg")
        presigned = storage.get_presigned_url(key)
        vec = embed_client.embed_image(presigned)
    rows = vector_search(db, vec, limit=50)
    return [_row_to_result(r) for r in rows]


@router.get("/products", response_model=ProductSearchPage)
def product_search(
    tag_ids: list[uuid.UUID] = Query(default=[]),
    dimension: Optional[DimensionEnum] = None,
    asset_type: Optional[AssetType] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items, total = product_attribute_search(
        db,
        tag_ids=tag_ids,
        dimension=dimension,
        asset_type=asset_type,
        page=page,
        page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/products/semantic", response_model=ProductSearchPage)
def product_semantic_search(
    body: ProductSemanticSearchRequest,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    embed_client = get_embedding_client()
    vec = embed_client.embed_text(body.text)
    items, total = product_vector_search(
        db,
        query_vector=vec,
        mode="semantic",
        page=body.page,
        page_size=body.page_size,
        candidate_limit=body.limit,
    )
    return {"items": items, "total": total, "page": body.page, "page_size": body.page_size}


@router.post("/products/vector", response_model=ProductSearchPage)
def product_image_vector_search(
    file: UploadFile,
    page: int = 1,
    page_size: int = 50,
    limit: int = 300,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    data = file.file.read()
    variants = process_image(data)
    embed_client = get_embedding_client()
    if getattr(embed_client, "provider", "") == "dashscope":
        vec = embed_client.embed_image_bytes(variants.display, "image/jpeg")
    else:
        storage = get_storage()
        key = f"search-tmp/{uuid.uuid4()}.jpg"
        storage.upload(key, variants.display, "image/jpeg")
        presigned = storage.get_presigned_url(key)
        vec = embed_client.embed_image(presigned)

    items, total = product_vector_search(
        db,
        query_vector=vec,
        mode="vector",
        page=page,
        page_size=page_size,
        candidate_limit=limit,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}
