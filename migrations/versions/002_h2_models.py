"""H2 Feature Models

Revision ID: 002_h2_models
Revises: 001_initial_schema
Create Date: 2026-01-09

Adds tables for:
- Benchmark suites and test cases
- Prompt templates and versions
- Comments and reviews
- Activities
- Usage metrics
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002_h2_models'
down_revision = '001_initial_schema'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Benchmark Suites
    op.create_table(
        'benchmark_suites',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('slug', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('test_cases', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('dimensions', postgresql.ARRAY(sa.String), nullable=False),
        sa.Column('weights', postgresql.JSONB, nullable=False),
        sa.Column('threshold', sa.Float, nullable=False, server_default='80.0'),
        sa.Column('model_config', postgresql.JSONB, nullable=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('is_default', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('version', sa.String(20), nullable=False, server_default='1.0.0'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_benchmark_suites_owner', 'benchmark_suites', ['owner_id'])
    op.create_index('ix_benchmark_suites_active', 'benchmark_suites', ['is_active'])

    # Benchmark Test Cases
    op.create_table(
        'benchmark_test_cases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('suite_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('input_text', sa.Text, nullable=False),
        sa.Column('expected_patterns', postgresql.JSONB, nullable=True),
        sa.Column('expected_output', sa.Text, nullable=True),
        sa.Column('scoring_criteria', postgresql.JSONB, nullable=False),
        sa.Column('weight', sa.Float, nullable=False, server_default='1.0'),
        sa.Column('tags', postgresql.ARRAY(sa.String), nullable=False, server_default='{}'),
        sa.Column('category', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_benchmark_test_cases_suite', 'benchmark_test_cases', ['suite_id'])
    op.create_index('ix_benchmark_test_cases_category', 'benchmark_test_cases', ['category'])

    # Prompt Templates
    op.create_table(
        'prompt_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('slug', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('variables', postgresql.JSONB, nullable=False, server_default='[]'),
        sa.Column('parent_template_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('forked_from_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('category', sa.String(100), nullable=True, index=True),
        sa.Column('tags', postgresql.ARRAY(sa.String), nullable=False, server_default='{}'),
        sa.Column('version', sa.String(20), nullable=False, server_default='1.0.0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft', index=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('owner_type', sa.String(20), nullable=False, server_default='user'),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('visibility', sa.String(20), nullable=False, server_default='private'),
        sa.Column('fork_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('usage_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('is_curated', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('is_featured', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_templates_owner', 'prompt_templates', ['owner_id'])
    op.create_index('ix_templates_status', 'prompt_templates', ['status'])
    op.create_index('ix_templates_curated', 'prompt_templates', ['is_curated'])
    op.create_index('ix_templates_featured', 'prompt_templates', ['is_featured'])

    # Template Versions
    op.create_table(
        'template_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('version', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('variables', postgresql.JSONB, nullable=False),
        sa.Column('change_summary', sa.String(500), nullable=True),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_template_versions_template_version', 'template_versions', ['template_id', 'version'])

    # Template Usages
    op.create_table(
        'template_usages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('variable_values', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_template_usages_template', 'template_usages', ['template_id'])
    op.create_index('ix_template_usages_user', 'template_usages', ['user_id'])

    # Comments
    op.create_table(
        'comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prompts.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version', sa.String(50), nullable=True),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('comments.id', ondelete='CASCADE'), nullable=True, index=True),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('author_name', sa.String(255), nullable=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('mentions', postgresql.ARRAY(sa.String), nullable=False, server_default='{}'),
        sa.Column('is_resolved', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('resolved_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('is_edited', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('edited_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_comments_prompt', 'comments', ['prompt_id'])
    op.create_index('ix_comments_author', 'comments', ['author_id'])
    op.create_index('ix_comments_parent', 'comments', ['parent_id'])

    # Reviews
    op.create_table(
        'reviews',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prompts.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('reviewer_name', sa.String(255), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending', index=True),
        sa.Column('body', sa.Text, nullable=True),
        sa.Column('required', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('dismissed', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('dismissed_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('dismissed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_reviews_prompt_version', 'reviews', ['prompt_id', 'version'])
    op.create_index('ix_reviews_reviewer', 'reviews', ['reviewer_id'])
    op.create_index('ix_reviews_status', 'reviews', ['status'])

    # Review Requests
    op.create_table(
        'review_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prompts.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('version', sa.String(50), nullable=False),
        sa.Column('requester_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('reviewer_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('message', sa.Text, nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='pending'),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_review_requests_prompt', 'review_requests', ['prompt_id'])
    op.create_index('ix_review_requests_reviewer', 'review_requests', ['reviewer_id'])

    # Activities
    op.create_table(
        'activities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('prompts.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('prompt_slug', sa.String(100), nullable=True),
        sa.Column('prompt_name', sa.String(255), nullable=True),
        sa.Column('version', sa.String(50), nullable=True),
        sa.Column('actor_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('actor_name', sa.String(255), nullable=True),
        sa.Column('actor_email', sa.String(255), nullable=True),
        sa.Column('activity_type', sa.String(50), nullable=False, index=True),
        sa.Column('description', sa.Text, nullable=False),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('is_public', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_activities_prompt', 'activities', ['prompt_id'])
    op.create_index('ix_activities_actor', 'activities', ['actor_id'])
    op.create_index('ix_activities_type', 'activities', ['activity_type'])
    op.create_index('ix_activities_created', 'activities', ['created_at'])

    # Usage Metrics
    op.create_table(
        'usage_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('metric_type', sa.String(50), nullable=False, index=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('model_id', sa.String(100), nullable=True),
        sa.Column('value', sa.Float, nullable=False, server_default='1.0'),
        sa.Column('unit', sa.String(20), nullable=True),
        sa.Column('metadata', postgresql.JSONB, nullable=True),
        sa.Column('hour', sa.Integer, nullable=False),
        sa.Column('day', sa.Integer, nullable=False),
        sa.Column('week', sa.Integer, nullable=False),
        sa.Column('month', sa.Integer, nullable=False),
        sa.Column('year', sa.Integer, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_usage_metrics_type_day', 'usage_metrics', ['metric_type', 'day'])
    op.create_index('ix_usage_metrics_user_type', 'usage_metrics', ['user_id', 'metric_type'])
    op.create_index('ix_usage_metrics_prompt_type', 'usage_metrics', ['prompt_id', 'metric_type'])
    op.create_index('ix_usage_metrics_created', 'usage_metrics', ['created_at'])

    # Aggregated Metrics
    op.create_table(
        'aggregated_metrics',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('metric_type', sa.String(50), nullable=False, index=True),
        sa.Column('granularity', sa.String(20), nullable=False, index=True),
        sa.Column('period_start', sa.DateTime, nullable=False, index=True),
        sa.Column('period_end', sa.DateTime, nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('prompt_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('model_id', sa.String(100), nullable=True),
        sa.Column('total_value', sa.Float, nullable=False, server_default='0.0'),
        sa.Column('count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('min_value', sa.Float, nullable=True),
        sa.Column('max_value', sa.Float, nullable=True),
        sa.Column('avg_value', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        'ix_agg_metrics_unique', 
        'aggregated_metrics', 
        ['metric_type', 'granularity', 'period_start', 'user_id', 'team_id', 'prompt_id', 'model_id'],
        unique=True
    )
    op.create_index('ix_agg_metrics_period', 'aggregated_metrics', ['period_start', 'granularity'])


def downgrade() -> None:
    op.drop_table('aggregated_metrics')
    op.drop_table('usage_metrics')
    op.drop_table('activities')
    op.drop_table('review_requests')
    op.drop_table('reviews')
    op.drop_table('comments')
    op.drop_table('template_usages')
    op.drop_table('template_versions')
    op.drop_table('prompt_templates')
    op.drop_table('benchmark_test_cases')
    op.drop_table('benchmark_suites')
