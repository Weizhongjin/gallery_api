import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum, Float, ForeignKey,
    Integer, String, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ImageGroup(Base):
    __tablename__ = "image_group"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Asset(Base):
    __tablename__ = "asset"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("image_group.id"), nullable=True
    )
    original_uri: Mapped[str] = mapped_column(String, nullable=False)
    display_uri: Mapped[str] = mapped_column(String, nullable=False)
    thumb_uri: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    feature_status: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DimensionEnum(str, enum.Enum):
    category = "category"
    style = "style"
    color = "color"
    scene = "scene"
    detail = "detail"


class TaxonomyNode(Base):
    __tablename__ = "taxonomy_node"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_node.id"), nullable=True
    )
    dimension: Mapped[DimensionEnum] = mapped_column(Enum(DimensionEnum), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    name_en: Mapped[str | None] = mapped_column(String, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TaxonomyCandidate(Base):
    __tablename__ = "taxonomy_candidate"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    raw_label: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    dimension: Mapped[DimensionEnum | None] = mapped_column(Enum(DimensionEnum), nullable=True)
    hit_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TagSource(str, enum.Enum):
    ai = "ai"
    human = "human"


class AssetTag(Base):
    __tablename__ = "asset_tag"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset.id"), primary_key=True
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_node.id"), primary_key=True
    )
    source: Mapped[TagSource] = mapped_column(Enum(TagSource), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class AssetEmbedding(Base):
    __tablename__ = "asset_embedding"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset.id"), primary_key=True
    )
    model_ver: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # vector column added via raw SQL in migration (pgvector)


class Lookbook(Base):
    __tablename__ = "lookbook"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String, nullable=False)
    cover_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset.id"), nullable=True
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class LookbookItem(Base):
    __tablename__ = "lookbook_item"

    lookbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lookbook.id"), primary_key=True
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset.id"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    note: Mapped[str | None] = mapped_column(String, nullable=True)


class LookbookAccess(Base):
    __tablename__ = "lookbook_access"

    lookbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lookbook.id"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), primary_key=True
    )
    granted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user.id"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
