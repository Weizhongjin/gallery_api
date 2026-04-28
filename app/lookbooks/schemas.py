import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class LookbookCreate(BaseModel):
    title: str
    cover_asset_id: uuid.UUID | None = None


class LookbookUpdate(BaseModel):
    title: str | None = None
    cover_asset_id: uuid.UUID | None = None


class LookbookItemIn(BaseModel):
    asset_id: uuid.UUID
    sort_order: int = 0
    note: str | None = None


class LookbookItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    lookbook_id: uuid.UUID
    asset_id: uuid.UUID
    sort_order: int
    note: str | None = None


class LookbookOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    cover_asset_id: uuid.UUID | None
    resolved_cover_asset_id: uuid.UUID | None = None
    is_published: bool
    created_by: uuid.UUID
    created_at: datetime


class AccessIn(BaseModel):
    user_id: uuid.UUID


class AccessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    lookbook_id: uuid.UUID
    user_id: uuid.UUID
    granted_by: uuid.UUID
    granted_at: datetime


class LookbookSectionCreateFromProduct(BaseModel):
    product_id: uuid.UUID


class LookbookSectionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    asset_id: uuid.UUID
    sort_order: int
    source: str
    is_cover: bool
    note: str | None = None


class LookbookSectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    lookbook_id: uuid.UUID
    product_id: uuid.UUID | None
    sort_order: int
    cover_asset_id: uuid.UUID | None
    items: list[LookbookSectionItemOut] = []


class LookbookSectionItemAdd(BaseModel):
    asset_ids: list[uuid.UUID]


class LookbookSectionReorderIn(BaseModel):
    section_ids: list[uuid.UUID]
