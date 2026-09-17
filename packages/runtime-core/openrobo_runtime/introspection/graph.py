"""Runtime ROS Graph Inspector."""

from typing import Any, Dict, List

from openrobo_runtime.introspection.qos import QoSEvaluator
from openrobo_runtime.models import ConnectionDiagnostic, NodeHealth, QoSPolicyCompatibility


class RuntimeGraphInspector:
    """Introspects or parses active ROS 2 computational graph telemetry."""

    def __init__(self):
        self.evaluator = QoSEvaluator()

    def build_diagnostics_from_graph(
        self,
        nodes: List[Dict[str, Any]],
        topics: List[Dict[str, Any]],
    ) -> tuple[List[NodeHealth], List[ConnectionDiagnostic]]:
        node_healths = []
        for n in nodes:
            node_healths.append(
                NodeHealth(
                    name=n.get("name", "unknown"),
                    namespace=n.get("namespace", "/"),
                    is_present=n.get("is_present", True),
                    is_alive=n.get("is_alive", True),
                    pid=n.get("pid"),
                    publisher_topics=n.get("publisher_topics", []),
                    subscriber_topics=n.get("subscriber_topics", []),
                    services=n.get("services", []),
                    actions=n.get("actions", []),
                )
            )

        connection_diagnostics = []
        for t in topics:
            tname = t.get("topic") or t.get("name") or ""
            ttype = t.get("msg_type") or t.get("type") or "unknown"

            raw_pubs = t.get("publishers", [])
            raw_subs = t.get("subscribers", [])

            pubs = [p if isinstance(p, str) else p.get("node_name", p.get("name", str(p))) for p in raw_pubs]
            subs = [s if isinstance(s, str) else s.get("node_name", s.get("name", str(s))) for s in raw_subs]

            rate = t.get("rate_hz")

            pub_qos = t.get("publisher_qos", {})
            sub_qos = t.get("subscriber_qos", {})

            qos_status, qos_reason = self.evaluator.evaluate_compatibility(pub_qos, sub_qos)

            # Determine connection status
            if not pubs and subs:
                status = "ORPHANED_SUBSCRIBER"
            elif pubs and not subs:
                status = "ORPHANED_PUBLISHER"
            elif qos_status == QoSPolicyCompatibility.INCOMPATIBLE:
                status = "INCOMPATIBLE_QOS"
            else:
                status = "HEALTHY"

            connection_diagnostics.append(
                ConnectionDiagnostic(
                    topic=tname,
                    topic_type=ttype,
                    status=status,
                    publishers=pubs,
                    subscribers=subs,
                    rate_hz=rate,
                    qos_status=qos_status,
                    qos_reason=qos_reason if qos_status != QoSPolicyCompatibility.COMPATIBLE else None,
                )
            )

        return node_healths, connection_diagnostics
