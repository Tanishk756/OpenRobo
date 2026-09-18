# Milestone 7.1 Security Audit & Vulnerability Remediation Report

**Date**: September 17, 2026
**Auditor**: OpenRobo Fleet Security Team
**Scope**: OpenRobo Fleet Foundation, PKI, Agent Transport, and Control Plane Ingress
**Target Milestone**: Milestone 7.1.1 — Fleet Security Boundary Closure & Real mTLS Verification

---

## 1. Expected Trust Model vs. Actual Baseline Behavior

| Component | Documented / Expected Trust Model | Actual M7.1 Baseline Implementation | Risk Level |
|---|---|---|---|
| **Client Transport** | Agent uses Python `ssl.SSLContext` to authenticate via mTLS presentation of device certificate & private key. | `HttpTransportClient` used `urllib.request` with optional `X-Client-Cert-Fingerprint` header override without presenting actual TLS client certificates. | **CRITICAL** |
| **Header Trust** | Client-supplied identity headers (`X-Client-Cert-Fingerprint`, `X-OpenRobo-Cert-Fingerprint`) are rejected unless originating from verified reverse-proxy subnets. | Default fallback allowed dev header when `ENVIRONMENT` was unset (defaulting to `development`). | **HIGH** |
| **Development CA Gate** | Development CA must NEVER generate or use CA material unless `OPENROBO_DEV_CA=true` is explicitly provided. | `DevelopmentCA.__init__` checked `OPENROBO_DEV_CA` for a boolean flag but unconditionally generated CA keypairs and certificates in memory. | **HIGH** |
| **Dev CA Persistence** | Development CA keys/certs persist in `.openrobo/ca` (0600 permissions) across server restarts to allow certificate re-verification. | Dev CA generated new ephemeral keypairs on each instantiation/process restart, invalidating previously issued certs upon reload. | **MEDIUM** |
| **Enrollment Expiry Race** | Token consumption update must atomically enforce `expires_at > :now` along with `is_used=false`. | SQL update only checked `is_used=False`, creating a potential race where expired tokens could be consumed before an explicit query. | **MEDIUM** |
| **Token Device Binding** | Tokens bound to specific device IDs/names must reject enrollment attempts by mismatched devices. | Router did not strictly enforce token-device pre-binding. | **MEDIUM** |
| **CSR Validation** | Control plane must verify CSR signature, key algorithm (Ed25519/ECDSA), and Common Name (`openrobo-device:{device_id}`). | Router signed any parseable CSR without validating CN match or rejecting malformed subjects. | **HIGH** |
| **Cert Expiration Source** | `EnrollmentResponse.expires_at` must reflect the actual `not_valid_after` field from the signed X.509 certificate. | Independently computed `now + 365 days` in the router handler. | **LOW** |
| **WebSocket Ingress** | WebSocket endpoint must authenticate client certificate before session establishment, reject unauthenticated/revoked devices, and validate envelopes. | `/api/v1/fleet/agent/ws` accepted all incoming connections without authentication, envelope validation, replay checks, or revocation checks. | **CRITICAL** |
| **Admin Endpoints** | Control-plane endpoints (`/fleet/enrollment-tokens`, `/fleet/devices/...`) must require administrative authorization. | Publicly callable without admin authentication. | **HIGH** |
| **Rate & Payload Limits** | Server-side rate limiting and payload bounds on enrollment, telemetry, and WebSocket messages. | No bounding on payload sizes or request frequencies. | **MEDIUM** |

---

## 2. Identified Vulnerabilities & Technical Root Causes

### GAP-01: Agent Transport Missing TLS Client Certificate Presentation
- **Root Cause**: `HttpTransportClient` accepted `cert_path` and `key_path` but invoked `urllib.request.urlopen` without an `ssl.SSLContext` configured with `load_cert_chain`.
- **Remediation**: Re-engineer `HttpTransportClient` to build an `ssl.SSLContext` loading client certificate, private key, and trusted CA bundle. Enforce TLS 1.2+ minimum, hostname verification, and refuse plaintext `http://` in non-development modes.

