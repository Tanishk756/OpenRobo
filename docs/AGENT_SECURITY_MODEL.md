# OpenRobo Agent & Fleet Security Model (Milestone 7.1.1)

**Document:** Agent & Fleet Security Model
**Version:** 1.1.0 (Milestone 7.1.1 Closure)
**Maintainer:** Tanishk Singhal
**Classification:** Open Source Security Architecture & Trust Model

---

## 1. Core Trust Boundaries

OpenRobo separates untrusted edge environments from the central control plane with cryptographic identity and explicit transport termination models:

```
+-------------------------------------------------------------+
|                     Robot / Edge Device                     |
|                                                             |
|  +------------------+          +-------------------------+  |
|  |   ROS 2 Graph    |          |     openrobo-agent      |  |
|  | (Nodes, Topics)  | <------> |  (Read-Only Collectors) |  |
|  +------------------+          +-------------------------+  |
|                                             |               |
|                         Local Key Storage (0600)            |
|                         [Ed25519 Private Key]               |
+-------------------------------------------------------------+
                                              |
                   Mutual TLS (mTLS) Transport
                   [Client Cert + Strict Envelope]
                                              |
+-------------------------------------------------------------+
|                   OpenRobo Control Plane                    |
|                                                             |
|  +--------------------------+   +------------------------+  |
|  | Direct mTLS / Reverse    |   | Fleet Device Registry  |  |
|  | Proxy Header Sanitizer   |   | (Hashed Tokens, Single |  |
|  | Replay & Rate Limiter    |   |  Use, Revocation State)|  |
|  +--------------------------+   +------------------------+  |
+-------------------------------------------------------------+
```

### 1.1 Non-Negotiable Invariants
1. **No Remote Code Execution:** The agent does NOT expose any shell execution, script execution, or `eval()` interface. Remote commands are restricted to a strict read-oriented enum (`PING`, `GET_AGENT_INFO`, `GET_RUNTIME_STATUS`, `GET_ROS_ENVIRONMENT`, `GET_ROS_GRAPH`, `GET_RUNTIME_DIAGNOSTICS`, `GET_CONNECTION_INSPECTOR_STATUS`, `GET_SIMULATOR_STATUS`). Primitives such as `EXEC`, `SHELL`, `RUN_SCRIPT` are completely prohibited.
2. **Key Exclusivity:** Device private keys are generated on the robot using the mature `cryptography` package (Ed25519 or ECDSA P-256) and saved with restrictive `0600` permissions. Private keys are never transmitted over the network or persisted centrally.
3. **Primary Identity:** The primary identity is `device_id` (UUIDv4) + locally generated private key + signed X.509 Device Certificate. Hardware fingerprinting is optional telemetry metadata, never an authentication root.
4. **No Trust of Client Headers:** Client-supplied identity headers (`X-Client-Cert-Fingerprint`, `X-OpenRobo-Cert-Fingerprint`) are rejected unless operating in explicit reverse-proxy mode originating from a configured trusted proxy subnet.

---

## 2. TLS Termination & Proxy Trust Models

OpenRobo defines two explicit transport termination models:

### Mode A: Direct mTLS (`DIRECT_MTLS`)
- The ASGI application / HTTP server performs direct mutual TLS handshake.
- Client presents X.509 certificate signed by the trusted fleet CA.
- Verification checks validity window (`not_valid_before`, `not_valid_after`), chain of trust, and revocation status.

### Mode B: Trusted Reverse-Proxy mTLS (`TRUSTED_PROXY_MTLS`)
- An edge reverse proxy (e.g. Nginx, Traefik, Envoy, Caddy) terminates mTLS and validates client certificates.
- The proxy sanitizes and injects `X-SSL-Client-Fingerprint` or `X-Client-Cert-Fingerprint`.
- OpenRobo accepts certificate identity headers ONLY when:
  1. `OPENROBO_PROXY_CERT_AUTH=true` is explicitly enabled.
  2. The incoming TCP request originates from an IP address in `OPENROBO_TRUSTED_PROXIES` (e.g. `127.0.0.1`, internal Kubernetes cluster CIDR).
  3. Requests originating from untrusted source IPs have proxy headers stripped and ignored.

