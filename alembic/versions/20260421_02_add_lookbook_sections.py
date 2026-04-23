"""add_lookbook_sections

Revision ID: 20260421_02
Revises: 20260421_01
Create Date: 2026-04-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260421_02"
down_revision: Union[str, None] = "20260421_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lookbook_product_section",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("lookbook_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cover_asset_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["lookbook_id"], ["lookbook.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"]),
        sa.ForeignKeyConstraint(["cover_asset_id"], ["asset.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lookbook_id", "product_id", name="uq_lookbook_product_section_lookbook_product"),
    )
    op.create_index("ix_lookbook_product_section_lookbook_id", "lookbook_product_section", ["lookbook_id"])
    op.create_index("ix_lookbook_product_section_product_id", "lookbook_product_section", ["product_id"])

    op.create_table(
        "lookbook_section_item",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("section_id", sa.UUID(), nullable=False),
        sa.Column("asset_id", sa.UUID(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(), nullable=False, server_default="system"),
        sa.Column("is_cover", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("note", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["section_id"], ["lookbook_product_section.id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["asset.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("section_id", "asset_id", name="uq_lookbook_section_item_section_asset"),
    )
    op.create_index("ix_lookbook_section_item_section_id", "lookbook_section_item", ["section_id"])


def downgrade() -> None:
    op.drop_table("lookbook_section_item")
    op.drop_table("lookbook_product_section")
