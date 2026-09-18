# OpenRobo Release Security Model (Milestone 7.2.1)

**Document:** Release Security Model & Cryptographic Threat Analysis  
**Version:** 1.0.0 (Milestone 7.2.1)  
**Maintainer:** Tanishk Singhal  
**Classification:** Open Source Security Architecture & Threat Model  

---

## 1. Overview & Trust Hierarchy

OpenRobo OTA deployments establish an explicit cryptographic chain of trust from the release authoring environment to edge robotics hardware:

```
+-------------------------------------------------------------+
|                Release Authoring / Build CI                 |
|                                                             |
|  Workspace Files ----> Deterministic Packager               |
|                              |                              |
|                              v                              |
|                     .tar.gz + Canonical Manifest            |
|                              |                              |
|                         [Ed25519 Key] (0600)                |
|                              |                              |
|                              v                              |
|                   Detached Signature (.sig)                 |
+-------------------------------------------------------------+
                               |
               Untrusted Distribution Channel
                               |
                               v
+-------------------------------------------------------------+
|                     Edge Robot / Agent                      |
|                                                             |
|  1. Verify Signature against Trusted Public Key             |
|  2. Verify Artifact SHA-256 Digest                          |
|  3. Evaluate Platform Safety Policy                         |
|  4. Safe Quarantine Extraction (Path Traversal Resistant)   |
|  5. Post-Extraction SHA-256 Verification of Files           |
|  6. Stage into Inactive Slot (slot-b)                       |
|  7. Atomic Switch: current -> slot-b                        |
|  8. Preserve slot-a as PREVIOUS (Rollback Candidate)        |
+-------------------------------------------------------------+
```

---

## 2. Threat Analysis & Mitigations

| Threat Scenario | Attack Vector | OpenRobo Mitigation | Residual Risk |
|---|---|---|---|
| **Private Signing Key Compromise** | Attacker gains access to release private key | Keys stored in secure build environment with 0600 permissions. `ReleaseVerifier` enforces immediate key revocation checks via `TrustedReleaseKey.status = "REVOKED"`. | Compromised key can sign artifacts until revocation metadata reaches agent. |
| **Artifact / Manifest Tampering** | Attacker modifies file in transit or host | Any modification to `.tar.gz` violates `manifest.artifact_digest`. Any modification to manifest violates detached Ed25519 signature over canonical JSON. | None; tampered payloads fail closed before extraction. |
| **Path Traversal / Escape** | Archive contains `../`, `C:\`, or absolute paths | `SafeArtifactExtractor.sanitize_path` inspects all TarInfo entries, rejecting `..`, absolute paths, Windows drive letters, UNC paths, and NUL bytes. | None; malicious paths fail closed. |
| **Symlink / Hardlink Attacks** | Symlink targets `/etc/shadow` or sensitive files | `SafeArtifactExtractor` resolves all symlinks relative to target root, rejecting links that point outside the extraction boundary. | None; symlinks constrained to sandbox. |
| **Decompression Bomb / Resource Exhaustion** | Tiny archive decompressing to gigabytes | Enforces strict bounds: `max_archive_bytes` (100MB), `max_file_count` (5000), `max_individual_file_bytes` (50MB), `max_total_extracted_bytes` (200MB). | None; bombs rejected prior to or during streaming. |
| **Secret Leaks in Releases** | Developer accidentally includes `*.key`, `.env`, tokens | `create_deterministic_archive` automatically denies `*.key`, `*.pem`, `.env`, `id_rsa*`, tokens, credentials, and SQLite caches. | Custom unlisted secret filenames; mitigated by workspace hygiene. |
| **Accidental Overwrite of Running Stack** | Staging writes directly over active workspace | Active slot is protected (`prepare_staging_slot` raises `RuntimeError` if active slot targeted). Staging occurs strictly in inactive partition. | None; active stack never touched during staging. |
| **Crash During Switch** | Power loss or reboot during pointer activation | Pointer switch uses atomic replacement (`current.tmp` -> `current`). On crash, partial temp links are ignored/cleaned on startup. | None; filesystem guarantees atomic directory link pointer. |
| **Downgrade / Replay Attacks** | Attacker presents older signed release | Manifest tracks `release_version` and sequence. Operator-authorized rollback to `PREVIOUS` is explicitly separated from arbitrary remote downgrades. | Mitigated in M7.2.2 control-plane deployment state machine. |

---

## 3. Deployment Safety Policy Model (`DeploymentSafetyPolicy`)

OpenRobo rejects universal hardcoded thresholds across heterogeneous robotics platforms. Pre-flight health gates are platform-specific and strictly evidence-backed:
- **Battery Requirements**: Configurable `threshold_percent` and `telemetry_source`.
- **Motion Requirements**: Configurable `required_state` (e.g. `STATIONARY`) and `max_linear_velocity`.
- **E-Stop Requirements**: Configurable `safe_states` (e.g. `["ENGAGED", "ACTIVE"]`).
- **Strict Invariant**: Any `UNKNOWN`, missing, or stale telemetry state strictly returns `(False, "Safety state UNKNOWN; deployment blocked")`.
