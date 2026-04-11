import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.assets.models import AssetProductRole, AssetType, ProductTagSource


class ProductUpsertIn(BaseModel):
    product_code: str
    name: str | None = None
    list_price: float | None = None
    sale_price: float | None = None
    currency: str = "CNY"


class ProductPatchIn(BaseModel):
    name: str | None = None
    list_price: float | None = None
    sale_price: float | None = None
    currency: str | None = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_code: str
    name: str | None = None
    list_price: float | None = None
    sale_price: float | None = None
    currency: str
    created_at: datetime
    updated_at: datetime


class ProductAssetOut(BaseModel):
    asset_id: uuid.UUID
    filename: str
    asset_type: AssetType
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
