"""create_stacks_table

Revision ID: 0005_stack_persistence
Revises: 0004_graph_indexes
Create Date: 2026-09-17 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0005_stack_persistence"
down_revision: Union[str, None] = "0004_graph_indexes"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stacks",
        sa.Column("id", sa.String(length=255), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False, server_default="1.0.0"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("robot_domain", sa.String(length=100), nullable=False, server_default="general_robotics"),
        sa.Column("robot_type", sa.String(length=100), nullable=False, server_default="custom"),
        sa.Column("target_os", sa.String(length=100), nullable=True),
        sa.Column("target_arch", sa.String(length=100), nullable=True),
        sa.Column("target_ros_distro", sa.String(length=100), nullable=True),
        sa.Column("components_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stacks_name", "stacks", ["name"], unique=False)
    op.create_index("ix_stacks_updated_at", "stacks", ["updated_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_stacks_updated_at", table_name="stacks")
    op.drop_index("ix_stacks_name", table_name="stacks")
    op.drop_table("stacks")
