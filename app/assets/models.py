import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Enum, Float, ForeignKey,
    Integer, String, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AssetType(str, enum.Enum):
    advertising = "advertising"
    flatlay = "flatlay"
    model_set = "model_set"
    unknown = "unknown"


class ParseStatus(str, enum.Enum):
    parsed = "parsed"
    unresolved = "unresolved"


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
    asset_type: Mapped[AssetType] = mapped_column(
        Enum(AssetType, name="assettype"),
        nullable=False,
        default=AssetType.unknown,
        server_default=AssetType.unknown.value,
    )
    source_dataset: Mapped[str | None] = mapped_column(String, nullable=True)
    source_relpath: Mapped[str | None] = mapped_column(String, nullable=True)
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, name="parsestatus"),
        nullable=False,
        default=ParseStatus.unresolved,
        server_default=ParseStatus.unresolved.value,
    )
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


class AssetProductRole(str, enum.Enum):
    flatlay_primary = "flatlay_primary"
    advertising_ref = "advertising_ref"
    model_ref = "model_ref"
    manual = "manual"


class ProductTagSource(str, enum.Enum):
    aggregated = "aggregated"
    human = "human"


class Product(Base):
    __tablename__ = "product"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_code: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    list_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    sale_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String, nullable=False, default="CNY", server_default="CNY")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AssetProduct(Base):
    __tablename__ = "asset_product"

    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("asset.id"), primary_key=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product.id"), primary_key=True
    )
    relation_role: Mapped[AssetProductRole] = mapped_column(
        Enum(AssetProductRole, name="assetproductrole"),
        nullable=False,
        default=AssetProductRole.manual,
        server_default=AssetProductRole.manual.value,
    )
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProductTag(Base):
    __tablename__ = "product_tag"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product.id"), primary_key=True
    )
    node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("taxonomy_node.id"), primary_key=True
    )
    source: Mapped[ProductTagSource] = mapped_column(
        Enum(ProductTagSource, name="producttagsource"),
        nullable=False,
        primary_key=True,
    )
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SalesOrderRaw(Base):
    __tablename__ = "sales_order_raw"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="budan", server_default="budan")
    source_order_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    style_no_norm: Mapped[str] = mapped_column(String, index=True, nullable=False)
    total_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    customer: Mapped[str | None] = mapped_column(String, nullable=True)
    salesperson: Mapped[str | None] = mapped_column(String, nullable=True)
    order_type: Mapped[str | None] = mapped_column(String, nullable=True)
    source_file: Mapped[str | None] = mapped_column(String, nullable=True)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ProductSalesSummary(Base):
    __tablename__ = "product_sales_summary"

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product.id"), primary_key=True
    )
    product_code: Mapped[str] = mapped_column(String, index=True, nullable=False)
    sales_total_qty: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


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


class JobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class ProcessingJob(Base):
    __tablename__ = "processing_job"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), nullable=False, server_default="pending")
    stages: Mapped[list] = mapped_column(JSONB, nullable=False)
    total: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    processed: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
