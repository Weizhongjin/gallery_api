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
