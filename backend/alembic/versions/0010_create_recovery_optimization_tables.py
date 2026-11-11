"""create recovery optimization tables

Revision ID: 0010_create_recovery_optimization_tables
Revises: 0009_create_agent_intelligence_tables
Create Date: 2026-11-11 20:38:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0010_create_recovery_optimization_tables'
down_revision = '0009_create_agent_intelligence_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. recovery_plans
    op.create_table(
        'recovery_plans',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('recovery_code', sa.String(length=64), nullable=False),
        sa.Column('disruption_id', sa.String(length=36), nullable=False),
        sa.Column('simulation_id', sa.String(length=64), nullable=True),
        sa.Column('agent_run_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('optimization_strategy', sa.String(length=64), nullable=False),
        sa.Column('objective_value', sa.Float(), nullable=True),
        sa.Column('estimated_total_distance_km', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('estimated_total_travel_time_minutes', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('estimated_total_delay_minutes', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('estimated_recovery_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('affected_order_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reassigned_order_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('assigned_vehicle_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('optimization_metadata', sa.JSON(), nullable=True),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('approved_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejected_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['agent_run_id'], ['agent_runs.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['disruption_id'], ['disruptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['simulation_id'], ['simulations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('recovery_code', name='uq_recovery_code'),
    )
    op.create_index(op.f('ix_recovery_plans_id'), 'recovery_plans', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_plans_recovery_code'), 'recovery_plans', ['recovery_code'], unique=False)
    op.create_index(op.f('ix_recovery_plans_disruption_id'), 'recovery_plans', ['disruption_id'], unique=False)
    op.create_index(op.f('ix_recovery_plans_status'), 'recovery_plans', ['status'], unique=False)
    op.create_index('ix_recovery_plans_disr_status', 'recovery_plans', ['disruption_id', 'status'], unique=False)

    # 2. recovery_assignments
    op.create_table(
        'recovery_assignments',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('recovery_plan_id', sa.String(length=36), nullable=False),
        sa.Column('order_id', sa.String(length=36), nullable=False),
        sa.Column('previous_vehicle_id', sa.String(length=36), nullable=True),
        sa.Column('proposed_vehicle_id', sa.String(length=36), nullable=False),
        sa.Column('origin_node_id', sa.String(length=36), nullable=False),
        sa.Column('destination_node_id', sa.String(length=36), nullable=False),
        sa.Column('proposed_route_node_ids', sa.JSON(), nullable=False),
        sa.Column('proposed_route_edge_ids', sa.JSON(), nullable=False),
        sa.Column('estimated_distance_km', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('estimated_travel_time_minutes', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('estimated_delay_minutes', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('order_priority', sa.String(length=32), nullable=False, server_default='NORMAL'),
        sa.Column('assignment_reason', sa.String(length=512), nullable=True),
        sa.Column('validation_status', sa.String(length=32), nullable=False, server_default='VALIDATED'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['destination_node_id'], ['network_nodes.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['origin_node_id'], ['network_nodes.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['previous_vehicle_id'], ['vehicles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['proposed_vehicle_id'], ['vehicles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recovery_plan_id'], ['recovery_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_assignments_id'), 'recovery_assignments', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_assignments_recovery_plan_id'), 'recovery_assignments', ['recovery_plan_id'], unique=False)
    op.create_index(op.f('ix_recovery_assignments_order_id'), 'recovery_assignments', ['order_id'], unique=False)
    op.create_index('ix_recovery_assignments_plan_order', 'recovery_assignments', ['recovery_plan_id', 'order_id'], unique=False)

    # 3. recovery_actions
    op.create_table(
        'recovery_actions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('recovery_plan_id', sa.String(length=36), nullable=False),
        sa.Column('action_type', sa.String(length=64), nullable=False),
        sa.Column('target_resource_type', sa.String(length=64), nullable=False),
        sa.Column('target_resource_id', sa.String(length=64), nullable=False),
        sa.Column('action_payload', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('execution_result', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.String(length=1024), nullable=True),
        sa.Column('executed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['recovery_plan_id'], ['recovery_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_actions_id'), 'recovery_actions', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_actions_recovery_plan_id'), 'recovery_actions', ['recovery_plan_id'], unique=False)
    op.create_index(op.f('ix_recovery_actions_action_type'), 'recovery_actions', ['action_type'], unique=False)
    op.create_index(op.f('ix_recovery_actions_status'), 'recovery_actions', ['status'], unique=False)

    # 4. recovery_audit_logs
    op.create_table(
        'recovery_audit_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('recovery_plan_id', sa.String(length=36), nullable=False),
        sa.Column('action', sa.String(length=64), nullable=False),
        sa.Column('previous_status', sa.String(length=32), nullable=True),
        sa.Column('new_status', sa.String(length=32), nullable=False),
        sa.Column('performed_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['performed_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['recovery_plan_id'], ['recovery_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_audit_logs_id'), 'recovery_audit_logs', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_audit_logs_recovery_plan_id'), 'recovery_audit_logs', ['recovery_plan_id'], unique=False)
    op.create_index(op.f('ix_recovery_audit_logs_action'), 'recovery_audit_logs', ['action'], unique=False)

    # 5. recovery_comparisons
    op.create_table(
        'recovery_comparisons',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('recovery_plan_id', sa.String(length=36), nullable=False),
        sa.Column('metric_name', sa.String(length=64), nullable=False),
        sa.Column('baseline_value', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('proposed_value', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('improvement_value', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('improvement_percentage', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('unit', sa.String(length=32), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['recovery_plan_id'], ['recovery_plans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recovery_comparisons_id'), 'recovery_comparisons', ['id'], unique=False)
    op.create_index(op.f('ix_recovery_comparisons_recovery_plan_id'), 'recovery_comparisons', ['recovery_plan_id'], unique=False)
    op.create_index(op.f('ix_recovery_comparisons_metric_name'), 'recovery_comparisons', ['metric_name'], unique=False)


def downgrade() -> None:
    op.drop_table('recovery_comparisons')
    op.drop_table('recovery_audit_logs')
    op.drop_table('recovery_actions')
    op.drop_table('recovery_assignments')
    op.drop_table('recovery_plans')

