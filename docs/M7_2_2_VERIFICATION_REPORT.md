# M7.2.2.1 Verification & Acceptance Report

**Milestone**: M7.2.2.1 — Remote OTA Service Wiring, Durable Delivery, Instruction Binding & Truthful End-to-End Acceptance Closure
**Date**: September 18, 2026
**Status**: VERIFIED & COMPLETE

---

## 1. Test Suite Summary

- **Total Python Tests**: 228 passed (0 failed, 6 pydantic deprecation warnings)
- **Total Frontend Tests**: 19 passed (0 failed)
- **Schema Validation**: All schemas and instances valid (`python scripts/validate_schemas.py`)
- **Code Style & Lint**: Clean (`ruff check .`, `pnpm run lint:web`)
- **Web Production Build**: Clean (`pnpm run build`)

---

## 2. Remote OTA End-to-End Acceptance Results

All mandatory remote OTA acceptance tests executed against real `AgentDaemon` and FastAPI service instances:

1. **SINGLE-DEVICE AUTHENTICATED REMOTE OTA ACCEPTANCE VERIFIED**
   - Verified end-to-end flow using real `AgentDaemon`, authoritative local `TrustedArtifactSourceRegistry`, HTTPS artifact distribution, bounded streaming (1 MiB manifest, 8 KiB signature), canonical manifest identity verification `SHA256(canonical_manifest_bytes(manifest))`, safe quarantine extraction, verified A/B staging, status report emitting, operator activation approval (`POST /api/v1/deployments/{id}/approve`), and atomic symlink pointer activation.

2. **3-AGENT AUTHENTICATED OPERATOR-GATED CANARY ACCEPTANCE VERIFIED**
   - Verified 3 concurrent `AgentDaemon` instances in a 2-stage canary rollout (Stage 0: 33% = 1 device, Stage 1: 100% = 2 devices).
   - Confirmed Stage 0 robot stages; 0 robots activate prior to operator approval.
   - Confirmed only Stage 0 robot activates following approval. Other 2 robots receive no staging instruction until stage 1 approval.
   - Confirmed full cohort progression and truthful terminal state reporting (`COMPLETED`).

3. **DURABLE OUTBOX RECONNECT/REDELIVERY VERIFIED**
   - Verified persistent instruction queue delivery with exponential retry backoff (`attempt_count`, `last_attempt_at`, `next_attempt_at`).
   - Unacknowledged and reconnecting devices cleanly receive pending durable instructions without retransmission loops.

4. **AGENT SERVICE RESTART RECOVERY VERIFIED**
   - Verified `AgentDaemon` and `DeploymentWorker` crash consistency: mid-job restarts properly inspect `deployment_jobs.json`, `generation_state.json`, A/B slot state, and intent journals, resuming safely without corrupting slots or replaying stale instructions.

5. **CONTROL-PLANE RESTART RECOVERY VERIFIED**
   - Verified control plane application/service recreation using persisted SQLite/PostgreSQL storage.
   - Deployments, target snapshots with compatibility evidence, approval versions, and pending outbox instructions survive server restarts.

6. **100-DEVICE ORCHESTRATION SIMULATED**
   - Simulated 100 enrolled fleet devices across a 3-stage cumulative canary rollout (10%, 40%, 100%).
   - Verified exact cohort partition sizing: Stage 0 = 10 devices, Stage 1 = 30 devices, Stage 2 = 60 devices.
   - Verified target snapshot compatibility evidence recording (OS, architecture normalization `x86_64 == amd64 == x64`, `aarch64 == arm64`, ROS distro, observed timestamp).

---

## 3. Real WebSocket Direction Enforcement & Attack Resistance

- Verified over real WebSocket sessions:
  - Unauthorized/unauthenticated connections rejected immediately (`1008`).
  - STAGE_RELEASE, ACTIVATE_RELEASE, CANCEL_DEPLOYMENT sent by edge agent to control plane rejected (`403 FORBIDDEN`).
  - Valid `DEPLOYMENT_ACK` and `DEPLOYMENT_STATUS` frames accepted.
  - Corrupted correlation attacks (altered `device_id`, stale `generation`, mismatched `instruction_id`) rejected and logged.

---

## 4. Key Security & Architecture Amendments Incorporated

- **Whole-Instruction Canonical Replay Digest**: Complete binding of `protocol_version`, `instruction_id`, `deployment_id`, `device_id`, `generation`, `instruction_type`, `payload`, `created_at`, `expires_at`.
- **Status Report Instruction Binding**: Reports strictly verified against active expected instruction.
- **Strict ACK Correlation**: Non-terminal status enforcement, terminal rejection on `EXPIRED`/`CANCELLED`/`FAILED`.
- **Artifact Source Immutability**: Referenced sources are frozen against mutation (`409 Conflict`).
- **Authoritative Agent Source Registry**: Agent local `TrustedArtifactSourceRegistry` is the security authority; unknown source IDs fail closed.
- **SSRF & DNS TOCTOU Transparency**: DNS preflight SSRF mitigation implemented; DNS validation-to-connect TOCTOU / rebinding documented as residual risk.
- **Rate Limiting & Redaction**: Authenticated rate limiting and <= 64 KiB bounded event storage with recursive secret redaction.
- **Lease Lifecycle**: Mutating deployments acquire exclusive device leases with automatic orphan cleanup on terminal states.
