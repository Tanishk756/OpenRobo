"""add_graph_composite_indexes

Revision ID: 0004_graph_indexes
Revises: 0003_search_indexes
Create Date: 2026-09-17 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "0004_graph_indexes"
down_revision: Union[str, None] = "0003_search_indexes"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_graph_edges_subject_predicate",
        "graph_edges",
        ["subject_id", "predicate"],
        unique=False,
    )
    op.create_index(
        "ix_graph_edges_object_predicate",
        "graph_edges",
        ["object_id", "predicate"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_graph_edges_object_predicate", table_name="graph_edges")
    op.drop_index("ix_graph_edges_subject_predicate", table_name="graph_edges")
