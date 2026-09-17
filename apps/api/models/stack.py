from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class StackModel(Base):
    __tablename__ = "stacks"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1.0.0")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    robot_domain: Mapped[str] = mapped_column(String(100), nullable=False, default="general_robotics")
    robot_type: Mapped[str] = mapped_column(String(100), nullable=False, default="custom")
    target_os: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_arch: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    target_ros_distro: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    components_json: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("ix_stacks_updated_at", "updated_at"),
    )
