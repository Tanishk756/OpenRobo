"""OpenRobo Delta Telemetry Collector & Sanitizer."""

import time
from typing import Any, Dict, List, Optional, Set

from openrobo_runtime.ros.collector import LiveRosGraphCollector

from openrobo_agent.identity import DeviceIdentityManager
from openrobo_agent.models import TelemetryEventType, TelemetryMessage
from openrobo_agent.security import sanitize_telemetry_payload


class TelemetryCollector:
    """Collects delta computational graph updates and sanitized edge events."""

    def __init__(self, identity_manager: DeviceIdentityManager, graph_collector: Optional[LiveRosGraphCollector] = None):
        self.identity_manager = identity_manager
        self.graph_collector = graph_collector or LiveRosGraphCollector()
        self._known_nodes: Set[str] = set()
        self._known_topics: Set[str] = set()
        self._last_full_snapshot_time = 0.0

    def collect_delta_events(self, full_snapshot_interval_sec: float = 60.0) -> List[TelemetryMessage]:
        """Collect delta events (added/removed nodes/topics) or periodic full snapshots."""
        events: List[TelemetryMessage] = []
        now = time.time()

        graph = self.graph_collector.collect()
        current_nodes = {n.get("name") for n in graph.get("nodes", []) if n.get("name")}
        current_topics = {t.get("name") for t in graph.get("topics", []) if t.get("name")}

        # Check for added / removed nodes
        added_nodes = current_nodes - self._known_nodes
        removed_nodes = self._known_nodes - current_nodes

        for n in added_nodes:
            events.append(
                self.create_event(
                    TelemetryEventType.NODE_STATE_CHANGE,
                    {"action": "NODE_ADDED", "node_name": n},
                )
            )

        for n in removed_nodes:
            events.append(
                self.create_event(
                    TelemetryEventType.NODE_STATE_CHANGE,
                    {"action": "NODE_REMOVED", "node_name": n},
                )
            )

        # Check for added / removed topics
        added_topics = current_topics - self._known_topics
        removed_topics = self._known_topics - current_topics

        for t in added_topics:
            events.append(
                self.create_event(
                    TelemetryEventType.TOPIC_STATE_CHANGE,
                    {"action": "TOPIC_ADDED", "topic_name": t},
                )
            )

        for t in removed_topics:
            events.append(
                self.create_event(
                    TelemetryEventType.TOPIC_STATE_CHANGE,
                    {"action": "TOPIC_REMOVED", "topic_name": t},
                )
            )

        self._known_nodes = current_nodes
        self._known_topics = current_topics

        # Periodic full summary
        if now - self._last_full_snapshot_time > full_snapshot_interval_sec:
            events.append(
                self.create_event(
                    TelemetryEventType.DIAGNOSTIC_EVENT,
                    {
                        "node_count": len(current_nodes),
                        "topic_count": len(current_topics),
                        "collector_status": graph.get("status"),
                    },
                )
            )
            self._last_full_snapshot_time = now

        return events

    def create_event(self, event_type: TelemetryEventType, payload: Dict[str, Any]) -> TelemetryMessage:
        """Create a sanitized TelemetryMessage."""
        sanitized = sanitize_telemetry_payload(payload)
        return TelemetryMessage(
            event_type=event_type,
            device_id=self.identity_manager.device_id,
            payload=sanitized,
        )
