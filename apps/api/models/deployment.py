"""SQLAlchemy models for release catalog, artifact distribution, deployments, outbox instructions, and audit events."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReleaseArtifactModel(Base):
    """Authoritative release catalog storing immutable release metadata."""

    __tablename__ = "release_artifacts"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    release_id: Mapped[str] = mapped_column(sa.String(128), unique=True, index=True, nullable=False)
    release_version: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    manifest_digest: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    artifact_digest: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    workspace_digest: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    release_key_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    artifact_source_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    target_os: Mapped[str] = mapped_column(sa.String(32), default="linux", nullable=False)
    target_architecture: Mapped[str] = mapped_column(sa.String(32), default="x86_64", nullable=False)
    target_ros_distro: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)

    status: Mapped[str] = mapped_column(sa.String(32), default="ACTIVE", nullable=False)
    immutable_after_deployment: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    registered_by: Mapped[str] = mapped_column(sa.String(128), default="configured-admin", nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class ArtifactSourceModel(Base):
    """Configured trusted artifact distribution endpoints."""

    __tablename__ = "artifact_sources"

    id: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    base_url: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    enabled: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)
    allowed_host: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    ca_policy: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    max_artifact_bytes: Mapped[int] = mapped_column(sa.BigInteger, default=104857600, nullable=False)  # 100 MB
    allow_private_network: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, nullable=False)


class DeploymentModel(Base):
    """Root deployment orchestration record with snapshot release evidence and rollout state."""

    __tablename__ = "deployments"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    release_id: Mapped[str] = mapped_column(sa.String(128), index=True, nullable=False)

    # Immutable release snapshot persisted at deployment creation
    release_snapshot_json: Mapped[str] = mapped_column(sa.Text, nullable=False)
    manifest_digest: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    artifact_digest: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    workspace_digest: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    release_key_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    artifact_source_id: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    target_os: Mapped[str] = mapped_column(sa.String(32), default="linux", nullable=False)
    target_architecture: Mapped[str] = mapped_column(sa.String(32), default="x86_64", nullable=False)
    target_ros_distro: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)

    rollout_strategy: Mapped[str] = mapped_column(sa.Text, nullable=False)  # JSON
    target_filter: Mapped[str] = mapped_column(sa.Text, nullable=False)  # JSON

    status: Mapped[str] = mapped_column(sa.String(32), default="CREATED", index=True, nullable=False)
    current_stage: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    total_stages: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)

    generation: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, default=1, nullable=False)  # Optimistic concurrency
    idempotency_key: Mapped[Optional[str]] = mapped_column(sa.String(128), unique=True, index=True, nullable=True)

    created_by: Mapped[str] = mapped_column(sa.String(128), default="configured-admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    device_deployments: Mapped[List["DeviceDeploymentModel"]] = relationship(
        "DeviceDeploymentModel", back_populates="deployment", cascade="all, delete-orphan"
    )
    instructions: Mapped[List["DeploymentInstructionModel"]] = relationship(
        "DeploymentInstructionModel", back_populates="deployment", cascade="all, delete-orphan"
    )
    approvals: Mapped[List["DeploymentApprovalModel"]] = relationship(
        "DeploymentApprovalModel", back_populates="deployment", cascade="all, delete-orphan"
    )
    events: Mapped[List["DeploymentEventModel"]] = relationship(
        "DeploymentEventModel", back_populates="deployment", cascade="all, delete-orphan"
    )


class DeviceDeploymentModel(Base):
    """Per-device deployment state machine and immutable cohort target assignment."""

    __tablename__ = "device_deployments"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deployment_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[str] = mapped_column(sa.String(64), sa.ForeignKey("fleet_devices.id", ondelete="CASCADE"), nullable=False)

    stage_index: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(sa.String(32), default="PENDING", index=True, nullable=False)
    generation: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)

    error_message: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    staged_slot: Mapped[Optional[str]] = mapped_column(sa.String(16), nullable=True)
    active_slot: Mapped[Optional[str]] = mapped_column(sa.String(16), nullable=True)

    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)
    target_snapshot_json: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    deployment: Mapped["DeploymentModel"] = relationship("DeploymentModel", back_populates="device_deployments")

    __table_args__ = (sa.UniqueConstraint("deployment_id", "device_id", name="uq_deployment_device"),)


class DeploymentInstructionModel(Base):
    """Durable server-side outbox storing deployment instructions until confirmed delivery."""

    __tablename__ = "deployment_instructions"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deployment_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[str] = mapped_column(sa.String(64), sa.ForeignKey("fleet_devices.id", ondelete="CASCADE"), nullable=False)

    generation: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    instruction_type: Mapped[str] = mapped_column(sa.String(32), nullable=False)

    payload_json: Mapped[str] = mapped_column(sa.Text, nullable=False)
    payload_digest: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    status: Mapped[str] = mapped_column(sa.String(32), default="PENDING", index=True, nullable=False)
    attempt_count: Mapped[int] = mapped_column(sa.Integer, default=0, nullable=False)

    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    deployment: Mapped["DeploymentModel"] = relationship("DeploymentModel", back_populates="instructions")


class DeploymentApprovalModel(Base):
    """Operator approval audit log recording stage progression gates."""

    __tablename__ = "deployment_approvals"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deployment_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False)

    stage_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    action: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    approved_by: Mapped[str] = mapped_column(sa.String(128), nullable=False)

    previous_state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    new_state: Mapped[str] = mapped_column(sa.String(32), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    deployment: Mapped["DeploymentModel"] = relationship("DeploymentModel", back_populates="approvals")


class DeploymentEventModel(Base):
    """Structured audit log for deployment lifecycle events."""

    __tablename__ = "deployment_events"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    deployment_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False)
    device_id: Mapped[Optional[str]] = mapped_column(sa.String(64), nullable=True)

    event_type: Mapped[str] = mapped_column(sa.String(64), index=True, nullable=False)
    details: Mapped[str] = mapped_column(sa.Text, nullable=False)  # JSON, secrets redacted, bounded <= 64KB
    timestamp: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, index=True, nullable=False)

    deployment: Mapped["DeploymentModel"] = relationship("DeploymentModel", back_populates="events")


class DeploymentCounterModel(Base):
    """Transactional monotonic counters (e.g. global_generation)."""

    __tablename__ = "deployment_counters"

    counter_name: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    current_val: Mapped[int] = mapped_column(sa.BigInteger, default=0, nullable=False)
