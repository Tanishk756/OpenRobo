"""Unit tests for DeploymentSafetyPolicy evaluation."""

from openrobo_release import DeploymentSafetyPolicy, evaluate_deployment_safety_policy


def test_safety_policy_battery_pass_and_fail():
    policy = DeploymentSafetyPolicy(
        battery_requirement={"enabled": True, "threshold_percent": 30.0, "telemetry_source": "battery_percentage"},
    )

    # 1. Battery adequate -> PASS
    ok, msg, _ = evaluate_deployment_safety_policy(policy, {"battery_percentage": 45.0})
    assert ok is True

    # 2. Battery low -> FAIL
    ok, msg, _ = evaluate_deployment_safety_policy(policy, {"battery_percentage": 15.0})
    assert ok is False
    assert "below required threshold" in msg

    # 3. Missing telemetry -> UNKNOWN -> BLOCKED
    ok, msg, _ = evaluate_deployment_safety_policy(policy, {})
    assert ok is False
    assert "UNKNOWN" in msg


def test_safety_policy_motion_and_estop():
    policy = DeploymentSafetyPolicy(
        motion_requirement={"enabled": True, "required_state": "STATIONARY"},
        estop_requirement={"enabled": True, "safe_states": ["ENGAGED", "ACTIVE"]},
    )

    # All conditions met
    ok, msg, _ = evaluate_deployment_safety_policy(
        policy,
        {"motion_state": "STATIONARY", "estop_state": "ENGAGED"}
    )
    assert ok is True

    # Moving robot -> FAIL
    ok, msg, _ = evaluate_deployment_safety_policy(
        policy,
        {"motion_state": "MOVING", "estop_state": "ENGAGED"}
    )
    assert ok is False
    assert "does not match required state" in msg

    # Missing e-stop -> UNKNOWN -> FAIL
    ok, msg, _ = evaluate_deployment_safety_policy(
        policy,
        {"motion_state": "STATIONARY"}
    )
    assert ok is False
    assert "UNKNOWN" in msg
