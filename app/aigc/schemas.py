import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.aigc.models import AigcTaskStatus
from app.assets.models import AssetType


class AigcTaskCreateIn(BaseModel):
    product_id: uuid.UUID
    flatlay_asset_id: uuid.UUID
    reference_source: str  # "library" | "upload"
    reference_asset_id: uuid.UUID | None = None
    reference_upload_uri: str | None = None
    consent_checked: bool = False
    face_deidentify_enabled: bool = True
    candidate_count: int = 2
    template_version: int = 1

    @field_validator("reference_source")
    @classmethod
    def validate_reference_source(cls, v):
        if v not in ("library", "upload"):
            raise ValueError("reference_source must be 'library' or 'upload'")
        return v

    @field_validator("consent_checked")
    @classmethod
    def require_consent(cls, v):
        if not v:
            raise ValueError("consent_checked must be true for AIGC task creation")
        return v


class AigcApproveIn(BaseModel):
    selected_candidate_id: uuid.UUID
    target_asset_type: AssetType = AssetType.model_set


class AigcRejectIn(BaseModel):
    reason: str | None = None


class AigcTaskCandidateOut(BaseModel):
    id: uuid.UUID
    seq_no: int
    image_uri: str | None = None
    thumb_uri: str | None = None
    width: int | None = None
    height: int | None = None
    file_size: int | None = None
    is_selected: bool = False

    model_config = {"from_attributes": True}


class AigcTaskOut(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    flatlay_asset_id: uuid.UUID
    flatlay_original_uri: str
    reference_source: str
    reference_asset_id: uuid.UUID | None = None
    reference_original_uri: str | None = None
    reference_upload_uri: str | None = None
    face_deidentify_enabled: bool = True
    candidate_count: int = 2
    template_version: int = 1
    status: AigcTaskStatus
    provider: str
    model_name: str
    timeout_seconds: int
    error_code: str | None = None
    error_message: str | None = None
    created_by: uuid.UUID
    reviewed_by: uuid.UUID | None = None
    reviewed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    candidates: list[AigcTaskCandidateOut] = []

    model_config = {"from_attributes": True}


class AigcProviderOut(BaseModel):
    provider_key: str
    display_name: str
    default_model: str


class AigcCandidateFeedbackIn(BaseModel):
    score: int | None = None
    comment: str | None = None

    @field_validator("score")
    @classmethod
    def score_range(cls, v):
        if v is not None and not (1 <= v <= 5):
            raise ValueError("score must be between 1 and 5")
        return v
