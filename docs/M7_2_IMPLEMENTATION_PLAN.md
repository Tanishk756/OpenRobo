# OpenRobo Milestone 7.2 — Implementation Plan
**Objective:** Secure Over-the-Air (OTA) Workspace Deployments, Staged Rollouts & Fleet Orchestration  
**Status:** DRAFT (Ready for Review; Execution Blocked until M7.1 Merge)  

---

## 1. Overview & Context

Milestone 7.1 established the secure remote agent foundation, Ed25519 X.509 device identity, mTLS trust boundaries, offline telemetry spools, and real-time fleet health monitoring. 

Milestone 7.2 transitions OpenRobo from passive read-oriented fleet observation to **active, reliable, and cryptographically verified Over-the-Air (OTA) deployment execution** across heterogeneous robotics fleets.

---

## 2. Core Architectural Pillars for M7.2

### 2.1 Cryptographically Signed Deployment Packages
- **Artifact Signing**: Build workspaces and manifest lockfiles generated in M5/M5.1 will be bundled into immutable `.tar.zst` release artifacts, signed by the control-plane Release Key.
- **Agent-Side Verification**: Before unpacking any workspace, the agent verifies the digital signature against the control-plane trusted public keys. Unsigned or tampered artifacts are immediately rejected.

### 2.2 Atomic A/B Workspace Partitioning & Zero-Downtime Switching
- **Dual Partitioning**: Maintain `active` and `staged` workspace directories on target robots (e.g. `/var/lib/openrobo-agent/workspaces/slot-a` and `slot-b`).
- **Atomic Symlinking**: Atomic symlink switch (`current -> slot-b`) only after full pre-flight verification passes.
- **Process Supervision**: Agent manages ROS 2 launch processes using `systemd` user services or isolated child process groups with graceful `SIGINT`/`SIGTERM` handling.

### 2.3 Pre-Flight & Post-Flight Health Gates & Platform-Specific Deployment Policies
- **Platform-Specific Deployment Policies (`DeploymentSafetyPolicy`)**:
  - Do NOT use universal hardcoded thresholds (such as universal battery >= 30% or stationary requirements) across heterogeneous robots.
  - Policies are resource- and platform-specific, explicitly configured, and evidence-backed:
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
  - **Explicit Unknown-State Policy**: If any configured telemetry source is unavailable or unknown, deployment is strictly **BLOCKED**. No guessing or optimistic assumptions.

### 2.4 Automatic Rollback Mechanism
- If post-flight health verification fails or times out:
  1. Agent aborts the rollout.
  2. Reverts the `current` symlink to the previous known-good slot.
  3. Restarts previous ROS 2 nodes.
  4. Emits an `OTA_ROLLBACK_TRIGGERED` telemetry event to the control plane with failure diagnostic logs.

### 2.5 Fleet Staged Rollout Orchestration
- **Phased Rollouts**:
  - Phase 1: Canary node (e.g., 1 designated robot in test environment).
  - Phase 2: 10% of fleet with 10-minute bake time.
  - Phase 3: Remainder of fleet with automatic circuit-breaking if canary error rate exceeds 0%.
- **Target Filtering**: Deploy by domain (`ugv`, `manipulation`, `uav`), tags, capabilities, or individual device UUIDs.

---

## 3. Scope Boundaries & Non-Goals for M7.2

- **No Arbitrary Remote Shells**: OTA will only apply structured, signed OpenRobo workspace packages. No arbitrary `bash` or raw remote execution endpoints will be added.
- **No Kernel/Firmware Flashing**: M7.2 focuses on application-level robotics stacks (ROS 2 workspaces, launchfiles, configurations), not low-level BIOS/microcontroller flashing.
- **No Zenoh/DDS Multi-Robot Meshing**: Multi-robot DDS discovery and cross-robot communication federation remain in Milestone 8.

---

## 4. Verification & Testing Strategy

1. **Local Agent OTA Sandbox**:
   - Unit tests for artifact signature verification, A/B directory switching, and atomic symlink rollback.
2. **End-to-End Canary Deployment Test**:
   - Deploy Workspace v1 to 3 simulated robots -> verify all online.
   - Deploy Workspace v2 (healthy) to Canary -> verify promotion to fleet.
   - Deploy Workspace v3 (faulty launchfile) to Canary -> verify automated rollback on Canary, preventing fleet-wide deployment.
3. **Simulated Fleet Rollout Benchmark**:
   - Run staged rollout across 50 simulated agents with staged progress tracking and live status reporting in Fleet Studio.

---

## 5. Implementation Roadmap

| Phase | Milestone 7.2 Sub-Tasks | Estimated Scope |
|---|---|---|
| Phase 1 | Artifact Packaging, Signing & Agent Verification | Backend & Agent Core |
| Phase 2 | A/B Slot Manager, Process Supervisor & Atomic Switch | Agent Core |
| Phase 3 | Pre/Post-Flight Health Gates & Auto-Rollback Engine | Agent Core & Runtime Core |
| Phase 4 | Control-Plane Deployment Orchestrator & Canary Logic | API & Database Models |
| Phase 5 | Fleet Studio OTA Deployment UI & Live Rollout Tracker | Web App |
| Phase 6 | End-to-End Canary & Rollback Integration Tests | Integration Suite |
