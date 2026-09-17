# OpenRobo Agent & Fleet Security Model (Milestone 7.1)

**Document:** Agent & Fleet Security Model  
**Version:** 1.0.0 (M7.1)  
**Maintainer:** Tanishk Singhal  
**Classification:** Open Source Security Architecture  

---

## 1. Core Trust Boundaries

OpenRobo's distributed architecture separates untrusted edge environments from the central control plane:

```
┌─────────────────────────────────────────────────────────┐
│                    Robot / Edge Device                  │
│                                                         │
│  ┌──────────────────┐          ┌─────────────────────┐  │
│  │   ROS 2 Graph    │          │  openrobo-agent     │  │
│  │ (Nodes, Topics)  │◄─────────┤ (Read-Only Sensors) │  │
│  └──────────────────┘          └──────────┬──────────┘  │
│                                           │             │
│                       Local Key Storage (0600)          │
│                       [Ed25519 Private Key]             │
└───────────────────────────────────────────┼─────────────┘
                                            │
                   Mutual TLS (mTLS) Transport
                   [Client Cert + Strict Envelope]
                                            │
┌───────────────────────────────────────────▼─────────────┐
│                  OpenRobo Control Plane                 │
│                                                         │
│  ┌───────────────────────┐   ┌───────────────────────┐  │
│  │ FastDDS / WebSocket   │   │ Fleet Device Registry │  │
│  │ Termination           ├──►│ (Hashed Tokens,       │  │
│  │ Replay Deduplication  │   │  Revocation State)    │  │
│  └───────────────────────┘   └───────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 1.1 Non-Negotiable Invariants
1. **No Remote Code Execution:** The agent does NOT expose any shell execution, script execution, or `eval()` interface. All control messages are strictly typed, read-oriented enums.
2. **Key Exclusivity:** Device private keys are generated on the robot using `cryptography` (Ed25519 or ECDSA P-256) with `0600` permissions. Private keys are never transmitted over the network or saved centrally.
3. **No Unauthenticated State Mutations:** All telemetry ingestion requires valid mTLS certificate authentication.
4. **No Trust of Client Headers:** Headers such as `X-Device-ID` or `X-Certificate-Fingerprint` are never trusted unless explicitly operating in `proxy-certificate` mode behind a configured, sanitizing reverse proxy.

---

## 2. Cryptographic Device Identity & PKI

### 2.1 Identity Hierarchy
1. **Primary Root Identity:** `device_id` (UUIDv4) + locally generated private key (Ed25519) + signed X.509 Device Certificate.
2. **Secondary Anomaly Signals:** OS, architecture, kernel version, hostname hash (used only for telemetry and anomaly detection, NEVER for authentication).

### 2.2 Certificate Specifications
- **Format:** X.509 v3
- **Subject Common Name (CN):** `device_id` (e.g. `openrobo-device:urn:uuid:<UUID>`)
- **Key Algorithm:** Ed25519 (or ECDSA NIST P-256)
- **Signature Algorithm:** Ed25519 (or SHA256withECDSA)
- **Validity Window:** Configurable (default 90 days in production; short-lived development certs).
- **Fingerprint:** SHA-256 over DER-encoded certificate.

### 2.3 Local Development CA
- Development PKI is handled via `openrobo_agent.certificates.DevelopmentCA`.
- **Safety Gate:** The development CA requires explicit activation via `OPENROBO_DEV_CA=true` or an explicit developer initialization command. In production mode, the server warns or refuses if dev CA material is detected.

---

## 3. Enrollment Protocol

```
Agent                                                     Control Plane
  │                                                             │
  │                     1. Admin creates token                  │
  │                     ───────────────────────────────────────►│ (Stores SHA-256 hash)
  │                                                             │
  │ 2. Agent receives token + URL                               │
  │                                                             │
  │ 3. Generates Ed25519 Keypair locally (0600)                 │
  │ 4. Generates X.509 CSR with device UUID                     │
  │                                                             │
  │ 5. POST /api/v1/fleet/enroll (token, CSR, metadata)         │
  │ ───────────────────────────────────────────────────────────►│
  │                                                             │ 6. Validates token hash & expiry
  │                                                             │ 7. Transactionally marks token USED
  │                                                             │ 8. Signs CSR with CA key
  │                                                             │ 9. Registers FleetDeviceModel
  │ 10. Returns signed certificate + CA cert chain              │
  │◄────────────────────────────────────────────────────────────│
  │                                                             │
  │ 11. Stores certificate with 0600 permissions                │
  │ 12. Connects via mTLS WebSocket                             │
  │ ═══════════════════════════════════════════════════════════►│
```

### 3.1 Race Condition & Concurrency Defense
- The enrollment token is validated and invalidated within an atomic database transaction (`SELECT ... FOR UPDATE` or transactional update).
- If two concurrent requests attempt to consume the same token, exactly one succeeds; the other receives `400 Bad Request: Token already consumed or invalid`.

---

## 4. Replay Protection & Envelope Validation

Every message transmitted over the transport protocol uses the standardized `MessageEnvelope`:

```json
{
  "protocol_version": "1.0",
  "message_id": "urn:uuid:6ba7b810-9dad-11d1-80b4-00c04fd430c8",
  "device_id": "urn:uuid:550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-09-17T14:30:00.000Z",
  "message_type": "HEARTBEAT",
  "payload": { ... }
}
```

### 4.1 Server-Side Replay Defense Rules
1. **Clock Skew Window:** `abs(now() - envelope.timestamp) <= MAX_CLOCK_SKEW` (default 60s). Messages outside the window are rejected.
2. **Deduplication Cache:** The server maintains an in-memory bounded LRU / TTL cache of recent `(device_id, message_id)` tuples. Replayed message IDs are immediately rejected.
3. **Identity Match:** `envelope.device_id` must strictly match the authenticated client certificate subject CN. Cross-device spoofing is rejected with `403 Forbidden`.

---

## 5. Offline Telemetry Spool

The agent incorporates an `OfflineTelemetrySpool` backed by SQLite:
- **FIFO Eviction:** When `max_events` (default 5,000) or `max_bytes` (default 50 MB) is reached, the oldest unacknowledged events are dropped.
- **TTL Eviction:** Telemetry older than `max_age_days` (default 7 days) is automatically pruned.
- **Delivery Guarantee:** `at-least-once`. Server deduplication prevents duplicate processing on reconnect.

---

## 6. Threat Model & Residual Risks

| Threat | Mitigation | Residual Risk |
|---|---|---|
| **Stolen Enrollment Token** | Single-use, short TTL (e.g. 15 min), stored hashed (SHA-256). Token invalidated immediately upon first enrollment. | Window of vulnerability if token intercepted before legitimate agent enrolls. Admin can revoke device immediately. |
| **Compromised Robot Device** | Private key stored `0600`. Agent only has read-only operations. Revocation endpoint immediately rejects device. | Attacker with root on robot can exfiltrate private key and send fake telemetry until revoked. Cannot execute remote code on other robots or server. |
| **Cross-Device Impersonation** | Control plane enforces `cert.subject.device_id == request.device_id`. | None; cryptographic binding prevents cross-device tampering. |
| **Message Replay Attack** | Sliding timestamp window (±60s) + server-side message ID deduplication cache. | None within the deduplication retention period. |
| **Man-In-The-Middle (MITM)** | TLS 1.3 with pinned CA certificate validation on both client and server. | None assuming CA integrity. |
| **Cross-Device Data Exfiltration** | Telemetry schema strictly scrubs environment variables, command line arguments, usernames, and SSIDs. | None; only structured robot health telemetry is transmitted. |
