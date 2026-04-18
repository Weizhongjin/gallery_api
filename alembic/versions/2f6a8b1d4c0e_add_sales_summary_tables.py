"""add sales raw and product summary tables

Revision ID: 2f6a8b1d4c0e
Revises: 1e3c5b7a9d21
Create Date: 2026-04-16 11:10:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "2f6a8b1d4c0e"
down_revision: Union[str, None] = "1e3c5b7a9d21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales_order_raw",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(), nullable=False, server_default="budan"),
        sa.Column("source_order_id", sa.Integer(), nullable=False),
        sa.Column("order_date", sa.Date(), nullable=True),
        sa.Column("style_no_norm", sa.String(), nullable=False),
        sa.Column("total_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("customer", sa.String(), nullable=True),
        sa.Column("salesperson", sa.String(), nullable=True),
        sa.Column("order_type", sa.String(), nullable=True),
        sa.Column("source_file", sa.String(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("source", "source_order_id", name="uq_sales_order_raw_source_order"),
    )
    op.create_index("ix_sales_order_raw_style_no_norm", "sales_order_raw", ["style_no_norm"], unique=False)

    op.create_table(
        "product_sales_summary",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_code", sa.String(), nullable=False),
        sa.Column("sales_total_qty", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"]),
        sa.PrimaryKeyConstraint("product_id"),
    )
    op.create_index("ix_product_sales_summary_product_code", "product_sales_summary", ["product_code"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_product_sales_summary_product_code", table_name="product_sales_summary")
    op.drop_table("product_sales_summary")

    op.drop_index("ix_sales_order_raw_style_no_norm", table_name="sales_order_raw")
    op.drop_table("sales_order_raw")
