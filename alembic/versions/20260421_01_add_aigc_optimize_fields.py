"""add_aigc_optimize_fields

Revision ID: 20260421_01
Revises: 7f2622d07b01
Create Date: 2026-04-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "20260421_01"
down_revision: Union[str, None] = "7f2622d07b01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("aigc_task", sa.Column("workflow_type", sa.String(), server_default="base", nullable=False))
    op.add_column("aigc_task", sa.Column("source_task_id", sa.UUID(), nullable=True))
    op.add_column("aigc_task", sa.Column("source_candidate_id", sa.UUID(), nullable=True))
    op.add_column("aigc_task", sa.Column("optimize_prompt", sa.String(), nullable=True))
    op.create_unique_constraint(
        "uq_aigc_task_candidate_task_id_id",
        "aigc_task_candidate",
        ["task_id", "id"],
    )
    op.create_foreign_key(
        "fk_aigc_task_source_task_id_aigc_task",
        "aigc_task",
        "aigc_task",
        ["source_task_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_aigc_task_source_candidate_id_aigc_task_candidate",
        "aigc_task",
        "aigc_task_candidate",
        ["source_candidate_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_aigc_task_source_task_source_candidate_pair",
        "aigc_task",
        "aigc_task_candidate",
        ["source_task_id", "source_candidate_id"],
        ["task_id", "id"],
    )
    op.create_check_constraint(
        "ck_aigc_task_source_pair_nullity",
        "aigc_task",
        "(source_task_id IS NULL AND source_candidate_id IS NULL) OR "
        "(source_task_id IS NOT NULL AND source_candidate_id IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_aigc_task_source_pair_nullity", "aigc_task", type_="check")
    op.drop_constraint("fk_aigc_task_source_task_source_candidate_pair", "aigc_task", type_="foreignkey")
    op.drop_constraint("fk_aigc_task_source_candidate_id_aigc_task_candidate", "aigc_task", type_="foreignkey")
    op.drop_constraint("fk_aigc_task_source_task_id_aigc_task", "aigc_task", type_="foreignkey")
    op.drop_constraint("uq_aigc_task_candidate_task_id_id", "aigc_task_candidate", type_="unique")
    op.drop_column("aigc_task", "optimize_prompt")
    op.drop_column("aigc_task", "source_candidate_id")
    op.drop_column("aigc_task", "source_task_id")
    op.drop_column("aigc_task", "workflow_type")
