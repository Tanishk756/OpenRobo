"""Add paused_from_state to deployments for truthful pause restoration.

Revision ID: 0009_add_paused_from_state
Revises: 0008_deployment_lease_and_hardening
Create Date: 2026-09-18 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0009_add_paused_from_state'
down_revision: Union[str, None] = '0008_deployment_lease_and_hardening'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('deployments', sa.Column('paused_from_state', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('deployments', 'paused_from_state')
