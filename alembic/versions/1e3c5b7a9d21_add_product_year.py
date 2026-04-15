"""add product year

Revision ID: 1e3c5b7a9d21
Revises: c8f9b6d5f2a1
Create Date: 2026-04-15 21:58:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "1e3c5b7a9d21"
down_revision: Union[str, None] = "c8f9b6d5f2a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("product", sa.Column("year", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("product", "year")

