"""add_aigc_tables_and_ai_generated_flag

Revision ID: 7f2622d07b01
Revises: 2f6a8b1d4c0e
Create Date: 2026-04-19 23:13:04.284077

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '7f2622d07b01'
down_revision: Union[str, None] = '2f6a8b1d4c0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('aigc_prompt_template',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('status', sa.Enum('active', 'disabled', name='aigcprompttemplatestatus'), server_default='active', nullable=False),
    sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('aigc_prompt_template_version',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('template_id', sa.UUID(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('content', sa.String(), nullable=False),
    sa.Column('variables', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('is_published', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['template_id'], ['aigc_prompt_template.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('aigc_task',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('flatlay_asset_id', sa.UUID(), nullable=False),
    sa.Column('flatlay_original_uri', sa.String(), nullable=False),
    sa.Column('reference_source', sa.String(), nullable=False),
    sa.Column('reference_asset_id', sa.UUID(), nullable=True),
    sa.Column('reference_original_uri', sa.String(), nullable=True),
    sa.Column('reference_upload_uri', sa.String(), nullable=True),
    sa.Column('face_deidentify_enabled', sa.Boolean(), server_default='true', nullable=False),
    sa.Column('candidate_count', sa.Integer(), server_default='2', nullable=False),
    sa.Column('template_id', sa.UUID(), nullable=True),
    sa.Column('template_version', sa.Integer(), server_default='1', nullable=False),
    sa.Column('status', sa.Enum('queued', 'running', 'review_pending', 'approved', 'rejected', 'failed', name='aigctaskstatus'), server_default='queued', nullable=False),
    sa.Column('provider', sa.String(), server_default='seedream_ark', nullable=False),
    sa.Column('model_name', sa.String(), server_default='doubao-seedream-4-5-251128', nullable=False),
    sa.Column('provider_profile', sa.String(), nullable=True),
    sa.Column('timeout_seconds', sa.Integer(), server_default='900', nullable=False),
    sa.Column('created_by', sa.UUID(), nullable=False),
    sa.Column('reviewed_by', sa.UUID(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('error_code', sa.String(), nullable=True),
    sa.Column('error_message', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['user.id'], ),
    sa.ForeignKeyConstraint(['flatlay_asset_id'], ['asset.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
    sa.ForeignKeyConstraint(['reference_asset_id'], ['asset.id'], ),
    sa.ForeignKeyConstraint(['reviewed_by'], ['user.id'], ),
    sa.ForeignKeyConstraint(['template_id'], ['aigc_prompt_template.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('aigc_authorization_log',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('uploader_user_id', sa.UUID(), nullable=False),
    sa.Column('consent_text_version', sa.String(), nullable=False),
    sa.Column('consent_checked', sa.Boolean(), nullable=False),
    sa.Column('ip', sa.String(), nullable=True),
    sa.Column('user_agent', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['aigc_task.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('aigc_prompt_log',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('template_id', sa.UUID(), nullable=True),
    sa.Column('template_version', sa.Integer(), nullable=True),
    sa.Column('system_prompt', sa.String(), nullable=True),
    sa.Column('user_prompt', sa.String(), nullable=True),
    sa.Column('negative_prompt', sa.String(), nullable=True),
    sa.Column('request_payload_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('response_meta_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['aigc_task.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('aigc_task_candidate',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('task_id', sa.UUID(), nullable=False),
    sa.Column('seq_no', sa.Integer(), nullable=False),
    sa.Column('image_uri', sa.String(), nullable=True),
    sa.Column('thumb_uri', sa.String(), nullable=True),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('is_selected', sa.Boolean(), server_default='false', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['task_id'], ['aigc_task.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('aigc_candidate_feedback',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('candidate_id', sa.UUID(), nullable=False),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('comment', sa.String(), nullable=True),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['candidate_id'], ['aigc_task_candidate.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('asset', sa.Column('is_ai_generated', sa.Boolean(), server_default='false', nullable=False))


def downgrade() -> None:
    op.drop_column('asset', 'is_ai_generated')
    op.drop_table('aigc_candidate_feedback')
    op.drop_table('aigc_task_candidate')
    op.drop_table('aigc_prompt_log')
    op.drop_table('aigc_authorization_log')
    op.drop_table('aigc_task')
    op.drop_table('aigc_prompt_template_version')
    op.drop_table('aigc_prompt_template')
    op.execute("DROP TYPE IF EXISTS aigctaskstatus")
    op.execute("DROP TYPE IF EXISTS aigcprompttemplatestatus")
