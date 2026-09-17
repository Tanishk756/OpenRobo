import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FleetDeviceModel(Base):
    __tablename__ = 'fleet_devices'

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False, index=True)
    domain: Mapped[str] = mapped_column(sa.String(100), nullable=False, default='general_robotics')
    robot_type: Mapped[str] = mapped_column(sa.String(100), nullable=False, default='custom')

    # Certificate & Security Identity
    certificate_fingerprint: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, nullable=False)
    certificate_serial: Mapped[Optional[str]] = mapped_column(sa.String(100), unique=True, nullable=True)
    certificate_pem: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)

    # Status & Revocation
    status: Mapped[str] = mapped_column(sa.String(50), nullable=False, default='ENROLLED')
    revoked_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    revocation_reason: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)

    # Capabilities & Telemetry
    capabilities_json: Mapped[List[str]] = mapped_column(sa.JSON, default=list, nullable=False)
    last_heartbeat_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    last_heartbeat_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(sa.JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    heartbeats: Mapped[List['AgentHeartbeatModel']] = relationship(
        'AgentHeartbeatModel', back_populates='device', cascade='all, delete-orphan'
    )
    telemetry_events: Mapped[List['AgentTelemetryEventModel']] = relationship(
        'AgentTelemetryEventModel', back_populates='device', cascade='all, delete-orphan'
    )


class AgentEnrollmentTokenModel(Base):
    __tablename__ = 'agent_enrollment_tokens'

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, nullable=False)
    device_name: Mapped[Optional[str]] = mapped_column(sa.String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    is_used: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    used_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    used_by_device_id: Mapped[Optional[str]] = mapped_column(sa.String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, nullable=False)


class AgentHeartbeatModel(Base):
    __tablename__ = 'agent_heartbeats'

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey('fleet_devices.id', ondelete='CASCADE'), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    payload_json: Mapped[Dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    device: Mapped['FleetDeviceModel'] = relationship('FleetDeviceModel', back_populates='heartbeats')


class AgentTelemetryEventModel(Base):
    __tablename__ = 'agent_telemetry_events'

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(sa.String(36), sa.ForeignKey('fleet_devices.id', ondelete='CASCADE'), index=True, nullable=False)
    message_id: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    payload_json: Mapped[Dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), default=utc_now, nullable=False)

    device: Mapped['FleetDeviceModel'] = relationship('FleetDeviceModel', back_populates='telemetry_events')
