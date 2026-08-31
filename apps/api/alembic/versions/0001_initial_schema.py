"""initial_schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-08-31 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'resources',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', sa.String(length=100), nullable=False),
        sa.Column('summary', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('spdx_license_id', sa.String(length=100), nullable=False),
        sa.Column('repo_url', sa.String(length=500), nullable=True),
        sa.Column('evidence_level', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resources_name'), 'resources', ['name'], unique=False)
    op.create_index(op.f('ix_resources_type'), 'resources', ['type'], unique=False)

    op.create_table(
        'graph_nodes',
        sa.Column('id', sa.String(length=255), nullable=False),
        sa.Column('node_type', sa.String(length=100), nullable=False),
        sa.Column('properties_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_graph_nodes_node_type'), 'graph_nodes', ['node_type'], unique=False)

    op.create_table(
        'graph_edges',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('subject_id', sa.String(length=255), nullable=False),
        sa.Column('predicate', sa.String(length=100), nullable=False),
        sa.Column('object_id', sa.String(length=255), nullable=False),
        sa.Column('properties_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['object_id'], ['graph_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subject_id'], ['graph_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_graph_edges_predicate'), 'graph_edges', ['predicate'], unique=False)
    op.create_index(op.f('ix_graph_edges_subject_id'), 'graph_edges', ['subject_id'], unique=False)
    op.create_index(op.f('ix_graph_edges_object_id'), 'graph_edges', ['object_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_graph_edges_object_id'), table_name='graph_edges')
    op.drop_index(op.f('ix_graph_edges_subject_id'), table_name='graph_edges')
    op.drop_index(op.f('ix_graph_edges_predicate'), table_name='graph_edges')
    op.drop_table('graph_edges')
    op.drop_index(op.f('ix_graph_nodes_node_type'), table_name='graph_nodes')
    op.drop_table('graph_nodes')
    op.drop_index(op.f('ix_resources_type'), table_name='resources')
    op.drop_index(op.f('ix_resources_name'), table_name='resources')
    op.drop_table('resources')
