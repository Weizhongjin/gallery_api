"""add_user_registration_request

Revision ID: 46bee5ffc059
Revises: 20260424_01
Create Date: 2026-04-29 00:18:00.673706

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '46bee5ffc059'
down_revision: Union[str, None] = '20260424_01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('user_registration_request',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_registration_request_email'), 'user_registration_request', ['email'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_user_registration_request_email'), table_name='user_registration_request')
    op.drop_table('user_registration_request')
