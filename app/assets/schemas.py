import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.assets.models import TagSource


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    original_uri: str
    display_uri: str
    thumb_uri: str
    width: int
    height: int
    file_size: int
    feature_status: dict
    created_at: datetime


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    node_id: uuid.UUID
    source: str
    confidence: float | None


class AssetTagPatch(BaseModel):
    add: list[uuid.UUID] = []
    remove: list[uuid.UUID] = []


class AssetWithTags(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    filename: str
    original_uri: str
    display_uri: str
    thumb_uri: str
    width: int
    height: int
    file_size: int
    feature_status: dict
    created_at: datetime
    tags: list[TagOut] = []
