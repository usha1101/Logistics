"""create reports table

Revision ID: 0011_create_reports_table
Revises: 0010_create_recovery_optimization_tables
Create Date: 2026-11-11 21:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0011_create_reports_table'
down_revision = '0010_create_recovery_optimization_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'reports',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('report_code', sa.String(length=64), nullable=False),
        sa.Column('report_type', sa.String(length=64), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False, server_default='LOGIPULSE Analytics Report'),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='COMPLETED'),
        sa.Column('requested_by_user_id', sa.String(length=36), nullable=True),
        sa.Column('simulation_id', sa.String(length=64), nullable=True),
        sa.Column('include_simulations', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('start_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('end_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('filters', sa.JSON(), nullable=True),
        sa.Column('summary_metrics', sa.JSON(), nullable=True),
        sa.Column('include_charts', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('file_reference', sa.String(length=255), nullable=True),
        sa.Column('file_name', sa.String(length=255), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['requested_by_user_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['simulation_id'], ['simulations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('report_code', name='uq_report_code'),
    )
    op.create_index(op.f('ix_reports_id'), 'reports', ['id'], unique=False)
    op.create_index(op.f('ix_reports_report_code'), 'reports', ['report_code'], unique=False)
    op.create_index(op.f('ix_reports_report_type'), 'reports', ['report_type'], unique=False)
    op.create_index(op.f('ix_reports_status'), 'reports', ['status'], unique=False)
    op.create_index(op.f('ix_reports_requested_by_user_id'), 'reports', ['requested_by_user_id'], unique=False)
    op.create_index(op.f('ix_reports_simulation_id'), 'reports', ['simulation_id'], unique=False)
    op.create_index(op.f('ix_reports_created_at'), 'reports', ['created_at'], unique=False)
    op.create_index('ix_reports_type_status', 'reports', ['report_type', 'status'], unique=False)


def downgrade() -> None:
    op.drop_table('reports')
