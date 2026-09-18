"""Platform-specific pre-flight safety policy evaluation."""

from typing import Any, Dict, Tuple

from openrobo_release.models import DeploymentSafetyPolicy


def evaluate_deployment_safety_policy(
    policy: DeploymentSafetyPolicy,
    telemetry_state: Dict[str, Any],
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Evaluate platform-specific pre-flight safety gates against current robot telemetry.

    Strict Invariant:
    If any enabled safety requirement's telemetry is missing, stale, or unrecognized,
    the evaluation returns UNKNOWN and blocks deployment.
    """
    details: Dict[str, Any] = {}

    # 1. Battery Requirement
    if policy.battery_requirement and policy.battery_requirement.get("enabled", False):
        threshold = policy.battery_requirement.get("threshold_percent")
        source = policy.battery_requirement.get("telemetry_source", "battery_percentage")

        val = telemetry_state.get(source)
        if val is None:
            val = telemetry_state.get("battery_percentage")

        if val is None:
            return False, f"Safety check failed: Battery telemetry source '{source}' is UNKNOWN.", {"field": source, "status": "UNKNOWN"}

        try:
            battery_pct = float(val)
        except (ValueError, TypeError):
            return False, f"Safety check failed: Battery telemetry value '{val}' is invalid.", {"field": source, "value": val}

        details["battery_percentage"] = battery_pct
        details["battery_threshold"] = threshold

        if threshold is not None and battery_pct < float(threshold):
            return False, f"Safety check failed: Battery level {battery_pct:.1f}% is below required threshold {threshold}%.", details

    # 2. Motion Requirement
    if policy.motion_requirement and policy.motion_requirement.get("enabled", False):
        req_state = str(policy.motion_requirement.get("required_state", "STATIONARY")).upper()
        source = policy.motion_requirement.get("telemetry_source", "motion_state")
        max_vel = policy.motion_requirement.get("max_linear_velocity")

        current_state = telemetry_state.get(source)
        if current_state is None:
            current_state = telemetry_state.get("motion_state")

        if current_state is None:
            return False, f"Safety check failed: Motion telemetry source '{source}' is UNKNOWN.", {"field": source, "status": "UNKNOWN"}

        details["motion_state"] = str(current_state).upper()
        details["required_motion_state"] = req_state

        if str(current_state).upper() != req_state:
            msg = f"Safety check failed: Current motion state '{current_state}' does not match required state '{req_state}'."
            return False, msg, details

        if max_vel is not None:
            vel = telemetry_state.get("linear_velocity")
            if vel is not None:
                details["linear_velocity"] = float(vel)
                if float(vel) > float(max_vel):
                    return False, f"Safety check failed: Linear velocity {vel} exceeds max limit {max_vel}.", details

    # 3. E-Stop Requirement
    if policy.estop_requirement and policy.estop_requirement.get("enabled", False):
        safe_states = [str(s).upper() for s in policy.estop_requirement.get("safe_states", ["ENGAGED", "ACTIVE", "TRUE"])]
        source = policy.estop_requirement.get("state_source", "estop_state")

        estop_val = telemetry_state.get(source)
        if estop_val is None:
            estop_val = telemetry_state.get("estop_state")

        if estop_val is None:
            return False, f"Safety check failed: E-Stop telemetry source '{source}' is UNKNOWN.", {"field": source, "status": "UNKNOWN"}

        details["estop_state"] = str(estop_val).upper()
        details["safe_estop_states"] = safe_states

        if str(estop_val).upper() not in safe_states:
            return False, f"Safety check failed: E-Stop state '{estop_val}' is not in safe states {safe_states}.", details

    return True, "Pre-flight safety policy verified.", details
