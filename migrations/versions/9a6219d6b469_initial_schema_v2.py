"""initial_schema_v2

Revision ID: 9a6219d6b469
Revises: 
Create Date: 2026-09-13 13:07:26.446204

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9a6219d6b469'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('fraud_alerts', sa.Column('incident_id', sa.Integer(), nullable=True))
    op.create_index('ix_fraud_alerts_incident_id', 'fraud_alerts', ['incident_id'], unique=False)

    op.add_column('login_sessions', sa.Column('step_up_token', sa.String(length=64), nullable=True))
    op.add_column('login_sessions', sa.Column('step_up_expires_at', sa.DateTime(), nullable=True))
    op.create_index('ix_login_sessions_step_up_token', 'login_sessions', ['step_up_token'], unique=True)

    op.add_column('risk_assessments', sa.Column('action_taken', sa.String(length=40), nullable=True))
    op.add_column('risk_assessments', sa.Column('anomaly_details', sa.JSON(), nullable=True))

    op.add_column('transactions', sa.Column('idempotency_key', sa.String(length=64), nullable=True))
    op.create_index('ix_transactions_idempotency_key', 'transactions', ['idempotency_key'], unique=False)


def downgrade():
    op.drop_index('ix_transactions_idempotency_key', table_name='transactions')
    op.drop_column('transactions', 'idempotency_key')

    op.drop_column('risk_assessments', 'anomaly_details')
    op.drop_column('risk_assessments', 'action_taken')

    op.drop_index('ix_login_sessions_step_up_token', table_name='login_sessions')
    op.drop_column('login_sessions', 'step_up_expires_at')
    op.drop_column('login_sessions', 'step_up_token')

    op.drop_index('ix_fraud_alerts_incident_id', table_name='fraud_alerts')
    op.drop_column('fraud_alerts', 'incident_id')

    # ### end Alembic commands ###
