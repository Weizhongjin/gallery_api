"""add_processing_job

Revision ID: 89f84c614b43
Revises: 56005649f40b
Create Date: 2026-04-09 00:16:45.035302

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '89f84c614b43'
down_revision: Union[str, None] = '56005649f40b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "processing_job",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("status", sa.Enum("pending", "running", "done", "failed", name="jobstatus"), nullable=False, server_default="pending"),
        sa.Column("stages", JSONB, nullable=False),
        sa.Column("total", sa.Integer, nullable=False, server_default="0"),
        sa.Column("processed", sa.Integer, nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("processing_job")
    op.execute("DROP TYPE IF EXISTS jobstatus")
