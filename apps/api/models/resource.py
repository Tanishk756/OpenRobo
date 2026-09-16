from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from apps.api.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ResourceModel(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    spdx_license_id: Mapped[str] = mapped_column(String(100), nullable=False, default="NOASSERTION", index=True)
    repo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    evidence_level: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    robotics_domains: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    capabilities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, default=list)
    platforms: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    versions: Mapped[List["ResourceVersionModel"]] = relationship(back_populates="resource", cascade="all, delete-orphan")


class ResourceVersionModel(Base):
    __tablename__ = "resource_versions"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(255), ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    version_string: Mapped[str] = mapped_column(String(100), nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    resource: Mapped["ResourceModel"] = relationship(back_populates="versions")


class DomainModel(Base):
    __tablename__ = "domains"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[Optional[str]] = mapped_column(String(100), ForeignKey("domains.id"), nullable=True)


class CapabilityModel(Base):
    __tablename__ = "capabilities"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class StackManifestModel(Base):
    __tablename__ = "stack_manifests"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    manifest_yaml: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
