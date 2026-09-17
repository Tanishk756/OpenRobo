# Milestone 7 — Distributed Fleet Management, Remote Agents & Telemetry Transport

**Milestone:** M7 — Distributed Fleet Management, Remote Agents & Telemetry Transport
**Project:** OpenRobo
**Owner / Maintainer:** Tanishk Singhal
**Status:** PLANNED (Do NOT implement in M6.1)

---

## 1. Objective

Extend OpenRobo beyond single-workspace and local-host execution into distributed multi-robot fleet management, remote edge agents, encrypted telemetry transport, and remote over-the-air (OTA) workspace deployment.

---

## 2. Planned Subsystems & Scope Boundaries

### 2.1 Remote Runtime Agent (`openrobo-agent`)
- Lightweight, secure Python/Rust edge daemon running on target robot compute (Raspberry Pi, Jetson Orin, x86 IPC).
- Mutual TLS (mTLS) authentication and device identity tokens.
- Secure command reception for workspace deployment and lifecycle management.

### 2.2 Fleet Health & Telemetry Transport
- Bounded WebSocket / gRPC telemetry transport streaming live node liveness, topic rates, and hardware diagnostics to central OpenRobo control plane.
- Offline buffering and bandwidth-constrained rate throttling.

### 2.3 Remote Workspace Deployment & Rollback
- Remote artifact push with cryptographic lockfile verification (`openrobo.lock.json`).
- Atomic container and workspace rollout with automatic rollback on runtime health check failure.

### 2.4 Multi-Robot Graph Federation
- Multi-domain ID bridging and Zenoh/DDS topic namespace isolation across fleet members.

---

## 3. Implementation Prerequisites

- Successful completion and merge of Milestone 6.1 (`feature/m6-live-runtime-wiring`).
- Protected branch CI verification on `main`.
