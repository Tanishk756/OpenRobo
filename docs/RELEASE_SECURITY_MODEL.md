# OpenRobo Release Security Model (Milestone 7.2.1.1 Hardened)

**Document:** Release Security Model & Cryptographic Threat Analysis
**Version:** 1.1.0 (Milestone 7.2.1.1 Hardening Pass)
**Maintainer:** Tanishk Singhal
**Classification:** Open Source Security Architecture & Threat Model

---

## 1. Overview & Trust Hierarchy

OpenRobo OTA deployments establish an explicit cryptographic chain of trust from the release authoring environment to edge robotics hardware:

`
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
|  1. Resolve Trusted Key from Local Store (by release_key_id)|
|  2. Verify Key Status (ACTIVE vs REVOKED/EXPIRED)           |
|  3. Verify Ed25519 Signature over Canonical Manifest        |
|  4. Verify Artifact SHA-256 Digest against Manifest         |
|  5. Fresh Quarantine Extraction (slot-b.incoming.<uuid>)     |
|     - Links Forbidden by Default (allow_symlinks=False)     |
|     - Canonical Alias & Reserved Device Name Rejection       |
|     - Control Character Rejection                           |
|     - Max Expansion Ratio & Byte Limits                     |
|  6. Post-Extraction SHA-256 Verification of Extracted Files |
|  7. Atomic Rename to Inactive Slot -> Mark VERIFIED         |
|  8. Fresh Safety Re-check (Telemetry Freshness & No Defaults|
|  9. Crash-Consistent Activation Journal (activation.intent) |
| 10. Atomic Pointer Switch: current -> slot-b                |
| 11. Complete Activation Journal -> slot-b ACTIVE, slot-a PREV|
+-------------------------------------------------------------+
`

---

## 2. Threat Analysis & Mitigations

