import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class SearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    thumb_uri: str
    display_uri: str
    width: int
    height: int
    created_at: datetime


class ProductSearchItem(BaseModel):
    product_id: uuid.UUID
    product_code: str
    name: str | None = None
    year: int | None = None
    list_price: float | None = None
    sale_price: float | None = None
    currency: str | None = None
    sales_total_qty: int | None = None
    score: float
    match_reasons: list[str]
    cover_asset_id: uuid.UUID | None = None
    cover_filename: str | None = None
    cover_thumb_uri: str | None = None
    cover_display_uri: str | None = None
    cover_width: int | None = None
    cover_height: int | None = None
    matched_asset_count: int = 0


class ProductSearchPage(BaseModel):
    items: list[ProductSearchItem]
    total: int
    page: int
    page_size: int
