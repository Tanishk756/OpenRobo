"""add_search_indexes

Revision ID: 0003_search_indexes
Revises: 0002_resource_metadata
Create Date: 2026-09-16 15:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = "0003_search_indexes"
down_revision: Union[str, None] = "0002_resource_metadata"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
        op.execute("CREATE INDEX IF NOT EXISTS idx_resources_name_trgm ON resources USING GIN (name gin_trgm_ops);")
        op.execute("CREATE INDEX IF NOT EXISTS idx_resources_id_trgm ON resources USING GIN (id gin_trgm_ops);")
        op.execute(
            "CREATE INDEX IF NOT EXISTS idx_resources_fts ON resources USING GIN ("
            "to_tsvector('english', coalesce(name, '') || ' ' || coalesce(id, '') || ' ' || coalesce(summary, '') || ' ' || coalesce(description, ''))"
            ");"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS idx_resources_fts;")
        op.execute("DROP INDEX IF EXISTS idx_resources_id_trgm;")
        op.execute("DROP INDEX IF EXISTS idx_resources_name_trgm;")
