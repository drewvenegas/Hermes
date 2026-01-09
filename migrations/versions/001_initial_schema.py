"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-01-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create prompt_type enum
    prompt_type = postgresql.ENUM(
        'agent_system', 'user_template', 'tool_definition', 'mcp_instruction',
        name='prompt_type'
    )
    prompt_type.create(op.get_bind())
    
    # Create prompt_status enum
    prompt_status = postgresql.ENUM(
        'draft', 'review', 'staged', 'deployed', 'archived',
        name='prompt_status'
    )
    prompt_status.create(op.get_bind())
    
    # Create prompts table
    op.create_table(
        'prompts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('slug', sa.String(255), nullable=False, unique=True, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('type', sa.Enum('agent_system', 'user_template', 'tool_definition', 'mcp_instruction', name='prompt_type'), nullable=False, index=True),
        sa.Column('category', sa.String(100), nullable=True, index=True),
        sa.Column('tags', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('variables', postgresql.JSONB, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('version', sa.String(50), nullable=False, default='1.0.0'),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('status', sa.Enum('draft', 'review', 'staged', 'deployed', 'archived', name='prompt_status'), nullable=False, default='draft', index=True),
        sa.Column('deployed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('owner_type', sa.String(20), nullable=False, default='user'),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('visibility', sa.String(20), nullable=False, default='private'),
        sa.Column('app_scope', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('repo_scope', postgresql.ARRAY(sa.String), nullable=True),
        sa.Column('benchmark_score', sa.Float, nullable=True),
        sa.Column('last_benchmark_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('nursery_path', sa.String(500), nullable=True),
        sa.Column('source_commit', sa.String(40), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    # Create indexes for prompts
    op.create_index('ix_prompts_owner_status', 'prompts', ['owner_id', 'status'])
    op.create_index('ix_prompts_type_category', 'prompts', ['type', 'category'])
    op.create_index('ix_prompts_visibility', 'prompts', ['visibility'])
    
    # Create prompt_versions table
    op.create_table(
        'prompt_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prompts.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('diff', sa.Text, nullable=True),
        sa.Column('change_summary', sa.String(500), nullable=True),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('variables', postgresql.JSONB, nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('benchmark_results', postgresql.JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    
    # Create unique index for prompt version
    op.create_index('ix_prompt_versions_prompt_version', 'prompt_versions', ['prompt_id', 'version'], unique=True)
    
    # Create benchmark_results table
    op.create_table(
        'benchmark_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prompts.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('prompt_version', sa.String(50), nullable=False),
        sa.Column('suite_id', sa.String(100), nullable=False, default='default'),
        sa.Column('overall_score', sa.Float, nullable=False),
        sa.Column('dimension_scores', postgresql.JSONB, nullable=False),
        sa.Column('model_id', sa.String(100), nullable=False),
        sa.Column('model_version', sa.String(50), nullable=True),
        sa.Column('execution_time_ms', sa.Integer, nullable=False),
        sa.Column('token_usage', postgresql.JSONB, nullable=True),
        sa.Column('baseline_score', sa.Float, nullable=True),
        sa.Column('delta', sa.Float, nullable=True),
        sa.Column('gate_passed', sa.Boolean, nullable=False, default=False),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('executed_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('environment', sa.String(20), nullable=False, default='staging'),
        sa.Column('raw_results', postgresql.JSONB, nullable=True),
    )
    
    # Create indexes for benchmark_results
    op.create_index('ix_benchmark_results_prompt_version', 'benchmark_results', ['prompt_id', 'prompt_version'])
    op.create_index('ix_benchmark_results_executed_at', 'benchmark_results', ['executed_at'])


def downgrade() -> None:
    op.drop_table('benchmark_results')
    op.drop_table('prompt_versions')
    op.drop_table('prompts')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS prompt_status')
    op.execute('DROP TYPE IF EXISTS prompt_type')
