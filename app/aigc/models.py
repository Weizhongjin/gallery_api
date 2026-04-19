import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AigcTaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    review_pending = "review_pending"
    approved = "approved"
    rejected = "rejected"
    failed = "failed"


class AigcTask(Base):
    __tablename__ = "aigc_task"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product.id"), nullable=False)
    flatlay_asset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("asset.id"), nullable=False)
    flatlay_original_uri: Mapped[str] = mapped_column(String, nullable=False)
    reference_source: Mapped[str] = mapped_column(String, nullable=False)  # "library" | "upload"
    reference_asset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("asset.id"), nullable=True)
    reference_original_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    reference_upload_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    face_deidentify_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=2, server_default="2")
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("aigc_prompt_template.id"), nullable=True)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[AigcTaskStatus] = mapped_column(
        Enum(AigcTaskStatus, name="aigctaskstatus"),
        nullable=False,
        default=AigcTaskStatus.queued,
        server_default=AigcTaskStatus.queued.value,
    )
    provider: Mapped[str] = mapped_column(String, nullable=False, default="seedream_ark", server_default="seedream_ark")
    model_name: Mapped[str] = mapped_column(String, nullable=False, default="doubao-seedream-4-5-251128", server_default="doubao-seedream-4-5-251128")
    provider_profile: Mapped[str | None] = mapped_column(String, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=900, server_default="900")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AigcTaskCandidate(Base):
    __tablename__ = "aigc_task_candidate"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("aigc_task.id"), nullable=False)
    seq_no: Mapped[int] = mapped_column(Integer, nullable=False)
    image_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    thumb_uri: Mapped[str | None] = mapped_column(String, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AigcPromptLog(Base):
    __tablename__ = "aigc_prompt_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("aigc_task.id"), nullable=False)
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    system_prompt: Mapped[str | None] = mapped_column(String, nullable=True)
    user_prompt: Mapped[str | None] = mapped_column(String, nullable=True)
    negative_prompt: Mapped[str | None] = mapped_column(String, nullable=True)
    request_payload_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_meta_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AigcAuthorizationLog(Base):
    __tablename__ = "aigc_authorization_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("aigc_task.id"), nullable=False)
    uploader_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    consent_text_version: Mapped[str] = mapped_column(String, nullable=False, default="v1")
    consent_checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ip: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AigcCandidateFeedback(Base):
    __tablename__ = "aigc_candidate_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("aigc_task_candidate.id"), nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AigcPromptTemplateStatus(str, enum.Enum):
    active = "active"
    disabled = "disabled"


class AigcPromptTemplate(Base):
    __tablename__ = "aigc_prompt_template"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[AigcPromptTemplateStatus] = mapped_column(
        Enum(AigcPromptTemplateStatus, name="aigcprompttemplatestatus"),
        nullable=False,
        default=AigcPromptTemplateStatus.active,
        server_default=AigcPromptTemplateStatus.active.value,
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AigcPromptTemplateVersion(Base):
    __tablename__ = "aigc_prompt_template_version"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("aigc_prompt_template.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    variables: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