| Threat Scenario | Attack Vector | OpenRobo Mitigation | Residual Risk |
|---|---|---|---|
| **Private Signing Key Compromise** | Attacker gains access to release private key | Keys stored in secure build environment with 0600 permissions. ReleaseVerifier enforces immediate key revocation checks via TrustedReleaseKeyStore / KeyStatus.REVOKED. | Compromised key can sign artifacts until revocation metadata reaches agent. |
| **Silent Dev Signing in Production** | Unconfigured CI/build produces unverified dev keys | openrobo release build requires explicit --private-key. Key generation strictly requires OPENROBO_DEV_RELEASE_SIGNING=true + --dev flag. | None; production build fails closed without signing authority. |
| **Arbitrary Public Key Injection** | Deployment supplies its own untrusted public key | Agent resolves trusted keys strictly from agent-owned TrustedReleaseKeyStore (/etc/openrobo-agent/trusted-release-keys/) by
elease_key_id. Development override requires explicit OPENROBO_ALLOW_DEV_RELEASE_KEY=true. | None; untrusted public keys cannot self-authenticate. |
| **Malformed Trust Metadata** | Key has unparseable expiration or malformed timestamps | ReleaseVerifier strictly parses ISO 8601 timestamps and fails closed with KEY_METADATA_INVALID. Never swallows exceptions. | None; malformed metadata fails closed. |
| **Artifact / Manifest Tampering** | Attacker modifies file in transit or host | Any modification to .tar.gz violates manifest.artifact_digest. Any modification to manifest violates detached Ed25519 signature over canonical JSON. | None; tampered payloads fail closed before extraction. |
| **Path Traversal / Escape** | Archive contains ../, C:\, or absolute paths | SafeArtifactExtractor.sanitize_path inspects all TarInfo entries, rejecting .., absolute paths, Windows drive letters, UNC paths, and NUL/control bytes. | None; malicious paths fail closed. |
| **Symlink / Hardlink Attacks & Pivots** | Archive creates symlink to /etc and writes through it | Links forbidden by default (llow_symlinks=False, llow_hardlinks=False). Multi-entry pivot chains rejected. | Links require explicit future manifest capability and security review. |
| **Canonical Path Collisions** | Archive uses aliases (/b and /./b or //b or case collisions) | Archive paths canonicalized before duplicate tracking; case-insensitive collisions rejected on Windows platforms. | None; alias collisions fail closed. |
| **Control Characters & Device Names** | Archive targets CON, NUL, AUX, or control chars | Extractor rejects Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9) and non-printable ASCII. | None; malformed member names rejected. |
| **Decompression Bomb / Resource Exhaustion** | Tiny archive decompressing to gigabytes | Enforces strict bounds: max_archive_bytes (100MB), max_file_count (5000), max_individual_file_bytes (50MB), max_total_extracted_bytes (200MB), and max_expansion_ratio (50.0x). | None; bombs rejected prior to or during streaming. |
| **Partial / Dirty Slot on Failure** | Failed extraction leaves broken files in candidate slot | Extraction occurs in isolated temporary quarantine directory (slot-x.incoming.<uuid>). Deleted immediately on failure. Target slot remains untouched. | None; failed staging cannot leave usable candidate. |
| **Secret Leaks in Releases** | Developer accidentally includes *.key, .env, tokens | create_deterministic_archive denies high-confidence credential files (*.key, *.pem, .env, id_rsa*, *credentials.json) and warns on suspicious patterns. Emits ExclusionReport. Legitimate files like 	okenizer.py are preserved. | Custom unlisted secret filenames; mitigated by exclusion reporting. |
| **Accidental Overwrite of Running Stack** | Staging writes directly over active workspace | Active slot is protected (prepare_staging_slot raises RuntimeError if active slot targeted). Staging occurs strictly in inactive partition. | None; active stack never touched during staging. |
| **Crash During Pointer Switch** | Power loss between pointer flip and metadata updates | Atomic activation intent journal (ctivation.intent.json) records transaction state. Startup reconciliation recovers deterministic state. Filesystem pointer is authoritative. | None; crash recovery reconciles pointer and slot states. |
| **Tampered Rollback Candidate** | Attacker or corrupted disk mutates inactive slot files | Rollback verifies previous slot cryptographic evidence (manifest signature, active trust key status, and file-by-file SHA-256) before switching pointer. | Tampered previous slot is quarantined and rollback blocked. |
| **Revoked Key Rollback** | Attempting rollback to a release signed by a revoked key | Rollback checks key status in local trust store; rollback to revoked key is blocked by default. | None; revoked software cannot reactivate. |
| **Stale Telemetry Pre-Flight Bypass** | Staging safety check passed earlier, but robot is now moving | Pre-flight safety re-evaluated immediately before pointer switch. Safety evidence enforces max_age_seconds. Stale telemetry blocks activation (STALE_TELEMETRY). | None; stale telemetry fails closed. |
| **Implicit Safety Thresholds** | Platform assumes universal stationary / battery defaults | Evaluator requires explicit policy configuration. Missing required configurations return POLICY_CONFIGURATION_INVALID. Zero implicit defaults. | None; platform-specific thresholds required. |
| **Downgrade / Replay Attacks** | Attacker presents older signed release | Manifest tracks
elease_version and sequence. Local rollback requires verified PREVIOUS evidence. Remote monotonic generation replay protection is designed for M7.2.2 control plane. | Remote downgrade replay protection enforced in M7.2.2. |

---

## 3. Deployment Safety Policy Model (DeploymentSafetyPolicy)

OpenRobo rejects universal hardcoded thresholds across heterogeneous robotics platforms. Pre-flight health gates are platform-specific, strictly configured, and evidence-backed:
- **Battery Requirements**: Configurable 	hreshold_percent, 	elemetry_source, and optional max_age_seconds.
- **Motion Requirements**: Configurable
equired_state and max_linear_velocity. Fails closed if enabled without parameters.
- **E-Stop Requirements**: Configurable safe_states list. Fails closed if empty.
- **Telemetry Freshness**: Evidence older than max_age_seconds is rejected as STALE_TELEMETRY.
- **Strict Invariant**: Any UNKNOWN, missing, or stale telemetry state strictly blocks deployment.
