# Milestone 7 — Distributed Fleet Management, Remote Agents & Telemetry Transport

**Milestone:** M7 — Distributed Fleet Management, Remote Agents & Telemetry Transport
**Project:** OpenRobo
**Owner / Maintainer:** Tanishk Singhal
**Status:** REFINED PLAN (Ready for implementation gate after M6.2 merge)

---

## 1. Objective

Extend OpenRobo beyond single-workspace and local-host execution into distributed multi-robot fleet management, remote edge agents, encrypted telemetry transport, and remote over-the-air (OTA) workspace deployment, grounded in the proven M6.2 runtime evidence model (`RUNTIME_VERIFIED`, `BUILD_VERIFIED`).

---

## 2. Architecture & Subsystems Grounded in M6.2 Evidence Model

### 2.1 Remote Runtime Agent (`openrobo-agent`)
- Lightweight, secure Python edge daemon running on target robot compute (e.g. Raspberry Pi, Jetson Orin, x86 industrial PCs).
- Mutual TLS (mTLS) authentication and device identity tokens with hardware fingerprinting.
- Integrates M6.2 `LiveRosGraphCollector` and `RosEnvironmentDetector` for edge-native graph introspection.
- Secure command reception for workspace deployment and runtime lifecycle management.

### 2.2 Fleet Health & Telemetry Transport
- Bounded WebSocket / gRPC telemetry transport streaming live node liveness, topic rates, QoS policy status, and hardware diagnostics to central OpenRobo control plane.
- Offline buffering, priority queues, and bandwidth-constrained rate throttling over cellular/lossy links.
- Emits structured events matching OpenRobo's SSE event schema (`/api/v1/runtime/sessions/{id}/events`).

### 2.3 Remote Workspace Deployment & Rollback
- Remote artifact push with cryptographic lockfile verification (`openrobo.lock.json`) and SHA-256 workspace digests.
- Atomic container and workspace rollout with automatic rollback on runtime health check failure (evaluated via M6.2 `ConnectionComparator` against declared `RuntimeContract`).

### 2.4 Multi-Robot Graph Federation
- Multi-domain ID bridging, Zenoh/DDS topic namespace isolation, and TF prefix management across fleet members.

---

## 3. Implementation Prerequisites & Gates

1. **M6.2 Gate Passed:**
   - Real ROS 2 environment discovered (`RosEnvironmentDetector`).
   - Live ROS graph collected via native `rclpy` (`LiveRosGraphCollector`).
   - Runtime contract evaluation verified (`ConnectionComparator` -> `RUNTIME_VERIFIED`).
   - Intentional contract and QoS failure detection verified (`QoSEvaluator` -> `INCOMPATIBLE`).
   - Real native `colcon build` executed on generated workspace fixture (`BUILD_VERIFIED`).
2. **Protected Main Branch CI Clean:** All remote checks green on GitHub Actions.

---

## 4. Phased Execution Roadmap for M7

- **Phase 1: Remote Agent Daemon & Identity Core (`packages/agent-core`)**
  - Edge daemon daemonization, mTLS client certificates, heartbeat telemetry loop.
- **Phase 2: Fleet Control Plane API (`apps/api/routers/fleet.py`)**
  - Fleet registration, robot device inventory, dynamic session orchestration across distributed nodes.
- **Phase 3: Telemetry Stream Aggregator & Transport**
  - High-throughput WebSocket ingestion, time-series metrics storage, rate limiting.
- **Phase 4: Remote Deployment Engine & Rollback Controller**
  - Signed bundle distribution, remote `colcon build` / container orchestration, runtime contract health checks.
- **Phase 5: Fleet Studio UI (`apps/web/app/fleet/`)**
  - Multi-robot map, topology visualizer, live fleet QoS monitoring, remote deployment controls.
