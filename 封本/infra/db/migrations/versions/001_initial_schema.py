"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Decisions table
    op.create_table(
        'decisions',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('symbol', sa.Text(), nullable=False),
        sa.Column('direction', sa.Text(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('regime', sa.Text(), nullable=False),
        sa.Column('entry_permission', sa.Boolean(), nullable=False, default=True),
        sa.Column('no_trade_reason', sa.Text()),
        sa.Column('max_position_pct', sa.Float(), nullable=False, default=0.1),
        sa.Column('suggested_quantity', sa.Float()),
        sa.Column('execution_style', sa.Text(), nullable=False, default='market'),
        sa.Column('limit_price', sa.Float()),
        sa.Column('stop_price', sa.Float()),
        sa.Column('stop_logic', sa.JSON()),
        sa.Column('take_profit', sa.Float()),
        sa.Column('engine_signals', sa.JSON(), nullable=False, default={}),
        sa.Column('consensus_score', sa.Float(), nullable=False, default=0.5),
        sa.Column('reasoning', sa.Text()),
        sa.Column('key_factors', sa.JSON(), default=[]),
        sa.Column('version', sa.Text(), nullable=False, default='1.0.0'),
        sa.Column('metadata', sa.JSON(), default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_decisions_symbol', 'decisions', ['symbol'])
    op.create_index('idx_decisions_timestamp', 'decisions', [sa.text('timestamp DESC')])

    # Orders table
    op.create_table(
        'orders',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('decision_id', sa.Text(), sa.ForeignKey('decisions.id')),
        sa.Column('symbol', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('side', sa.Text(), nullable=False),
        sa.Column('order_type', sa.Text(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('price', sa.Float()),
        sa.Column('stop_price', sa.Float()),
        sa.Column('status', sa.Text(), nullable=False, default='pending'),
        sa.Column('submitted_at', sa.DateTime(timezone=True)),
        sa.Column('filled_at', sa.DateTime(timezone=True)),
        sa.Column('cancelled_at', sa.DateTime(timezone=True)),
        sa.Column('filled_quantity', sa.Float(), nullable=False, default=0),
        sa.Column('avg_fill_price', sa.Float()),
        sa.Column('slippage_bps', sa.Float()),
        sa.Column('execution_quality', sa.Text()),
        sa.Column('exchange_order_id', sa.Text()),
        sa.Column('exchange', sa.Text()),
        sa.Column('metadata', sa.JSON(), default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_orders_decision', 'orders', ['decision_id'])
    op.create_index('idx_orders_symbol', 'orders', ['symbol'])
    op.create_index('idx_orders_timestamp', 'orders', [sa.text('timestamp DESC')])

    # Fills table
    op.create_table(
        'fills',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('order_id', sa.Text(), sa.ForeignKey('orders.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('side', sa.Text(), nullable=False),
        sa.Column('commission', sa.Float(), nullable=False, default=0),
        sa.Column('commission_currency', sa.Text(), nullable=False, default='USD'),
        sa.Column('is_maker', sa.Boolean()),
        sa.Column('liquidity_type', sa.Text()),
        sa.Column('exchange_fill_id', sa.Text()),
        sa.Column('venue', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_fills_order', 'fills', ['order_id'])

    # Risk events table
    op.create_table(
        'risk_events',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.Text(), nullable=False),
        sa.Column('symbol', sa.Text()),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('triggered_value', sa.Float(), nullable=False),
        sa.Column('threshold_value', sa.Float(), nullable=False),
        sa.Column('action_taken', sa.Text(), nullable=False),
        sa.Column('position_closed', sa.Boolean(), nullable=False, default=False),
        sa.Column('order_cancelled', sa.Boolean(), nullable=False, default=False),
        sa.Column('decision_id', sa.Text(), sa.ForeignKey('decisions.id')),
        sa.Column('metadata', sa.JSON(), default={}),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_risk_events_timestamp', 'risk_events', [sa.text('timestamp DESC')])

    # Audit log table
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('record_type', sa.Text(), nullable=False),
        sa.Column('entity_type', sa.Text(), nullable=False),
        sa.Column('entity_id', sa.Text(), nullable=False),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('actor', sa.Text(), nullable=False, default='system'),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('before_state', sa.JSON()),
        sa.Column('after_state', sa.JSON()),
        sa.Column('reason', sa.Text()),
        sa.Column('correlation_id', sa.Text()),
        sa.Column('metadata', sa.JSON(), default={}),
        sa.Column('checksum', sa.Text()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('idx_audit_timestamp', 'audit_log', [sa.text('timestamp DESC')])

    # Model registry table
    op.create_table(
        'model_registry',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('version', sa.Text(), nullable=False),
        sa.Column('model_type', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.Text(), nullable=False, default='system'),
        sa.Column('training_start', sa.DateTime(timezone=True)),
        sa.Column('training_end', sa.DateTime(timezone=True)),
        sa.Column('training_samples', sa.Integer(), default=0),
        sa.Column('metrics', sa.JSON(), default={}),
        sa.Column('is_active', sa.Boolean(), nullable=False, default=False),
        sa.Column('is_production', sa.Boolean(), nullable=False, default=False),
        sa.Column('parent_model_id', sa.Text()),
        sa.Column('experiment_id', sa.Text()),
        sa.Column('config', sa.JSON(), default={}),
        sa.Column('artifacts_path', sa.Text()),
        sa.Column('metadata', sa.JSON(), default={}),
    )
    op.create_index('idx_model_registry_active', 'model_registry', ['is_active', 'is_production'])

    # Experiments table
    op.create_table(
        'experiments',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('status', sa.Text(), nullable=False, default='running'),
        sa.Column('config', sa.JSON(), default={}),
        sa.Column('results', sa.JSON(), default={}),
        sa.Column('metrics', sa.JSON(), default={}),
        sa.Column('model_ids', sa.JSON(), default=[]),
        sa.Column('dataset_version', sa.Text()),
        sa.Column('metadata', sa.JSON(), default={}),
    )
    op.create_index('idx_experiments_status', 'experiments', ['status'])

    # Live feedback table
    op.create_table(
        'live_feedback',
        sa.Column('id', sa.Text(), primary_key=True),
        sa.Column('decision_id', sa.Text(), sa.ForeignKey('decisions.id'), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('pnl', sa.Float()),
        sa.Column('pnl_pct', sa.Float()),
        sa.Column('holding_period_seconds', sa.Integer()),
        sa.Column('outcome', sa.Text()),
        sa.Column('actual_return', sa.Float()),
        sa.Column('predicted_return', sa.Float()),
        sa.Column('key_lessons', sa.Text()),
        sa.Column('notes', sa.Text()),
        sa.Column('metadata', sa.JSON(), default={}),
    )
    op.create_index('idx_feedback_decision', 'live_feedback', ['decision_id'])


def downgrade() -> None:
    op.drop_table('live_feedback')
    op.drop_table('experiments')
    op.drop_table('model_registry')
    op.drop_table('audit_log')
    op.drop_table('risk_events')
    op.drop_table('fills')
    op.drop_table('orders')
    op.drop_table('decisions')
