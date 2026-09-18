# Milestone 7.2.3 Implementation Plan (PLAN ONLY — DO NOT IMPLEMENT)

> [!NOTE]
> This document is a planning specification for Milestone 7.2.3. Implementation will begin only in the designated subsequent milestone pass after M7.2.2 is merged.

---

## 1. Goal Description

Milestone 7.2.3 builds upon M7.2.2's operator-gated canary deployment engine by adding:
1. **Runtime Telemetry Health Gates**: Automated policy evaluation over ROS topic frequency, hardware error rates, and connection health during canary dwell time.
2. **Autonomous Rollback Engine**: Deterministic trigger of cryptographic rollback when a health policy breach is detected.
3. **Fleet Studio Rollout UI**: Real-time deployment dashboard in `apps/web` with live stage progress bar, canary health metrics, and interactive operator approval buttons.

---

## 2. Scope & Boundaries

- **M7.2.3 Scope**:
  - Telemetry rule engine (e.g. max crash rate, min heartbeat rate, QoS thresholds).
  - Configurable dwell timers per stage.
  - Automatic rollback instruction issuance on metric anomaly.
  - Next.js / React interactive rollout management in Fleet Studio.
- **Out of Scope for M7.2.3**:
  - Peer-to-peer mesh artifact distribution.
  - Cloud provider native fleet integrations (AWS RoboMaker / Google Cloud Robotics).

---

## 3. Architecture & Interfaces

### 3.1 Health Gate Rules Model
```python
class HealthPolicyRule(BaseModel):
    metric_name: str
    comparator: Literal["GT", "LT", "EQ", "GTE", "LTE"]
    threshold: float
    window_seconds: int
    consecutive_breaches_to_trip: int = 3
```

### 3.2 Rollback State Machine
- When a health gate trips during canary bake period:
  1. Halt pending stage approvals.
  2. Issue `ACTIVATE_RELEASE` targeting previous verified active slot.
  3. Transition deployment state to `ROLLING_BACK` -> `ROLLED_BACK`.

---

## 4. Verification Plan (Future)
- Automated metric injection simulating sensor failure during canary stage 0.
- Assertion that rollback completes within <500ms without operator intervention.
- Vitest UI testing of rollout visualization and manual override buttons.
