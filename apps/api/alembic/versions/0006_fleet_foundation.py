"""create_fleet_foundation_tables

Revision ID: 0006_fleet_foundation
Revises: 0005_stack_persistence
Create Date: 2026-09-17 19:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0006_fleet_foundation"
down_revision: Union[str, None] = "0005_stack_persistence"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "fleet_devices",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("domain", sa.String(length=100), nullable=False, server_default="general_robotics"),
        sa.Column("robot_type", sa.String(length=100), nullable=False, server_default="custom"),
        sa.Column("certificate_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("certificate_serial", sa.String(length=100), nullable=True),
        sa.Column("certificate_pem", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="ENROLLED"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=255), nullable=True),
        sa.Column("capabilities_json", sa.JSON(), nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_heartbeat_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_fleet_devices_name", "fleet_devices", ["name"], unique=False)
    op.create_index("ix_fleet_devices_fingerprint", "fleet_devices", ["certificate_fingerprint"], unique=True)
    op.create_index("ix_fleet_devices_serial", "fleet_devices", ["certificate_serial"], unique=True)

    op.create_table(
        "agent_enrollment_tokens",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_used", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by_device_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_enrollment_tokens_hash", "agent_enrollment_tokens", ["token_hash"], unique=True)

    op.create_table(
        "agent_heartbeats",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("device_id", sa.String(length=36), sa.ForeignKey("fleet_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_heartbeats_device_id", "agent_heartbeats", ["device_id"], unique=False)

    op.create_table(
        "agent_telemetry_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("device_id", sa.String(length=36), sa.ForeignKey("fleet_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_telemetry_events_device_id", "agent_telemetry_events", ["device_id"], unique=False)
    op.create_index("ix_telemetry_events_message_id", "agent_telemetry_events", ["message_id"], unique=True)


def downgrade() -> None:
    op.drop_table("agent_telemetry_events")
    op.drop_table("agent_heartbeats")
    op.drop_table("agent_enrollment_tokens")
    op.drop_table("fleet_devices")
