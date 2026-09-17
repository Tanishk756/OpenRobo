"""Unit tests for ROS 2 QoS Compatibility Evaluator."""

from openrobo_runtime import QoSEvaluator, QoSPolicyCompatibility


def test_qos_compatible_reliable():
    pub_qos = {"reliability": "RELIABLE", "durability": "VOLATILE"}
    sub_qos = {"reliability": "RELIABLE", "durability": "VOLATILE"}
    status, _ = QoSEvaluator.evaluate_compatibility(pub_qos, sub_qos)
    assert status == QoSPolicyCompatibility.COMPATIBLE


def test_qos_incompatible_reliability():
    # Publisher BEST_EFFORT with Subscriber RELIABLE -> INCOMPATIBLE
    pub_qos = {"reliability": "BEST_EFFORT", "durability": "VOLATILE"}
    sub_qos = {"reliability": "RELIABLE", "durability": "VOLATILE"}
    status, reason = QoSEvaluator.evaluate_compatibility(pub_qos, sub_qos)
    assert status == QoSPolicyCompatibility.INCOMPATIBLE
    assert "Incompatible Reliability" in reason


def test_qos_incompatible_durability():
    # Publisher VOLATILE with Subscriber TRANSIENT_LOCAL -> INCOMPATIBLE
    pub_qos = {"reliability": "RELIABLE", "durability": "VOLATILE"}
    sub_qos = {"reliability": "RELIABLE", "durability": "TRANSIENT_LOCAL"}
    status, reason = QoSEvaluator.evaluate_compatibility(pub_qos, sub_qos)
    assert status == QoSPolicyCompatibility.INCOMPATIBLE
    assert "Incompatible Durability" in reason
