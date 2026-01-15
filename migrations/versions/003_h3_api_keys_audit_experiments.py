"""H3: API Keys, Audit Logs, and Experiments

Revision ID: 003_h3_api_keys_audit_experiments
Revises: 002_h2_models
Create Date: 2026-01-14

This migration adds:
- api_keys: For programmatic API access
- audit_logs: For tracking all user actions
- experiments: For A/B testing
- experiment_events: For recording experiment metrics
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '003_h3_api_keys_audit_experiments'
down_revision: Union[str, None] = '002_h2_models'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create api_keys table
    op.create_table(
        'api_keys',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('key_prefix', sa.String(12), nullable=False),
        sa.Column('key_hash', sa.String(64), nullable=False),
        sa.Column('scopes', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('use_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('revoked_at', sa.DateTime(), nullable=True),
        sa.Column('revoked_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('revoked_reason', sa.String(500), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('allowed_ips', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key_prefix'),
        sa.UniqueConstraint('key_hash'),
    )
    op.create_index('ix_api_keys_created_by', 'api_keys', ['created_by'])
    op.create_index('ix_api_keys_active', 'api_keys', ['is_active'])
    op.create_index('ix_api_keys_expires_at', 'api_keys', ['expires_at'])
    op.create_index('ix_api_keys_organization_id', 'api_keys', ['organization_id'])

    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('api_key_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('action', sa.String(50), nullable=False),
        sa.Column('resource_type', sa.String(50), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('old_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('user_agent', sa.String(500), nullable=True),
        sa.Column('request_id', sa.String(64), nullable=True),
        sa.Column('endpoint', sa.String(200), nullable=True),
        sa.Column('http_method', sa.String(10), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_logs_user_id', 'audit_logs', ['user_id'])
    op.create_index('ix_audit_logs_api_key_id', 'audit_logs', ['api_key_id'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])
    op.create_index('ix_audit_logs_resource_type', 'audit_logs', ['resource_type'])
    op.create_index('ix_audit_logs_resource_id', 'audit_logs', ['resource_id'])
    op.create_index('ix_audit_logs_request_id', 'audit_logs', ['request_id'])
    op.create_index('ix_audit_logs_timestamp', 'audit_logs', ['timestamp'])
    op.create_index('ix_audit_logs_user_action', 'audit_logs', ['user_id', 'action'])
    op.create_index('ix_audit_logs_resource', 'audit_logs', ['resource_type', 'resource_id'])

    # Create experiments table
    op.create_table(
        'experiments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('variants', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('traffic_split', sa.String(50), nullable=False, server_default='equal'),
        sa.Column('traffic_percentage', sa.Float(), nullable=False, server_default='100.0'),
        sa.Column('min_sample_size', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('max_duration_days', sa.Integer(), nullable=False, server_default='14'),
        sa.Column('confidence_threshold', sa.Float(), nullable=False, server_default='0.95'),
        sa.Column('auto_promote', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('ended_at', sa.DateTime(), nullable=True),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('winner_variant_id', sa.String(100), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tags', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_experiments_status', 'experiments', ['status'])
    op.create_index('ix_experiments_created_by', 'experiments', ['created_by'])
    op.create_index('ix_experiments_started_at', 'experiments', ['started_at'])
    op.create_index('ix_experiments_organization_id', 'experiments', ['organization_id'])

    # Create experiment_events table
    op.create_table(
        'experiment_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('experiment_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('variant_id', sa.String(100), nullable=False),
        sa.Column('user_id', sa.String(100), nullable=False),
        sa.Column('session_id', sa.String(100), nullable=True),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('value', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('metric_id', sa.String(100), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['experiment_id'], ['experiments.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_experiment_events_experiment_id', 'experiment_events', ['experiment_id'])
    op.create_index('ix_experiment_events_variant_id', 'experiment_events', ['variant_id'])
    op.create_index('ix_experiment_events_user_id', 'experiment_events', ['user_id'])
    op.create_index('ix_experiment_events_event_type', 'experiment_events', ['event_type'])
    op.create_index('ix_experiment_events_timestamp', 'experiment_events', ['timestamp'])
    op.create_index('ix_experiment_events_experiment_variant', 'experiment_events', ['experiment_id', 'variant_id'])


def downgrade() -> None:
    # Drop experiment_events table
    op.drop_index('ix_experiment_events_experiment_variant', table_name='experiment_events')
    op.drop_index('ix_experiment_events_timestamp', table_name='experiment_events')
    op.drop_index('ix_experiment_events_event_type', table_name='experiment_events')
    op.drop_index('ix_experiment_events_user_id', table_name='experiment_events')
    op.drop_index('ix_experiment_events_variant_id', table_name='experiment_events')
    op.drop_index('ix_experiment_events_experiment_id', table_name='experiment_events')
    op.drop_table('experiment_events')

    # Drop experiments table
    op.drop_index('ix_experiments_organization_id', table_name='experiments')
    op.drop_index('ix_experiments_started_at', table_name='experiments')
    op.drop_index('ix_experiments_created_by', table_name='experiments')
    op.drop_index('ix_experiments_status', table_name='experiments')
    op.drop_table('experiments')

    # Drop audit_logs table
    op.drop_index('ix_audit_logs_resource', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_timestamp', table_name='audit_logs')
    op.drop_index('ix_audit_logs_request_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_resource_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_resource_type', table_name='audit_logs')
    op.drop_index('ix_audit_logs_action', table_name='audit_logs')
    op.drop_index('ix_audit_logs_api_key_id', table_name='audit_logs')
    op.drop_index('ix_audit_logs_user_id', table_name='audit_logs')
    op.drop_table('audit_logs')

    # Drop api_keys table
    op.drop_index('ix_api_keys_organization_id', table_name='api_keys')
    op.drop_index('ix_api_keys_expires_at', table_name='api_keys')
    op.drop_index('ix_api_keys_active', table_name='api_keys')
    op.drop_index('ix_api_keys_created_by', table_name='api_keys')
    op.drop_table('api_keys')
