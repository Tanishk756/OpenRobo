"""Connection & Stack Plan Comparator."""

from typing import Any, Dict, List, Optional

from openrobo_runtime.introspection.graph import RuntimeGraphInspector
from openrobo_runtime.models import (
    OverallHealthStatus,
    QoSDiagnostic,
    QoSPolicyCompatibility,
    RuntimeVerificationResult,
)


class ConnectionComparator:
    """Compares planned M4/M5 stack intent against observed running ROS system."""

    def __init__(self):
        self.inspector = RuntimeGraphInspector()

    def compare(
        self,
        planned_manifest: Dict[str, Any],
        observed_nodes: List[Dict[str, Any]],
        observed_topics: List[Dict[str, Any]],
        observed_tfs: Optional[List[Dict[str, Any]]] = None,
    ) -> RuntimeVerificationResult:
        stack_id = planned_manifest.get("id", "openrobo_stack")
        planned_resources = planned_manifest.get("resources", [])

        # Extract planned components / expected node tokens
        expected_tokens = set()
        for r in planned_resources:
            rid = r if isinstance(r, str) else r.get("id", "")
            token = rid.split("/")[-1].replace("-", "_").lower()
            if token:
                expected_tokens.add(token)

        node_healths, connection_diags = self.inspector.build_diagnostics_from_graph(
            observed_nodes, observed_topics
        )

        observed_node_names = {n.name.lower().strip("/").replace("_node", "") for n in node_healths}

        missing_nodes = []
        for exp in sorted(expected_tokens):
            if not any(exp in obs or obs in exp for obs in observed_node_names):
                missing_nodes.append(exp)

        unexpected_nodes = []
        for obs in sorted(observed_node_names):
            if not any(exp in obs or obs in exp for exp in expected_tokens):
                unexpected_nodes.append(obs)

        # Extract QoS findings
        qos_findings = []
        for c in connection_diags:
            if c.qos_status == QoSPolicyCompatibility.INCOMPATIBLE:
                for pub in c.publishers:
                    for sub in c.subscribers:
                        qos_findings.append(
                            QoSDiagnostic(
                                topic=c.topic,
                                publisher_node=pub,
                                subscriber_node=sub,
                                compatibility=c.qos_status,
                                reason=c.qos_reason,
                            )
                        )

        # Calculate overall status
        if not node_healths and not connection_diags:
            overall = OverallHealthStatus.UNKNOWN
            summary = "No active runtime ROS nodes or topics observed."
        elif missing_nodes or qos_findings:
            overall = OverallHealthStatus.DEGRADED
            issues = []
            if missing_nodes:
                issues.append(f"{len(missing_nodes)} expected nodes missing ({', '.join(missing_nodes)})")
            if qos_findings:
                issues.append(f"{len(qos_findings)} QoS incompatibilities detected")
            summary = "Runtime degraded: " + "; ".join(issues)
        else:
            overall = OverallHealthStatus.HEALTHY
            summary = f"Runtime healthy: {len(node_healths)} active nodes matching planned stack intent."

        return RuntimeVerificationResult(
            stack_id=stack_id,
            runtime_id=f"rt_{stack_id}",
            overall_status=overall,
            nodes=node_healths,
            connections=connection_diags,
            qos_findings=qos_findings,
            missing_nodes=missing_nodes,
            unexpected_nodes=unexpected_nodes,
            summary=summary,
        )
