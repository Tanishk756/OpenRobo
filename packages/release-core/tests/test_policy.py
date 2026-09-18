"""Tests for deployment safety policy evaluation, telemetry freshness, and zero implicit defaults."""

from datetime import datetime, timezone

from openrobo_release.models import (
    BatteryRequirement,
    DeploymentSafetyPolicy,
    EstopRequirement,
    MotionRequirement,
)
from openrobo_release.policy import evaluate_deployment_safety_policy


def test_policy_configuration_invalid_when_params_missing():
    # Enabled battery without threshold
    p_bad_bat = DeploymentSafetyPolicy(
        battery_requirement=BatteryRequirement(enabled=True, threshold_percent=None)
    )
    ok, msg = evaluate_deployment_safety_policy(p_bad_bat, {"battery_percent": 80.0})
    assert ok is False
    assert "POLICY_CONFIGURATION_INVALID" in msg

    # Enabled motion without required_state
    p_bad_mot = DeploymentSafetyPolicy(
        motion_requirement=MotionRequirement(enabled=True, required_state=None)
    )
    ok, msg = evaluate_deployment_safety_policy(p_bad_mot, {"motion_state": "STATIONARY"})
    assert ok is False
    assert "POLICY_CONFIGURATION_INVALID" in msg

    # Enabled estop without safe_states
    p_bad_estop = DeploymentSafetyPolicy(
        estop_requirement=EstopRequirement(enabled=True, safe_states=None)
    )
    ok, msg = evaluate_deployment_safety_policy(p_bad_estop, {"estop_state": "DISENGAGED"})
    assert ok is False
    assert "POLICY_CONFIGURATION_INVALID" in msg


def test_policy_telemetry_freshness():
    now_str = datetime.now(timezone.utc).isoformat()
    old_str = "2020-01-01T00:00:00Z"

    policy = DeploymentSafetyPolicy(
        battery_requirement=BatteryRequirement(enabled=True, threshold_percent=40.0),
        max_age_seconds=10.0,
    )

    # Fresh telemetry
    fresh_telemetry = {
        "battery_percent": {"value": 85.0, "observed_at": now_str}
    }
    ok, msg = evaluate_deployment_safety_policy(policy, fresh_telemetry)
    assert ok is True

    # Stale telemetry
    stale_telemetry = {
        "battery_percent": {"value": 85.0, "observed_at": old_str}
    }
    ok, msg = evaluate_deployment_safety_policy(policy, stale_telemetry)
    assert ok is False
    assert "STALE_TELEMETRY" in msg


def test_policy_missing_telemetry_blocks_deployment():
    policy = DeploymentSafetyPolicy(
        battery_requirement=BatteryRequirement(enabled=True, threshold_percent=30.0)
    )
    ok, msg = evaluate_deployment_safety_policy(policy, {})
    assert ok is False
    assert "UNKNOWN_TELEMETRY" in msg
