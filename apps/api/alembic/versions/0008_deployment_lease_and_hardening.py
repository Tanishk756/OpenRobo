"""Add device deployment leases and idempotency / rejection fields.

Revision ID: 0008_deployment_lease_and_hardening
Revises: 0007_deployment_orchestration
Create Date: 2026-09-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008_deployment_lease_and_hardening'
down_revision: Union[str, None] = '0007_deployment_orchestration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'device_deployment_leases',
        sa.Column('device_id', sa.String(length=64), sa.ForeignKey('fleet_devices.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('deployment_id', sa.String(length=36), sa.ForeignKey('deployments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('generation', sa.BigInteger(), nullable=False),
        sa.Column('acquired_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_device_deployment_leases_deployment_id', 'device_deployment_leases', ['deployment_id'], unique=False)

    op.add_column('deployments', sa.Column('request_digest', sa.String(length=64), nullable=True))
    op.add_column('deployment_instructions', sa.Column('rejection_reason', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('deployment_instructions', 'rejection_reason')
    op.drop_column('deployments', 'request_digest')
    op.drop_index('ix_device_deployment_leases_deployment_id', table_name='device_deployment_leases')
    op.drop_table('device_deployment_leases')
