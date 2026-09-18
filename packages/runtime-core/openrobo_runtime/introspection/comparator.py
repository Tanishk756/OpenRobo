"""Stack Runtime Contract & Observed Graph Comparator (Milestone 6.1)."""

from typing import Any, Dict, List, Optional

from openrobo_runtime.introspection.graph import RuntimeGraphInspector
from openrobo_runtime.models import (
    ConnectionDiagnostic,
    OverallHealthStatus,
    QoSDiagnostic,
    QoSPolicyCompatibility,
    ReadinessState,
    RuntimeContract,
    RuntimeVerificationResult,
    TFDiagnostic,
)
from openrobo_runtime.ros.tf_monitor import LiveTFMonitor


class ConnectionComparator:
    """Compares planned stack runtime contracts against observed live ROS system."""

    def __init__(self):
        self.inspector = RuntimeGraphInspector()
        self.tf_monitor = LiveTFMonitor()

    def compare(
        self,
        planned_manifest: Dict[str, Any],
        observed_nodes: List[Dict[str, Any]],
        observed_topics: List[Dict[str, Any]],
        observed_tfs: Optional[List[Dict[str, Any]]] = None,
        runtime_contract: Optional[RuntimeContract] = None,
    ) -> RuntimeVerificationResult:
        stack_id = planned_manifest.get("id", "openrobo_stack")

        # 1. Parse or resolve explicit runtime contract
        contract = runtime_contract
        if not contract:
            raw_contract = planned_manifest.get("runtime_contract") or planned_manifest.get("runtime")
            if isinstance(raw_contract, dict):
                contract = RuntimeContract(**raw_contract)
            elif isinstance(raw_contract, RuntimeContract):
                contract = raw_contract

        # 2. Build graph diagnostics
        node_healths, connection_diags = self.inspector.build_diagnostics_from_graph(
            observed_nodes, observed_topics
        )

        observed_node_map = {n.name.lstrip("/").lower(): n for n in node_healths}
        observed_topic_map = {c.topic: c for c in connection_diags}

        missing_nodes: List[str] = []
        unexpected_nodes: List[str] = []
        type_mismatches: List[str] = []

        if contract and (contract.expected_nodes or contract.expected_topics or contract.expected_transforms):
            contract_evaluated = True

            # Evaluate expected nodes strictly
            for exp_node in contract.expected_nodes:
                norm_exp = exp_node.lstrip("/").lower()
                if norm_exp not in observed_node_map:
                    missing_nodes.append(exp_node)

            # Evaluate expected topics & type mismatches
            for exp_topic in contract.expected_topics:
                obs_topic = observed_topic_map.get(exp_topic.name)
                if not obs_topic:
                    if exp_topic.required:
                        connection_diags.append(
                            ConnectionDiagnostic(
                                topic=exp_topic.name,
                                topic_type=exp_topic.msg_type,
                                status="MISSING_REQUIRED_TOPIC",
                                publishers=[],
                                subscribers=[],
                                qos_status=QoSPolicyCompatibility.UNKNOWN,
                                type_mismatch_detail=f"Topic '{exp_topic.name}' is declared in contract but not active in ROS graph.",
                            )
                        )
                else:
                    # Check type match
                    if obs_topic.topic_type != "unknown" and exp_topic.msg_type != "unknown":
                        if obs_topic.topic_type != exp_topic.msg_type:
                            obs_topic.status = "TYPE_MISMATCH"
                            obs_topic.type_mismatch_detail = (
                                f"Expected message type '{exp_topic.msg_type}', "
                                f"observed '{obs_topic.topic_type}' on topic '{exp_topic.name}'."
                            )
                            type_mismatches.append(exp_topic.name)
        else:
            contract_evaluated = False
            # Without an explicit contract, do not fabricate missing node failures from resource names

        # Evaluate TF findings if provided
        tf_findings: List[TFDiagnostic] = []
        expected_tf_pairs = (
            [(t.parent, t.child) for t in contract.expected_transforms] if contract else None
        )
        if observed_tfs or expected_tf_pairs:
            tf_findings = self.tf_monitor.inspect_transforms(
                known_tfs=observed_tfs,
                expected_pairs=expected_tf_pairs,
            )

        # Extract QoS findings
        qos_findings: List[QoSDiagnostic] = []
        for c in connection_diags:
            if c.qos_status == QoSPolicyCompatibility.INCOMPATIBLE:
                for pub in (c.publishers or ["unknown_pub"]):
                    for sub in (c.subscribers or ["unknown_sub"]):
                        qos_findings.append(
                            QoSDiagnostic(
                                topic=c.topic,
                                publisher_node=pub,
                                subscriber_node=sub,
                                compatibility=c.qos_status,
                                reason=c.qos_reason,
                            )
                        )

        # Calculate overall status and readiness
        tf_errors = [tf for tf in tf_findings if not tf.is_connected]

        if not node_healths and not connection_diags:
            overall = OverallHealthStatus.UNKNOWN
            readiness = ReadinessState.RUNTIME_NOT_EXECUTED
            summary = "No active runtime ROS nodes or topics observed."
        elif missing_nodes or type_mismatches or qos_findings or tf_errors:
            overall = OverallHealthStatus.DEGRADED
            readiness = ReadinessState.RUNTIME_FAILED
            issues = []
            if missing_nodes:
                issues.append(f"{len(missing_nodes)} expected nodes missing ({', '.join(missing_nodes)})")
            if type_mismatches:
                issues.append(f"{len(type_mismatches)} topic type mismatches ({', '.join(type_mismatches)})")
            if qos_findings:
                issues.append(f"{len(qos_findings)} QoS incompatibilities detected")
            if tf_errors:
                issues.append(f"{len(tf_errors)} transform frames disconnected")
            summary = "Runtime degraded: " + "; ".join(issues)
        else:
            overall = OverallHealthStatus.HEALTHY
            readiness = (
                ReadinessState.RUNTIME_VERIFIED
                if contract_evaluated
                else ReadinessState.STATICALLY_VALIDATED
            )
            summary = (
                f"Runtime verified: {len(node_healths)} nodes fulfilling runtime contract."
                if contract_evaluated
                else f"Runtime healthy: {len(node_healths)} active nodes observed (no contract specified)."
            )

        return RuntimeVerificationResult(
            stack_id=stack_id,
            runtime_id=f"rt_{stack_id}",
            overall_status=overall,
            readiness_state=readiness,
            nodes=node_healths,
            connections=connection_diags,
            qos_findings=qos_findings,
            tf_findings=tf_findings,
            missing_nodes=missing_nodes,
            unexpected_nodes=unexpected_nodes,
            contract_evaluated=contract_evaluated,
            summary=summary,
        )
