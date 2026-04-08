import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


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
