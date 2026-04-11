"""add_product_model_and_asset_type

Revision ID: c8f9b6d5f2a1
Revises: 89f84c614b43
Create Date: 2026-04-11 01:35:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "c8f9b6d5f2a1"
down_revision: Union[str, None] = "89f84c614b43"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'assettype') THEN "
        "CREATE TYPE assettype AS ENUM ('advertising','flatlay','model_set','unknown'); END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'parsestatus') THEN "
        "CREATE TYPE parsestatus AS ENUM ('parsed','unresolved'); END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'assetproductrole') THEN "
        "CREATE TYPE assetproductrole AS ENUM ('flatlay_primary','advertising_ref','model_ref','manual'); END IF; END $$;"
    )
    op.execute(
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'producttagsource') THEN "
        "CREATE TYPE producttagsource AS ENUM ('aggregated','human'); END IF; END $$;"
    )

    op.add_column(
        "asset",
        sa.Column(
            "asset_type",
            postgresql.ENUM("advertising", "flatlay", "model_set", "unknown", name="assettype", create_type=False),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column("asset", sa.Column("source_dataset", sa.String(), nullable=True))
    op.add_column("asset", sa.Column("source_relpath", sa.String(), nullable=True))
    op.add_column(
        "asset",
        sa.Column(
            "parse_status",
            postgresql.ENUM("parsed", "unresolved", name="parsestatus", create_type=False),
            nullable=False,
            server_default="unresolved",
        ),
    )

    op.create_table(
        "product",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_code", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("list_price", sa.Float(), nullable=True),
        sa.Column("sale_price", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="CNY"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_product_product_code", "product", ["product_code"], unique=True)

    op.create_table(
        "asset_product",
        sa.Column("asset_id", UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "relation_role",
            postgresql.ENUM(
                "flatlay_primary",
                "advertising_ref",
                "model_ref",
                "manual",
                name="assetproductrole",
                create_type=False,
            ),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"]),
        sa.PrimaryKeyConstraint("asset_id", "product_id"),
    )
    op.create_index("ix_asset_product_asset_id", "asset_product", ["asset_id"], unique=False)
    op.create_index("ix_asset_product_product_id", "asset_product", ["product_id"], unique=False)

    op.create_table(
        "product_tag",
        sa.Column("product_id", UUID(as_uuid=True), nullable=False),
        sa.Column("node_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source",
            postgresql.ENUM("aggregated", "human", name="producttagsource", create_type=False),
            nullable=False,
        ),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"]),
        sa.ForeignKeyConstraint(["node_id"], ["taxonomy_node.id"]),
        sa.PrimaryKeyConstraint("product_id", "node_id", "source"),
    )


def downgrade() -> None:
    op.drop_table("product_tag")
    op.drop_index("ix_asset_product_product_id", table_name="asset_product")
    op.drop_index("ix_asset_product_asset_id", table_name="asset_product")
    op.drop_table("asset_product")
    op.drop_index("ix_product_product_code", table_name="product")
    op.drop_table("product")

    op.drop_column("asset", "parse_status")
    op.drop_column("asset", "source_relpath")
    op.drop_column("asset", "source_dataset")
    op.drop_column("asset", "asset_type")

    op.execute("DROP TYPE IF EXISTS producttagsource")
    op.execute("DROP TYPE IF EXISTS assetproductrole")
    op.execute("DROP TYPE IF EXISTS parsestatus")
    op.execute("DROP TYPE IF EXISTS assettype")
