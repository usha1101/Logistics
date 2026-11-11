"""create agent intelligence tables

Revision ID: 0009_create_agent_intelligence_tables
Revises: 0008_create_disruption_tables
Create Date: 2026-11-11 20:16:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0009_create_agent_intelligence_tables'
down_revision = '0008_create_disruption_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. agent_runs table
    op.create_table(
        'agent_runs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('disruption_id', sa.String(length=36), nullable=False),
        sa.Column('simulation_id', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('primary_provider', sa.String(length=32), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('execution_duration_ms', sa.Float(), nullable=True),
        sa.Column('error_summary', sa.String(length=1024), nullable=True),
        sa.Column('created_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['disruption_id'], ['disruptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['simulation_id'], ['simulations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_runs_id'), 'agent_runs', ['id'], unique=False)
    op.create_index(op.f('ix_agent_runs_disruption_id'), 'agent_runs', ['disruption_id'], unique=False)
    op.create_index(op.f('ix_agent_runs_simulation_id'), 'agent_runs', ['simulation_id'], unique=False)
    op.create_index(op.f('ix_agent_runs_status'), 'agent_runs', ['status'], unique=False)
    op.create_index('ix_agent_runs_disr_status', 'agent_runs', ['disruption_id', 'status'], unique=False)

    # 2. agent_executions table
    op.create_table(
        'agent_executions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('agent_run_id', sa.String(length=36), nullable=False),
        sa.Column('agent_name', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('provider', sa.String(length=32), nullable=False),
        sa.Column('model', sa.String(length=64), nullable=False),
        sa.Column('input_summary', sa.String(length=1024), nullable=True),
        sa.Column('output', sa.JSON(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('evidence_references', sa.JSON(), nullable=True),
        sa.Column('warnings', sa.JSON(), nullable=True),
        sa.Column('execution_duration_ms', sa.Float(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['agent_run_id'], ['agent_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_executions_id'), 'agent_executions', ['id'], unique=False)
    op.create_index(op.f('ix_agent_executions_agent_run_id'), 'agent_executions', ['agent_run_id'], unique=False)
    op.create_index(op.f('ix_agent_executions_agent_name'), 'agent_executions', ['agent_name'], unique=False)
    op.create_index(op.f('ix_agent_executions_status'), 'agent_executions', ['status'], unique=False)
    op.create_index('ix_agent_exec_run_agent', 'agent_executions', ['agent_run_id', 'agent_name'], unique=False)

    # 3. agent_recommendations table
    op.create_table(
        'agent_recommendations',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('agent_run_id', sa.String(length=36), nullable=False),
        sa.Column('source_agent', sa.String(length=64), nullable=False),
        sa.Column('recommendation_type', sa.String(length=64), nullable=False),
        sa.Column('priority', sa.String(length=32), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('target_resource_type', sa.String(length=64), nullable=True),
        sa.Column('target_resource_id', sa.String(length=64), nullable=True),
        sa.Column('evidence', sa.JSON(), nullable=True),
        sa.Column('validation_status', sa.String(length=32), nullable=False),
        sa.Column('execution_status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['agent_run_id'], ['agent_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_recommendations_id'), 'agent_recommendations', ['id'], unique=False)
    op.create_index(op.f('ix_agent_recommendations_agent_run_id'), 'agent_recommendations', ['agent_run_id'], unique=False)
    op.create_index(op.f('ix_agent_recommendations_recommendation_type'), 'agent_recommendations', ['recommendation_type'], unique=False)
    op.create_index(op.f('ix_agent_recommendations_priority'), 'agent_recommendations', ['priority'], unique=False)
    op.create_index(op.f('ix_agent_recommendations_validation_status'), 'agent_recommendations', ['validation_status'], unique=False)
    op.create_index('ix_agent_rec_run_priority', 'agent_recommendations', ['agent_run_id', 'priority'], unique=False)


def downgrade() -> None:
    op.drop_table('agent_recommendations')
    op.drop_table('agent_executions')
    op.drop_table('agent_runs')

