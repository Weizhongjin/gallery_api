import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.assets.models import DimensionEnum


class TaxonomyNodeCreate(BaseModel):
    dimension: DimensionEnum
    name: str
    name_en: str | None = None
    parent_id: uuid.UUID | None = None
    sort_order: int = 0


class TaxonomyNodeUpdate(BaseModel):
    name: str | None = None
    name_en: str | None = None
    parent_id: uuid.UUID | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class TaxonomyNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dimension: DimensionEnum
    name: str
    name_en: str | None
    parent_id: uuid.UUID | None
    sort_order: int
    is_active: bool


class CandidatePromoteIn(BaseModel):
    parent_id: uuid.UUID | None = None


class CandidateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    raw_label: str
    dimension: DimensionEnum | None
    hit_count: int
    reviewed: bool
    created_at: datetime
