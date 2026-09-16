"""add_resource_metadata

Revision ID: 0002_resource_metadata
Revises: 0001_initial_schema
Create Date: 2026-09-16 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_resource_metadata'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('resources', sa.Column('robotics_domains', sa.JSON(), nullable=True))
    op.add_column('resources', sa.Column('capabilities', sa.JSON(), nullable=True))
    op.add_column('resources', sa.Column('platforms', sa.JSON(), nullable=True))
    op.add_column('resources', sa.Column('metadata_json', sa.JSON(), nullable=True))

def downgrade() -> None:
    op.drop_column('resources', 'metadata_json')
    op.drop_column('resources', 'platforms')
    op.drop_column('resources', 'capabilities')
    op.drop_column('resources', 'robotics_domains')
