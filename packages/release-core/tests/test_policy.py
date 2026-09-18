"""Unit and security tests for deployment safety policies, telemetry freshness, and future clock skew."""

from datetime import datetime, timedelta, timezone

from openrobo_release.models import (
    BatteryRequirement,
    DeploymentSafetyPolicy,
    EstopRequirement,
    MotionRequirement,
)
from openrobo_release.policy import evaluate_deployment_safety_policy


def test_policy_all_safety_checks_pass():
    policy = DeploymentSafetyPolicy(
        battery_requirement=BatteryRequirement(enabled=True, threshold_percent=30.0),
        motion_requirement=MotionRequirement(enabled=True, required_state="IDLE"),
        estop_requirement=EstopRequirement(enabled=True, safe_states=["RELEASED", "DISENGAGED"]),
    )

    now_str = datetime.now(timezone.utc).isoformat()
    telemetry = {
        "battery_percent": {"value": 85.0, "observed_at": now_str},
        "motion_state": {"value": "IDLE", "observed_at": now_str},
        "estop_state": {"value": "RELEASED", "observed_at": now_str},
    }

    ok, msg = evaluate_deployment_safety_policy(policy, telemetry)
    assert ok is True
    assert "passed" in msg


def test_policy_telemetry_staleness():
    policy = DeploymentSafetyPolicy(
        battery_requirement=BatteryRequirement(enabled=True, threshold_percent=30.0),
        max_age_seconds=10.0,
    )

    now = datetime.now(timezone.utc)
    fresh_str = now.isoformat()
    old_str = (now - timedelta(seconds=20)).isoformat()

    # Fresh telemetry
    fresh_telemetry = {
        "battery_percent": {"value": 85.0, "observed_at": fresh_str}
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


def test_scalar_telemetry_without_timestamp_rejected():
    """Bare scalar telemetry without timestamp/envelope must fail closed as STALE/UNKNOWN."""
    policy = DeploymentSafetyPolicy(
        battery_requirement=BatteryRequirement(enabled=True, threshold_percent=30.0)
    )
    # Scalar without timestamp
    scalar_telemetry = {"battery_percent": 80.0}
    ok, msg = evaluate_deployment_safety_policy(policy, scalar_telemetry)
    assert ok is False
    assert "STALE_TELEMETRY" in msg


def test_future_telemetry_skew_bounded():
    """Telemetry too far in the future (> max_future_skew_seconds) must be rejected."""
    policy = DeploymentSafetyPolicy(
        battery_requirement=BatteryRequirement(enabled=True, threshold_percent=30.0),
        max_future_skew_seconds=5.0,
    )
    now = datetime.now(timezone.utc)

    # 1 minute in the future
    future_str = (now + timedelta(seconds=60)).isoformat()
    future_telemetry = {
        "battery_percent": {"value": 85.0, "observed_at": future_str}
    }
    ok, msg = evaluate_deployment_safety_policy(policy, future_telemetry)
    assert ok is False
    assert "skewed into the future" in msg or "STALE_TELEMETRY" in msg

    # 2 seconds in the future (within 5s tolerance)
    tolerable_future_str = (now + timedelta(seconds=2)).isoformat()
    tolerable_telemetry = {
        "battery_percent": {"value": 85.0, "observed_at": tolerable_future_str}
    }
    ok_tol, msg_tol = evaluate_deployment_safety_policy(policy, tolerable_telemetry)
    assert ok_tol is True
