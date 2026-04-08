import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.assets.models import DimensionEnum
from app.auth.deps import get_current_user
from app.auth.models import User
from app.database import get_db
from app.search.schemas import SearchResult
from app.search.service import attribute_search

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
