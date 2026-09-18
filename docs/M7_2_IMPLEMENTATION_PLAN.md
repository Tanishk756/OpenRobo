# OpenRobo Milestone 7.2 — Implementation Plan
**Objective:** Secure Over-the-Air (OTA) Workspace Deployments, Staged Rollouts & Fleet Orchestration
**Status:** SPLIT INTO STAGED MILESTONES (M7.2.1 Active; M7.2.2 & M7.2.3 Planned)
**Maintainer:** Tanishk Singhal

---

## 1. Overview & Context

Milestone 7.1 and 7.1.2 established the secure remote agent foundation, Ed25519 X.509 device identity, verified network mTLS, offline telemetry spools, and real-time fleet health monitoring.

Milestone 7.2 transitions OpenRobo from passive read-oriented fleet observation to **active, reliable, and cryptographically verified Over-the-Air (OTA) deployment execution** across heterogeneous robotics fleets.

To maintain strict security verification standards, Milestone 7.2 is divided into three distinct execution phases:
1. **Milestone 7.2.1**: Signed Release Artifacts, Safe Extraction & Local A/B Deployment Foundation *(Current Focus)*
2. **Milestone 7.2.2**: Authenticated Remote Deployment Orchestration & Canary Rollout
3. **Milestone 7.2.3**: Runtime Health Gates, Automatic Rollback & Fleet Studio Rollout UI

---

## 2. Core Architectural Pillars

### 2.1 Cryptographically Signed Release Artifacts & Detached Signatures (M7.2.1)
- **Deterministic Archiving**: Packages generated workspaces into immutable `.tar.gz` release artifacts with normalized timestamps, permissions, and UID/GID metadata.
- **Strict Secret Exclusion**: Release packager automatically denies private keys (`*.key`, `*.pem`), credentials, tokens, `.env` files, and sensitive directories.
- **Ed25519 Detached Signing**: `ReleaseSigner` produces detached `.sig` files over canonical JSON manifest bytes (`ReleaseManifest`).
- **Cryptographic Verification Before Staging**: The agent verifies digital signatures against trusted release public keys, validates artifact SHA-256 hashes, and rejects untrusted/modified artifacts prior to extraction.

### 2.2 Safe Artifact Extraction & Quarantine (M7.2.1)
- **Path Traversal Protection**: `SafeArtifactExtractor` rigorously rejects `../`, `..\`, absolute POSIX paths, Windows drive letters (`C:\`), UNC paths, duplicate normalized entries, and NUL bytes.
- **Symlink & Resource Safeguards**: Blocks symlinks and hardlinks pointing outside the extraction root, device files, FIFOs, and enforces configurable limits on file counts, individual sizes, and decompression ratios.
- **Post-Extraction Integrity Verification**: Recalculates SHA-256 hashes for all extracted files against the manifest before marking the artifact `STAGED`.

### 2.3 Atomic Local A/B Workspace Partitioning & Mechanical Rollback (M7.2.1)
- **Dual Partitioning**: Maintains `slot-a` and `slot-b` under `/var/lib/openrobo-agent/workspaces/` (or configured agent state directory).
- **Atomic Pointer Switch**: Switches active workspace atomically using pointer replacement (`current.next` -> `current`).
- **Previous Slot Preservation**: Active slot transition marks previous slot as `PREVIOUS` without deletion, retaining it as a verified rollback candidate.
- **Mechanical Rollback Primitive**: `rollback_to_previous()` provides a deterministic local rollback mechanism.

### 2.4 Platform-Specific Deployment Safety Policies (`DeploymentSafetyPolicy`)
- **No Universal Hardcoded Thresholds**: Safety requirements (battery levels, motion states, e-stops) are platform-specific, explicitly declared, and evidence-backed:
  ```yaml
  deployment_safety_policy:
    platform_type: "ugv_differential_drive"
    battery_requirement:
      enabled: true
      threshold_percent: 30.0
      telemetry_source: "sensor_msgs/BatteryState"
    motion_requirement:
      enabled: true
      required_state: "STATIONARY"
      telemetry_source: "geometry_msgs/Twist"
      max_linear_velocity: 0.01
    estop_requirement:
      enabled: true
      state_source: "std_msgs/Bool"
      safe_states: ["ENGAGED", "ACTIVE"]
    on_unknown_state: "BLOCK_DEPLOYMENT"
  ```
- **Strict Unknown State Handling**: Missing, stale, or unrecognized telemetry strictly evaluates to `UNKNOWN`, which blocks deployment.

### 2.5 Authenticated Remote Deployment Orchestration (M7.2.2)
- Control plane issues cryptographically signed deployment instructions with release metadata and target constraints.
- Multi-device canary rollouts with configurable bake times and automatic circuit-breaking.

### 2.6 Health-Gated Rollouts & Automated Fleet Rollback (M7.2.3)
- Live ROS 2 node/topic graph contract evaluation post-activation.
- Automated rollback triggering upon health contract violation or crashloops.
- Next.js Fleet Studio OTA management dashboard.

---

## 3. Staged Implementation Breakdown

| Stage | Scope | Key Deliverables |
|---|---|---|
| **M7.2.1** *(Active)* | Signed Artifacts & Local A/B Foundation | `openrobo_release` package, canonical manifest, Ed25519 signing/verification, deterministic archiving, safe extraction, `ABSlotManager`, atomic activation, mechanical rollback primitive, real filesystem acceptance test. |
| **M7.2.2** *(Planned)* | Remote Deployment & Canary Orchestration | Control-plane deployment state machine, signed deployment envelopes, device targeting, staged canary rollouts, artifact distribution abstraction. |
| **M7.2.3** *(Planned)* | Health-Gated Rollout & Rollback UI | Post-activation runtime health contract gate, automated rollback triggering, Fleet Studio OTA rollout tracking UI. |