---

## 3. Cryptographic Device Identity & PKI

### 3.1 Certificate Specifications
- **Format:** X.509 v3
- **Subject Common Name (CN):** `openrobo-device:{device_id}`
- **Key Algorithm:** Ed25519 (or ECDSA NIST P-256)
- **Signature Algorithm:** PureEd25519 (or SHA256withECDSA)
- **Validity Source:** `not_valid_after_utc` parsed directly from the issued certificate.
- **Fingerprint:** SHA-256 over DER-encoded certificate.

### 3.2 Certificate Authority Abstraction & Dev CA Hard Gate
- The PKI subsystem implements an abstract `CertificateAuthority` interface.
- **Development CA (`DevelopmentCA`):**
  - Hard-gated behind `OPENROBO_DEV_CA=true`.
  - Instantiation in `production` environment raises `RuntimeError`.
  - Instantiation without `OPENROBO_DEV_CA=true` raises `PermissionError`.
  - Persistent storage: Writes `ca.key` (0600 permissions) and `ca.crt` to `.openrobo/ca` to preserve CA root identity across restarts.

---

## 4. Enrollment Protocol & Token Lifecycle

1. **Token Generation:** Administrative endpoint `POST /fleet/enrollment-tokens` generates a cryptographically secure token (`orb_tok_<32_bytes_urlsafe>`). Only the SHA-256 hash is stored in the database.
2. **Device Binding:** Tokens may be pre-bound to a specific `device_name` or `device_id`. Mismatched enrollment requests are rejected with `403 Forbidden`.
3. **Atomic Consumption & Expiry Check:**
   ```sql
   UPDATE agent_enrollment_tokens
   SET is_used = true, used_at = :now, used_by_device_id = :device_id
   WHERE token_hash = :hash AND is_used = false AND expires_at > :now
   ```
   Single-use consumption is enforced transactionally, preventing double-use race conditions.
4. **CSR Validation:** Control plane verifies CSR cryptographic signature, supported public key algorithms, and Common Name match before signing.

---

## 5. Protocol Envelope & Replay Protection

Every message conforms to `MessageEnvelope`:
- `protocol_version` (strictly `"1.0"` or `"1.1"`)
- `message_id` (UUIDv4)
- `device_id` (Device UUID)
- `timestamp` (ISO-8601 UTC)
- `message_type` (Enum)
- `payload` (JSON Dictionary)

### 5.1 Replay Protection Semantics
- Sliding timestamp window (±60 seconds). Messages with stale or future timestamps exceeding clock skew are rejected (`400 Bad Request`).
- Bounded in-memory deduplication store (50,000 entries) tracking `(device_id, message_id)`. Replayed messages are rejected (`409 Conflict`).

---

## 6. Authorization & Revocation Enforcement

1. **Device Isolation:** Authenticated device $A$ can only read/write resources belonging to device $A$. Cross-device writes return `403 Forbidden`.
2. **Immediate Revocation Effect:**
   - Database record updated to `status = 'REVOKED'` and `revoked_at = now()`.
   - Active WebSocket connections for the revoked device are closed immediately with WebSocket code `1008` (Policy Violation).
   - Subsequent heartbeat, telemetry, or WebSocket handshakes return `403 Forbidden`.

---

## 7. Administrative API Authorization & Rate Limits

1. **Admin Authorization:** Control-plane endpoints (`/fleet/enrollment-tokens`, `/fleet/devices`, `/fleet/devices/{id}/revoke`, `/fleet/devices/{id}/telemetry`) require `X-OpenRobo-Admin-Key` or `Authorization: Bearer <key>`.
2. **Rate Limits & Payload Bounds:**
   - Token creation: 60 requests / minute.
   - Device enrollment: 30 requests / minute.
   - Heartbeat: 180 requests / minute per device.
   - Telemetry: 300 requests / minute per device (batch limit 500 events).
   - CSR payload limit: 16KB.
