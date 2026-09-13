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
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    fa_cols = [c['name'] for c in inspector.get_columns('fraud_alerts')]
    if 'incident_id' not in fa_cols:
        op.add_column('fraud_alerts', sa.Column('incident_id', sa.Integer(), nullable=True))
        op.create_index('ix_fraud_alerts_incident_id', 'fraud_alerts', ['incident_id'], unique=False)

    ls_cols = [c['name'] for c in inspector.get_columns('login_sessions')]
    if 'step_up_token' not in ls_cols:
        op.add_column('login_sessions', sa.Column('step_up_token', sa.String(length=64), nullable=True))
        op.add_column('login_sessions', sa.Column('step_up_expires_at', sa.DateTime(), nullable=True))
        op.create_index('ix_login_sessions_step_up_token', 'login_sessions', ['step_up_token'], unique=True)

    ra_cols = [c['name'] for c in inspector.get_columns('risk_assessments')]
    if 'action_taken' not in ra_cols:
        op.add_column('risk_assessments', sa.Column('action_taken', sa.String(length=40), nullable=True))
    if 'anomaly_details' not in ra_cols:
        op.add_column('risk_assessments', sa.Column('anomaly_details', sa.JSON(), nullable=True))

    tx_cols = [c['name'] for c in inspector.get_columns('transactions')]
    if 'idempotency_key' not in tx_cols:
        op.add_column('transactions', sa.Column('idempotency_key', sa.String(length=64), nullable=True))
        op.create_index('ix_transactions_idempotency_key', 'transactions', ['idempotency_key'], unique=False)


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    tx_cols = [c['name'] for c in inspector.get_columns('transactions')]
    if 'idempotency_key' in tx_cols:
        op.drop_index('ix_transactions_idempotency_key', table_name='transactions')
        op.drop_column('transactions', 'idempotency_key')

    ra_cols = [c['name'] for c in inspector.get_columns('risk_assessments')]
    if 'anomaly_details' in ra_cols:
        op.drop_column('risk_assessments', 'anomaly_details')
    if 'action_taken' in ra_cols:
        op.drop_column('risk_assessments', 'action_taken')

    ls_cols = [c['name'] for c in inspector.get_columns('login_sessions')]
    if 'step_up_token' in ls_cols:
        op.drop_index('ix_login_sessions_step_up_token', table_name='login_sessions')
        op.drop_column('login_sessions', 'step_up_expires_at')
        op.drop_column('login_sessions', 'step_up_token')

    fa_cols = [c['name'] for c in inspector.get_columns('fraud_alerts')]
    if 'incident_id' in fa_cols:
        op.drop_index('ix_fraud_alerts_incident_id', table_name='fraud_alerts')
        op.drop_column('fraud_alerts', 'incident_id')

    # ### end Alembic commands ###