### GAP-02: Client Header Spoofing via `client_cert_header_override`
- **Root Cause**: `client_cert_header_override` allowed clients to self-assert fingerprints.
- **Remediation**: Eliminate `client_cert_header_override` from agent transport. Require genuine mTLS client certificate presentation. In reverse-proxy mode, trust headers only if incoming requests originate from configured proxy IPs and proxy mode is explicitly enabled.

### GAP-03: Development Environment Default & Header Fallback
- **Root Cause**: `SecurityIdentityExtractor` defaulted `ENVIRONMENT` to `"development"`, automatically opening dev header fallback.
- **Remediation**: Change default environment to `"production"`. Require BOTH `ENVIRONMENT=development` AND `OPENROBO_ALLOW_DEV_CERT_HEADER=true` for test header inspection.

### GAP-04: Development CA Unconditional Generation
- **Root Cause**: `DevelopmentCA` initialized keys without checking whether `OPENROBO_DEV_CA` was enabled.
- **Remediation**: `DevelopmentCA` constructor raises `PermissionError` if `OPENROBO_DEV_CA=true` is not set. In production environments, attempting to instantiate `DevelopmentCA` raises `RuntimeError`.

### GAP-05: Ephemeral Development CA Key Material
- **Root Cause**: Every `DevelopmentCA` instance generated a fresh keypair and root cert.
- **Remediation**: Persist development CA private key (`ca.key`, 0600 permissions) and certificate (`ca.crt`) in the designated CA directory. Reload existing keys across server restarts.

### GAP-06: CA Abstraction Missing
- **Root Cause**: `FleetPKIService` directly depended on concrete `DevelopmentCA`.
- **Remediation**: Introduce abstract `CertificateAuthority` interface (`sign_csr`, `verify_certificate`, `get_ca_chain`, `revoke_certificate`).

### GAP-07: Atomic Enrollment Token Expiry Check
- **Root Cause**: `UPDATE ... WHERE is_used=false` did not include `expires_at > now`.
- **Remediation**: Include `expires_at > :now` in the atomic update predicate. Distinguish between invalid, already consumed, and expired tokens.

### GAP-08: Token Binding & CSR Subject Verification
- **Root Cause**: Tokens issued for a specific device could be used by any device ID.
- **Remediation**: Check `token_model.device_name` against `req.device_name` or `req.device_id`. Validate CSR subject Common Name matches `openrobo-device:{req.device_id}`.

### GAP-09: Unauthenticated WebSocket Ingress
- **Root Cause**: `/api/v1/fleet/agent/ws` called `await websocket.accept()` without client authentication or envelope verification.
- **Remediation**: Authenticate client before or immediately upon connection. Parse all incoming frames through `MessageEnvelope`. Enforce device authorization, replay protection, clock skew, and operation allowlists. Terminate connections on device revocation.

### GAP-10: Administrative Endpoint Protection & Rate Limiting
- **Root Cause**: Fleet management APIs lacked authentication and rate limits.
- **Remediation**: Introduce administrative authorization middleware (`X-OpenRobo-Admin-Key` / bearer token), in-memory bounded rate limiting for enrollment and telemetry, and strict payload size limits.

---

## 3. Residual Limitations & Single-Process Scope
- **In-Memory Rate Limiting & Replay Cache**: The replay protection cache and rate limiters operate in-memory within the ASGI process. In distributed multi-worker deployments, a shared store (e.g., Redis) will be required in production milestones.
- **Reverse Proxy mTLS Termination**: In containerized or Kubernetes environments, TLS termination typically occurs at the ingress/reverse proxy (Nginx, Traefik, Envoy, Caddy). OpenRobo supports direct mTLS as well as trusted reverse-proxy header injection with strict source IP verification.
