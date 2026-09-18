"""create_deployment_orchestration_tables

Revision ID: 0007_deployment_orchestration
Revises: 0006_fleet_foundation
Create Date: 2026-09-18 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0007_deployment_orchestration"
down_revision: Union[str, None] = "0006_fleet_foundation"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    # 1. release_artifacts
    op.create_table(
        "release_artifacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("release_id", sa.String(length=128), nullable=False),
        sa.Column("release_version", sa.String(length=64), nullable=False),
        sa.Column("manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("artifact_digest", sa.String(length=64), nullable=False),
        sa.Column("workspace_digest", sa.String(length=64), nullable=False),
        sa.Column("release_key_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_source_id", sa.String(length=64), nullable=False),
        sa.Column("target_os", sa.String(length=32), nullable=False, server_default="linux"),
        sa.Column("target_architecture", sa.String(length=32), nullable=False, server_default="x86_64"),
        sa.Column("target_ros_distro", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("immutable_after_deployment", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("registered_by", sa.String(length=128), nullable=False, server_default="configured-admin"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_release_artifacts_release_id", "release_artifacts", ["release_id"], unique=True)

    # 2. artifact_sources
    op.create_table(
        "artifact_sources",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allowed_host", sa.String(length=255), nullable=False),
        sa.Column("ca_policy", sa.String(length=255), nullable=True),
        sa.Column("max_artifact_bytes", sa.BigInteger(), nullable=False, server_default="104857600"),
        sa.Column("allow_private_network", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 3. deployments
    op.create_table(
        "deployments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("release_id", sa.String(length=128), nullable=False),
        sa.Column("release_snapshot_json", sa.Text(), nullable=False),
        sa.Column("manifest_digest", sa.String(length=64), nullable=False),
        sa.Column("artifact_digest", sa.String(length=64), nullable=False),
        sa.Column("workspace_digest", sa.String(length=64), nullable=False),
        sa.Column("release_key_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_source_id", sa.String(length=64), nullable=False),
        sa.Column("target_os", sa.String(length=32), nullable=False, server_default="linux"),
        sa.Column("target_architecture", sa.String(length=32), nullable=False, server_default="x86_64"),
        sa.Column("target_ros_distro", sa.String(length=64), nullable=True),
        sa.Column("rollout_strategy", sa.Text(), nullable=False),
        sa.Column("target_filter", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="CREATED"),
        sa.Column("current_stage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_stages", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.String(length=128), nullable=False, server_default="configured-admin"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_deployments_release_id", "deployments", ["release_id"], unique=False)
    op.create_index("ix_deployments_status", "deployments", ["status"], unique=False)
    op.create_index("ix_deployments_idempotency_key", "deployments", ["idempotency_key"], unique=True)

    # 4. device_deployments
    op.create_table(
        "device_deployments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("deployment_id", sa.String(length=36), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(length=36), sa.ForeignKey("fleet_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("staged_slot", sa.String(length=16), nullable=True),
        sa.Column("active_slot", sa.String(length=16), nullable=True),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("target_snapshot_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("deployment_id", "device_id", name="uq_deployment_device"),
    )
    op.create_index("ix_device_deployments_status", "device_deployments", ["status"], unique=False)
    op.create_index("ix_device_deployments_device_id", "device_deployments", ["device_id"], unique=False)

    # 5. deployment_instructions
    op.create_table(
        "deployment_instructions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("deployment_id", sa.String(length=36), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(length=36), sa.ForeignKey("fleet_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("generation", sa.BigInteger(), nullable=False),
        sa.Column("instruction_type", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deployment_instructions_status", "deployment_instructions", ["status"], unique=False)
    op.create_index("ix_deployment_instructions_device_id", "deployment_instructions", ["device_id"], unique=False)

    # 6. deployment_approvals
    op.create_table(
        "deployment_approvals",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("deployment_id", sa.String(length=36), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_index", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=False),
        sa.Column("previous_state", sa.String(length=32), nullable=False),
        sa.Column("new_state", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # 7. deployment_events
    op.create_table(
        "deployment_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("deployment_id", sa.String(length=36), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("details", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deployment_events_event_type", "deployment_events", ["event_type"], unique=False)
    op.create_index("ix_deployment_events_timestamp", "deployment_events", ["timestamp"], unique=False)

    # 8. deployment_counters
    op.create_table(
        "deployment_counters",
        sa.Column("counter_name", sa.String(length=64), primary_key=True),
        sa.Column("current_val", sa.BigInteger(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("deployment_counters")
    op.drop_table("deployment_events")
    op.drop_table("deployment_approvals")
    op.drop_table("deployment_instructions")
    op.drop_table("device_deployments")
    op.drop_table("deployments")
    op.drop_table("artifact_sources")
    op.drop_table("release_artifacts")
