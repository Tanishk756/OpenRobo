# Remote Deployment Security Model & Architecture (M7.2.2)

## 1. Overview & Trust Model

Milestone 7.2.2 introduces authenticated remote deployment orchestration, trusted artifact distribution, and operator-gated multi-stage canary rollouts.

The security architecture guarantees that:
1. **Control-Plane Release Catalog & Immutability**: All deployable releases are registered with cryptographic digest snapshots. Once referenced by any active or completed deployment, the release tuple `(release_id, manifest_digest, artifact_digest, workspace_digest, release_key_id, artifact_source_id)` is immutable.
2. **Direction-Enforced WebSocket Protocol**: Strict allowlists prevent command injection or privilege escalation across WebSocket boundaries. Agents cannot submit operator commands, and the server never interprets arbitrary telemetry as deployment status.
3. **SSRF & Artifact Source Hardening**: Artifact client enforces strict URL validation (rejecting credentials, fragments, query strings), complete DNS pre-flight address checks (blocking cloud metadata `169.254.169.254`, loopback, link-local, and private subnets unless explicitly allowlisted), streaming with byte limits, `.part` quarantine downloads, and continuous SHA-256 calculation.
4. **Atomic Monotonic Generation Replay Protection**: Each deployment instruction carries a globally monotonic generation number allocated via database-locked counters (`DeploymentCounterModel` with `FOR UPDATE`). Agents maintain atomic `generation_state.json` written via temporary file, fsync, and replace.
5. **Durable Instruction Outbox**: Commands survive control-plane restarts, agent disconnections, and network drops. Delivery requires explicit `DEPLOYMENT_ACK` envelopes before transitioning outbox status to `ACKNOWLEDGED`.
6. **Strict Operator Gates**: Canary promotions and cohort activations are strictly operator-gated via `POST /api/v1/deployments/{id}/approve` using optimistic concurrency versioning (`version`).

---

## 2. Protocol Boundaries & Direction Allowlist

| Direction | Allowed Operation Types | Forbidden / Rejected Types |
| :--- | :--- | :--- |
| **Server -> Agent** | `DEPLOYMENT_INSTRUCTION` (with typed payloads: `STAGE_RELEASE`, `ACTIVATE_RELEASE`, `CANCEL_DEPLOYMENT`, `GET_DEPLOYMENT_STATUS`) | Generic execution commands (`COMMAND`, `EXEC`, `RUN`, `TASK`, `SCRIPT`) |
| **Agent -> Server** | `DEPLOYMENT_ACK`, `DEPLOYMENT_STATUS`, `DEPLOYMENT_EVENT`, `HEARTBEAT`, `TELEMETRY` | `STAGE_RELEASE`, `ACTIVATE_RELEASE`, `CANCEL_DEPLOYMENT`, operator approval commands |

---

## 3. Monotonic Generation State Machine

Agents maintain local state in `<agent_state>/generation_state.json` with the following structure:
```json
{
  "last_generation": 42,
  "last_deployment_id": "d-12345",
  "last_instruction_digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "updated_at": "2026-09-18T10:00:00Z"
}
```

Upon receiving a `DeploymentInstructionEnvelope`:
- If `generation < last_generation`: **REJECT** with `reason="STALE_GENERATION"`.
- If `generation == last_generation`:
  - If `payload_digest == last_instruction_digest`: **ACK** with `accepted=True`, `reason="IDEMPOTENT_REPLAY"`.
  - If `payload_digest != last_instruction_digest`: **REJECT** with `reason="REPLAY_CONFLICT"`.
- If `generation > last_generation`:
  - Atomically persist new state.
  - Return **ACK** with `accepted=True`, `reason="ACCEPTED"`.
  - Dispatch execution asynchronously under `device_lock`.

---

## 4. Artifact Download Quarantine & Verification Chain

```
[Instruction Received]
        |
        v
[Validate Base URL & Host Policy]
        |
        v
[Resolve DNS & Enforce SSRF Checks (Block 169.254.169.254, loopback, private ranges)]
        |
        v
[Stream to <agent_state>/downloads/<dep_id>/<digest>.part (Byte Limit Enforced)]
        |
        v
[Verify SHA-256 Digest & Atomic Rename to <digest>.tar.gz]
        |
        v
[Fetch Manifest JSON & Verify SHA-256 Digest]
        |
        v
[Fetch Detached Signature & Verify Ed25519 with TrustedReleaseKeyStore]
        |
        v
[Verify Target OS / Architecture / ROS Distro Compatibility]
        |
        v
[Safe Extraction to Inactive Slot & Check Manifest File Hashes]
        |
        v
[Update Slot State to VERIFIED & Report STAGED]
```

---

## 5. Canary Rollout & Operator Approval Concurrency

- **Cohort Sizing**: Stage sizes are calculated deterministically using `ceil(total_devices * stage_percentage / 100)`.
- **Cohort Device Assignment**: Sorted stable partition based on `SHA-256(deployment_id + ":" + device.id)`.
- **Optimistic Concurrency**:
  ```sql
  UPDATE deployments
  SET status = :target_state, version = version + 1
  WHERE id = :id AND version = :expected_version AND status = :expected_state
  ```
  Conflicting concurrent approval attempts result in `409 Conflict`.
