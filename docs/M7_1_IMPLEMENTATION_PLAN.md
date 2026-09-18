# Milestone 7.1 — Secure Remote Agent, Device Identity & Fleet Foundation Implementation Plan

**Milestone:** M7.1 — Secure Remote Agent, Device Identity & Fleet Foundation
**Project:** OpenRobo
**Owner / Maintainer:** Tanishk Singhal
**Status:** IN EXECUTION 🚀

---

## 1. Executive Summary & Purpose

Milestone 7.1 establishes OpenRobo's distributed edge architecture by introducing the `packages/agent-core` (`openrobo_agent`) package, cryptographic device identity, single-use token enrollment, X.509 mTLS certificates, a bounded offline telemetry spool, a central fleet inventory/control-plane API in `apps/api/routers/fleet.py`, and the Next.js 14 Fleet Studio at `/fleet`.

### Fundamental Security Mandates
1. **Zero Remote Execution:** NO `SHELL`, `EXEC`, `RUN_COMMAND`, `RUN_SCRIPT`, `PYTHON`, or `eval()` operations. All operations in M7.1 are strictly typed and read-oriented (`PING`, `GET_AGENT_INFO`, `GET_RUNTIME_STATUS`, `GET_ROS_ENVIRONMENT`, `GET_ROS_GRAPH`, `GET_RUNTIME_DIAGNOSTICS`, `GET_CONNECTION_INSPECTOR_STATUS`, `GET_SIMULATOR_STATUS`).
2. **Device-Rooted Identity:** The primary identity is `device_id` (UUID) + locally generated private key (Ed25519 / ECDSA P-256) + signed X.509 certificate. Hardware fingerprinting is optional anomaly metadata, never root authentication.
3. **No Key Exfiltration:** Device private keys are generated on-device with `0600` permissions and NEVER leave the robot.
4. **Single-Use Hashed Tokens:** Enrollment tokens are cryptographically random, short-lived, stored hashed (SHA-256), and transactionally invalidated upon enrollment to prevent double-use race conditions.
5. **Strict mTLS Boundary:** The control plane rejects unverified client certificates. Client-supplied headers like `X-Device-ID` are never trusted unless explicitly operating in proxy-certificate mode behind a verified, sanitizing reverse proxy.
6. **Telemetry Privacy:** Telemetry is strictly structured and sanitized. No usernames, home directories, process command lines, Wi-Fi SSIDs, or environment variables are transmitted.
7. **Offline Spool Bounding:** Local SQLite spool enforces message count, byte size, and age bounds with FIFO eviction. Delivery is `at-least-once` with server-side message ID deduplication.

---

## 2. Package Architecture (`packages/agent-core/`)

```
packages/agent-core/
├── pyproject.toml
├── openrobo_agent/
│   ├── __init__.py
│   ├── models.py           # DeviceIdentity, Heartbeat, Telemetry, Envelope schemas
│   ├── config.py           # AgentConfig, path resolvers, interval configs
│   ├── security.py         # Secret redaction, filesystem permission checks (0600)
│   ├── certificates.py     # X.509 CSR generation, cert parsing, Dev CA (OPENROBO_DEV_CA=true)
│   ├── identity.py         # DeviceIdentityManager, local key generation (Ed25519/P-256)
│   ├── enrollment.py       # One-time token enrollment client
│   ├── heartbeat.py        # System health, ROS environment, runtime state sampler
│   ├── telemetry.py        # Delta telemetry extractor and privacy sanitizer
│   ├── spool.py            # OfflineTelemetrySpool (SQLite FIFO bounded store)
│   ├── transport.py        # Transport abstraction, WebSocket client with backoff & jitter
│   ├── runtime.py          # Read-only introspection handler (delegates to runtime-core)
│   └── service.py          # Systemd unit generator (non-root default) and daemon runner
└── tests/
    ├── test_identity.py
    ├── test_certificates.py
    ├── test_enrollment.py
    ├── test_spool.py
    ├── test_replay.py
    ├── test_security.py
    └── test_transport.py
```

---

## 3. Database Models & Migrations (`apps/api/models/fleet.py`)

1. **`FleetDeviceModel`**:
   - `id`: String (UUID) primary key
   - `device_id`: String (UUID) unique
   - `display_name`: String
   - `status`: String enum (`PENDING_ENROLLMENT`, `ONLINE`, `DEGRADED`, `OFFLINE`, `REVOKED`, `UNKNOWN`)
   - `agent_version`: String
   - `os`: String
   - `architecture`: String
   - `ros_distro`: String nullable
   - `certificate_fingerprint`: String unique nullable
   - `certificate_serial`: String unique nullable
   - `last_heartbeat`: DateTime nullable
   - `capabilities`: JSON dict
   - `created_at`: DateTime
   - `updated_at`: DateTime

2. **`AgentEnrollmentTokenModel`**:
   - `id`: String (UUID) primary key
   - `token_hash`: String (SHA-256) unique
   - `device_id`: String nullable (pre-allocated device binding if any)
   - `issued_by`: String
   - `expires_at`: DateTime
   - `is_used`: Boolean default False
   - `used_at`: DateTime nullable
   - `created_at`: DateTime

3. **`AgentHeartbeatModel`**:
   - `id`: String (UUID) primary key
   - `device_id`: String foreign key
   - `timestamp`: DateTime
   - `status`: String
   - `ros_distro`: String nullable
   - `runtime_status`: String nullable
   - `cpu_percent`: Float nullable
   - `memory_percent`: Float nullable
   - `disk_percent`: Float nullable

---

## 4. API Endpoints (`apps/api/routers/fleet.py`)

- `POST /api/v1/fleet/enrollment-tokens`: Issue one-time enrollment token (returns token once, stores SHA-256 hash).
- `POST /api/v1/fleet/enroll`: Consume token, validate CSR, issue signed device certificate.
- `GET /api/v1/fleet/devices`: List all registered fleet devices with live state derivation.
- `GET /api/v1/fleet/devices/{id}`: Detailed device capabilities and current health.
- `POST /api/v1/fleet/devices/{id}/revoke`: Revoke device certificate and mark `REVOKED`.
- `GET /api/v1/fleet/devices/{id}/runtime`: Latest observed ROS graph telemetry for device.
- `GET /api/v1/fleet/devices/{id}/telemetry`: Historic hardware and QoS telemetry.
- `WebSocket /api/v1/fleet/agent/ws`: Authenticated agent telemetry stream with replay protection.
