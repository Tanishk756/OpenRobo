"""Platform-specific deployment safety policy evaluation with telemetry freshness checks and zero implicit defaults."""

from datetime import datetime, timezone
from typing import Any

from openrobo_release.models import DeploymentSafetyPolicy


def _parse_iso_datetime(dt_str: str) -> datetime | None:
    try:
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except Exception:
        return None


def is_telemetry_fresh(observed_at_str: str | None, max_age_seconds: float) -> tuple[bool, str]:
    """Checks if telemetry observation timestamp is fresh within max_age_seconds."""
    if not observed_at_str:
        return False, "Telemetry missing observed_at timestamp"

    obs_dt = _parse_iso_datetime(observed_at_str)
    if obs_dt is None:
        return False, f"Unparseable observed_at timestamp: {observed_at_str}"

    now = datetime.now(timezone.utc)
    age = (now - obs_dt).total_seconds()
    if age < 0:
        # Clock skew tolerance or future timestamp
        return True, "Fresh"
    if age > max_age_seconds:
        return False, f"Telemetry is stale ({age:.1f}s > {max_age_seconds:.1f}s)"

    return True, "Fresh"


def evaluate_deployment_safety_policy(
    policy: DeploymentSafetyPolicy,
    telemetry: dict[str, Any] | None,
) -> tuple[bool, str]:
    """Evaluates platform-specific safety requirements against device telemetry with zero implicit robot defaults."""
    if telemetry is None:
        telemetry = {}

    max_age = policy.max_age_seconds

    # 1. Battery Requirement
    if policy.battery_requirement.enabled:
        req = policy.battery_requirement
        if req.threshold_percent is None:
            return False, "POLICY_CONFIGURATION_INVALID: battery_requirement is enabled but threshold_percent is not configured"

        source_key = req.telemetry_source or "battery_percent"
        battery_data = telemetry.get(source_key)

        if battery_data is None:
            return False, f"UNKNOWN_TELEMETRY: Required battery telemetry '{source_key}' is missing"

        # Check freshness if telemetry is dict with observed_at
        if isinstance(battery_data, dict):
            val = battery_data.get("value")
            obs = battery_data.get("observed_at")
            fresh, reason = is_telemetry_fresh(obs, max_age)
            if not fresh:
                return False, f"STALE_TELEMETRY: Battery telemetry stale: {reason}"
        else:
            val = battery_data
            # Check global telemetry observed_at
            if "observed_at" in telemetry:
                fresh, reason = is_telemetry_fresh(telemetry["observed_at"], max_age)
                if not fresh:
                    return False, f"STALE_TELEMETRY: Telemetry stale: {reason}"

        if val is None:
            return False, f"UNKNOWN_TELEMETRY: Battery value is null for key '{source_key}'"

        try:
            val_float = float(val)
        except (ValueError, TypeError):
            return False, f"UNKNOWN_TELEMETRY: Invalid numeric value for battery: {val}"

        if val_float < req.threshold_percent:
            return False, f"POLICY_FAILED: Battery level {val_float}% is below required threshold {req.threshold_percent}%"

    # 2. Motion Requirement
    if policy.motion_requirement.enabled:
        req = policy.motion_requirement
        if not req.required_state:
            return False, "POLICY_CONFIGURATION_INVALID: motion_requirement is enabled but required_state is not configured"

        source_key = req.telemetry_source or "motion_state"
        motion_data = telemetry.get(source_key)

        if motion_data is None:
            return False, f"UNKNOWN_TELEMETRY: Required motion telemetry '{source_key}' is missing"

        if isinstance(motion_data, dict):
            val = motion_data.get("value")
            obs = motion_data.get("observed_at")
            fresh, reason = is_telemetry_fresh(obs, max_age)
            if not fresh:
                return False, f"STALE_TELEMETRY: Motion telemetry stale: {reason}"
        else:
            val = motion_data
            if "observed_at" in telemetry:
                fresh, reason = is_telemetry_fresh(telemetry["observed_at"], max_age)
                if not fresh:
                    return False, f"STALE_TELEMETRY: Telemetry stale: {reason}"

        if val is None:
            return False, f"UNKNOWN_TELEMETRY: Motion state is null for key '{source_key}'"

        if str(val).upper() != req.required_state.upper():
            return False, f"POLICY_FAILED: Current motion state '{val}' does not match required state '{req.required_state}'"

    # 3. Emergency Stop Requirement
    if policy.estop_requirement.enabled:
        req = policy.estop_requirement
        if not req.safe_states:
            return False, "POLICY_CONFIGURATION_INVALID: estop_requirement is enabled but safe_states list is empty or not configured"

        source_key = req.state_source or "estop_state"
        estop_data = telemetry.get(source_key)

        if estop_data is None:
            return False, f"UNKNOWN_TELEMETRY: Required E-stop telemetry '{source_key}' is missing"

        if isinstance(estop_data, dict):
            val = estop_data.get("value")
            obs = estop_data.get("observed_at")
            fresh, reason = is_telemetry_fresh(obs, max_age)
            if not fresh:
                return False, f"STALE_TELEMETRY: E-stop telemetry stale: {reason}"
        else:
            val = estop_data
            if "observed_at" in telemetry:
                fresh, reason = is_telemetry_fresh(telemetry["observed_at"], max_age)
                if not fresh:
                    return False, f"STALE_TELEMETRY: Telemetry stale: {reason}"

        if val is None:
            return False, f"UNKNOWN_TELEMETRY: E-stop state is null for key '{source_key}'"

        safe_states_upper = [s.upper() for s in req.safe_states]
        if str(val).upper() not in safe_states_upper:
            return False, f"POLICY_FAILED: E-stop state '{val}' is not in configured safe states {req.safe_states}"

    return True, "Safety policy passed"
