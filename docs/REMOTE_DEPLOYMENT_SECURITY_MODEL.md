# Remote Deployment Security Model & Architecture (M7.2.2.1)

## 1. Overview & Trust Model

Milestone 7.2.2.1 establishes authenticated remote deployment orchestration, trusted artifact distribution, and operator-gated multi-stage canary rollouts.

The security architecture guarantees that:
1. **Control-Plane Release Catalog & Immutability**: All deployable releases are registered with cryptographic digest snapshots. Once referenced by any active or completed deployment, the release tuple `(release_id, manifest_digest, artifact_digest, workspace_digest, release_key_id, artifact_source_id)` and its underlying artifact source configurations are immutable.
2. **Direction-Enforced WebSocket Protocol**: Strict allowlists prevent command injection or privilege escalation across WebSocket boundaries. Agents cannot submit operator commands (e.g. `STAGE_RELEASE`), and the server strictly correlates `DEPLOYMENT_ACK` and `DEPLOYMENT_STATUS` against authenticated device identities and active generation numbers.
3. **SSRF & Artifact Source Hardening**:
   - **Authoritative Agent Registry**: The edge agent's local `TrustedArtifactSourceRegistry` is the security authority. The server supplies only the `artifact_source_id`; base URLs, allowed hosts, CA roots, and network permissions are resolved locally.
   - **URL Sanitization**: Rejects embedded credentials, query strings, fragments, and invalid hostnames.
   - **DNS Preflight SSRF Mitigation**: Complete address preflight checks block cloud metadata (`169.254.169.254`, `100.100.100.200`), loopback, link-local, and private subnets unless explicitly permitted by local configuration.
   - **Residual Risk Disclosure**: *DNS preflight SSRF mitigation implemented. DNS validation-to-connect TOCTOU / rebinding remains a residual risk.*
4. **Whole-Instruction Replay Digest & Monotonic Generations**: Each deployment instruction binds the entire security-relevant instruction payload (`protocol_version`, `instruction_id`, `deployment_id`, `device_id`, `generation`, `instruction_type`, `payload`, `created_at`, `expires_at`). Agents persist atomic generation state via `generation_state.json` and enforce idempotency using complete instruction digests.
5. **Durable Instruction Outbox**: Instructions survive control-plane restarts, agent disconnections, and network drops with exponential retry backoff (`attempt_count`, `last_attempt_at`, `next_attempt_at`).
6. **Exclusive Device Leases**: Only one active mutating deployment may hold an exclusive device deployment lease (`DeviceDeploymentLeaseModel`). Leases survive control plane restarts and are safely released upon reaching terminal state.
7. **Strict Operator Gates**: Canary promotions and cohort activations are strictly operator-gated via `POST /api/v1/deployments/{id}/approve` using optimistic concurrency versioning (`version`).
8. **Bounded Storage & Recursive Secret Redaction**: All deployment events and reports are bounded to <= 64 KiB with recursive redaction of authorization headers, tokens, keys, passwords, and credentials prior to persistence.
