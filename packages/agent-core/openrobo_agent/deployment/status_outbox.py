# Durable, crash-consistent deployment status outbox for OpenRobo Agent.

import json
import logging
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from openrobo_release.deployment_protocol import DeploymentStatusReport, DeviceDeploymentState

logger = logging.getLogger("openrobo.agent.outbox")


class StatusOutboxError(Exception):
    pass


class StatusOutboxCorruptedError(StatusOutboxError):
    """Raised when persisted status outbox file exists but cannot be safely parsed."""

    pass


@dataclass
class OutboxReportItem:
    report_id: str
    instruction_id: str
    deployment_id: str
    device_id: str
    generation: int
    state: str
    current_slot: Optional[str]
    staged_slot: Optional[str]
    active_slot: Optional[str]
    error_code: Optional[str]
    error_message: Optional[str]
    timestamp: str
    delivery_status: str  # "PENDING", "SENT", "ACKNOWLEDGED", "REJECTED"
    created_at: str
    updated_at: str
    attempt_count: int = 0
    last_attempt_at: Optional[str] = None

    def to_status_report(self) -> DeploymentStatusReport:
        return DeploymentStatusReport(
            protocol_version="1.0.0",
            report_id=self.report_id,
            instruction_id=self.instruction_id,
            deployment_id=self.deployment_id,
            device_id=self.device_id,
            generation=self.generation,
            state=DeviceDeploymentState(self.state),
            current_slot=self.current_slot,
            staged_slot=self.staged_slot,
            active_slot=self.active_slot,
            error_code=self.error_code,
            error_message=self.error_message,
            timestamp=self.timestamp,
        )


class AgentStatusOutbox:
    """Durable outbox ensuring deployment status reports survive agent crashes and network disconnections."""

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path)
        self.items: Dict[str, OutboxReportItem] = self._load()

    def _load(self) -> Dict[str, OutboxReportItem]:
        if not self.file_path.exists():
            return {}
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if not isinstance(raw, dict):
                raise ValueError("Outbox content is not a valid JSON dictionary")
            items = {}
            for k, v in raw.items():
                items[k] = OutboxReportItem(**v)
            return items
        except Exception as e:
            logger.error("Failed to load status outbox from %s: %s", self.file_path, e)
            raise StatusOutboxCorruptedError(f"Corrupted deployment status outbox: {e}") from e

    def _save(self) -> None:
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = self.file_path.with_suffix(".tmp")
        raw = {k: asdict(v) for k, v in self.items.items()}
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        temp_file.replace(self.file_path)

    def enqueue(self, report: DeploymentStatusReport) -> OutboxReportItem:
        now_iso = datetime.now(timezone.utc).isoformat()
        item = OutboxReportItem(
            report_id=report.report_id,
            instruction_id=report.instruction_id,
            deployment_id=report.deployment_id,
            device_id=report.device_id,
            generation=report.generation,
            state=report.state.value,
            current_slot=report.current_slot,
            staged_slot=report.staged_slot,
            active_slot=report.active_slot,
            error_code=report.error_code,
            error_message=report.error_message,
            timestamp=report.timestamp,
            delivery_status="PENDING",
            created_at=now_iso,
            updated_at=now_iso,
            attempt_count=0,
            last_attempt_at=None,
        )
        self.items[item.report_id] = item
        self._save()
        return item

    def get_pending_or_unacknowledged(self) -> List[OutboxReportItem]:
        return [
            item
            for item in self.items.values()
            if item.delivery_status in ("PENDING", "SENT")
        ]

    def mark_sent(self, report_id: str) -> None:
        if report_id in self.items:
            item = self.items[report_id]
            item.delivery_status = "SENT"
            item.attempt_count += 1
            now_iso = datetime.now(timezone.utc).isoformat()
            item.last_attempt_at = now_iso
            item.updated_at = now_iso
            self._save()

    def mark_acknowledged(self, report_id: str) -> None:
        if report_id in self.items:
            item = self.items[report_id]
            item.delivery_status = "ACKNOWLEDGED"
            item.updated_at = datetime.now(timezone.utc).isoformat()
            self._save()

    def mark_rejected(self, report_id: str, reason: Optional[str] = None) -> None:
        if report_id in self.items:
            item = self.items[report_id]
            item.delivery_status = "REJECTED"
            if reason:
                item.error_message = reason
            item.updated_at = datetime.now(timezone.utc).isoformat()
            self._save()
