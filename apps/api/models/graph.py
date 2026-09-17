from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from apps.api.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class GraphNodeModel(Base):
    __tablename__ = "graph_nodes"

    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    node_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    properties_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class GraphEdgeModel(Base):
    __tablename__ = "graph_edges"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject_id: Mapped[str] = mapped_column(String(255), ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    predicate: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    object_id: Mapped[str] = mapped_column(String(255), ForeignKey("graph_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    properties_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    __table_args__ = (
        Index("ix_graph_edges_subject_predicate", "subject_id", "predicate"),
        Index("ix_graph_edges_object_predicate", "object_id", "predicate"),
    )
