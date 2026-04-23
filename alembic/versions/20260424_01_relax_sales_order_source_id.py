"""relax sales source_order_id nullability

Revision ID: 20260424_01
Revises: 20260421_02
Create Date: 2026-04-24 10:20:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260424_01"
down_revision: Union[str, None] = "20260421_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("sales_order_raw", "source_order_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.alter_column("sales_order_raw", "source_order_id", existing_type=sa.Integer(), nullable=False)
