import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.assets.models import AssetProductRole, AssetType, ProductTagSource


class ProductUpsertIn(BaseModel):
    product_code: str
    name: str | None = None
    year: int | None = None
    list_price: float | None = None
    sale_price: float | None = None
    currency: str = "CNY"


class ProductPatchIn(BaseModel):
    name: str | None = None
    year: int | None = None
    list_price: float | None = None
    sale_price: float | None = None
    currency: str | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_code: str
    name: str | None = None
    year: int | None = None
    list_price: float | None = None
    sale_price: float | None = None
    sales_total_qty: int | None = None
    currency: str
    created_at: datetime
    updated_at: datetime


class ProductPageOut(BaseModel):
    items: list[ProductOut]
    total: int
    page: int
    page_size: int


class ProductAssetOut(BaseModel):
    asset_id: uuid.UUID
    filename: str
    asset_type: AssetType
    thumb_uri: str
    display_uri: str
    width: int
    height: int
    created_at: datetime
    relation_role: AssetProductRole
    source: str | None = None
    confidence: float | None = None


class ProductTagOut(BaseModel):
    node_id: uuid.UUID
    source: ProductTagSource
    confidence: float | None = None


class ProductTagPatchIn(BaseModel):
    add: list[uuid.UUID] = []
    remove: list[uuid.UUID] = []


class ProductGovernanceSummaryOut(BaseModel):
    total_products: int
    missing_all_assets: int
    missing_flatlay: int
    missing_model: int
    missing_advertising: int
    in_lookbook: int


class ProductGovernanceItemOut(BaseModel):
    id: uuid.UUID
    product_code: str
    name: str | None = None
    sales_total_qty: int
    completeness_state: str
    aux_tags: list[str]
    recommended_action: str
    flatlay_count: int
    model_count: int
    advertising_count: int
    primary_asset_id: uuid.UUID | None = None


class ProductWorkbenchOut(BaseModel):
    product: ProductOut
    completeness_state: str
    aux_tags: list[str]
    recommended_action: str
    grouped_assets: dict[str, list[ProductAssetOut]]
    aigc_summary: dict
    lookbook_summary: dict
    tag_summary: list[ProductTagOut]
    quality_issues: list[str]
