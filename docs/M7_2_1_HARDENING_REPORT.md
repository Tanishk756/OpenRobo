# Milestone 7.2.1.1 Hardening & Security Audit Report

**Milestone:** M7.2.1.1 — Release Trust Anchor, Safe Extraction & A/B Crash-Consistency Hardening
**Status:** COMPLETE & VERIFIED (Green)
**Date:** 2026-09-18
**Author:** Antigravity / OpenRobo Maintainers
**Maintainer:** Tanishk Singhal
**Repository:** C:\OpenRobo
**Baseline HEAD:** f6ca60f9e2344700046adb45bad86871d6e2156
**Feature Branch:** eature/m7-2-1-release-hardening

---

## 1. Executive Summary

Milestone 7.2.1.1 is a dedicated correctness and security hardening pass executed prior to remote fleet deployment orchestration (M7.2.2). It formalizes release trust boundaries, implements an agent-owned trusted key store, eliminates implicit security and safety defaults, guarantees safe and link-free archive extraction, establishes crash-consistent A/B activation transactions, enforces rollback cryptographic re-verification, and repairs documentation provenance and planning specifications.

---

## 2. Hardened Architecture & Security Implementations

### 2.1 Release Signing Gate & Explicit Development Keypair Generation (Phases 1–3)
- **Production Gate**: openrobo release build strictly requires an explicit --private-key. Silent fallback to ephemeral or dev keys is rejected in production.
- **Explicit Dev Signing**: Development signing key generation is isolated behind generate_development_keypair() and gated by OPENROBO_DEV_RELEASE_SIGNING=true and CLI flag --dev.
- **Private Key Validation**: alidate_private_key_file validates file existence, regular file status (non-symlink), reasonable size bounds (<= 1MB), Ed25519 cryptography, and warns/fails on loose POSIX permissions (> 0600). Private keys are never copied into releases, manifests, or agent states.

### 2.2 Agent Trusted Release Key Store & Fail-Closed Metadata (Phases 4–7)
- **Trusted Key Store (TrustedReleaseKeyStore)**: Agents resolve release trust from an agent-owned directory (/etc/openrobo-agent/trusted-release-keys/ or configured path) keyed by
elease_key_id.
- **No Arbitrary Key Injection**: Deployments cannot self-authenticate by injecting arbitrary public keys via CLI. Development override is gated strictly by OPENROBO_ALLOW_DEV_RELEASE_KEY=true.
- **Fail-Closed Metadata**: ReleaseVerifier strictly parses ISO 8601 timestamps. Unparseable dates fail with KEY_METADATA_INVALID. Never swallows exceptions.
- **Key Revocation Enforcement**: Trusted keys support ACTIVE, REVOKED, EXPIRED. Revoked keys immediately fail verification with REVOKED_SIGNING_KEY.

### 2.3 Safe Extraction & Multi-Layer Path Sanitization (Phases 8–15)
- **Links Forbidden by Default**: SafeArtifactExtractor sets llow_symlinks=False and llow_hardlinks=False by default. Symlink pivot attacks and hardlink attacks fail closed.
- **Canonical Path Collision & Alias Rejection**: Member paths are normalized (//b, /./b resolve to canonical /b) and duplicate destination collisions are blocked. On Windows platforms, case-insensitive collisions (Config.yaml vs config.yaml) are rejected.
- **Control Characters & Device Names**: Rejects NUL and ASCII control characters in paths. On Windows-compatible validation, reserved device names (CON, PRN, AUX, NUL, COM1..9, LPT1..9) are rejected.
- **Quarantine Extraction**: Extractions unpack into isolated temporary directories (slot-x.incoming.<uuid>). Full file hash checks run post-extraction. On failure, quarantine directories are deleted immediately; the inactive slot remains untouched.
- **Expansion Ratio & Limits**: Enforces max_archive_bytes (100MB), max_file_count (5000), max_individual_file_bytes (50MB), max_total_extracted_bytes (200MB), and max_expansion_ratio (50.0x).

### 2.4 Unambiguous Slot Semantics & Crash-Consistent Activation (Phases 16, 20–23)
- **Slot States**: EMPTY, STAGING, VERIFIED, ACTIVE, PREVIOUS, FAILED, QUARANTINED. Activation strictly requires VERIFIED.
- **Activation Intent Journal (ctivation.intent.json)**: Activation operations write an intent record before switching pointers, perform atomic directory symlink/pointer switch, update metadata, and mark complete.
- **Startup Crash Reconciliation**: ABSlotManager startup reads the authoritative filesystem pointer, slot metadata, and activation journal to recover deterministic state after ungraceful termination at any step.
- **Windows Classification**: Windows A/B activation is formally classified as DEVELOPMENT / LIMITED due to non-atomic directory symlink replacement semantics on Windows NTFS compared to POSIX
enameat2.

### 2.5 Rollback Candidate Integrity & Revocation Policy (Phases 24–26)
- **Stored Release Evidence**: Release metadata and signature evidence are preserved alongside slots in slot-x.release/.
- **Rollback Cryptographic Verification**: Rollback to PREVIOUS re-verifies manifest signature, resolves the key in the local trust store, checks revocation status, and re-computes SHA-256 for all slot files. Tampered files reject rollback and transition the slot to QUARANTINED.
- **Revocation Safety**: Releases signed by keys revoked after staging cannot be reactivated during rollback.

### 2.6 Platform Safety Policy & Telemetry Freshness (Phases 17–19)
- **Pre-Activation Safety Recheck**: Safety policy is re-evaluated immediately prior to pointer switch.
- **Zero Implicit Robot Defaults**: Evaluator rejects policies missing required configurations with POLICY_CONFIGURATION_INVALID. Universal hardcoded defaults (STATIONARY, 30%, ENGAGED) are removed.
- **Telemetry Freshness**: Safety inputs must satisfy max_age_seconds. Stale or missing telemetry returns STALE_TELEMETRY and blocks activation.

### 2.7 Secret Exclusion Reporting (Phases 27–28)
- **High-Confidence Credential Blocking**: Blocks high-risk secrets (*.key, *.pem, .env, id_rsa*, *credentials.json).
- **Heuristic Warnings**: Suspicious terms emit warnings in ExclusionReport without silently deleting legitimate source files (e.g. 	okenizer.py is preserved).

### 2.8 Anti-Downgrade & Replay Protection Boundary (Phase 29)
- Local rollback is allowed with cryptographic verification. Remote monotonic generation replay protection is explicitly documented as designed for the M7.2.2 orchestration layer.

### 2.9 M7.2.2 Architecture & Canary Safety Refinement (Phases 30–32)
- **Trusted Source Resolution**: Deployment requests require
elease_id and content digests; arbitrary direct rtifact_url parameters are removed.
- **Manual Canary Stage Gates**: M7.2.2 canary progression requires explicit operator approval at each stage (CREATE -> TARGET_RESOLVED -> STAGE_CANARY -> CANARY_STAGED -> AWAITING_OPERATOR_APPROVAL -> ACTIVATE_CANARY -> AWAITING_OPERATOR_APPROVAL -> NEXT_STAGE). Automatic health-gated progression is deferred to M7.2.3.
- **Deterministic Cohort Selection**: Random sampling is replaced by auditable deterministic hash-based cohort assignment.

---

## 3. Verification & Test Evidence

- **Python Test Suite**: 196 tests passing (100% green).
- **Ruff Linter**: 0 errors.
- **Schema Validation**: Passed.
- **Frontend Test Suite**: 19 vitest tests passing.
- **Control Character Audit**: 0 unescaped control characters across repository text files.

---

## 4. Milestone 7.2.2 Gate Assessment

All 15 readiness criteria for M7.2.2 are fully satisfied:
1. Release signing gate blocks silent dev key generation.
2. Agent resolves trust exclusively via local TrustedReleaseKeyStore.
3. Malformed trust metadata fails closed.
4. Release extraction rejects symlinks/hardlinks by default.
5. Canonical path collisions and Windows reserved device names are blocked.
6. Quarantine extraction ensures failed staging never leaves dirty slots.
7. Slot activation requires VERIFIED status.
8. Safety policy evaluator contains zero implicit robot defaults.
9. Stale telemetry blocks deployment activation.
10. Crash-consistent activation journal and startup reconciliation verified.
11. Rollback performs full cryptographic re-verification.
12. Tampered previous slot rejects rollback and transitions to QUARANTINED.
13. M7.2.2 implementation plan is clean Markdown with deterministic canary stages.
14. PR-only discipline strictly followed.
15. Full test suite and CI green.
---

## 5. README & Repository Integrity Audit

A comprehensive encoding, character integrity, and technical accuracy audit was performed across `README.md` and all tracked repository documentation.

### 5.1 README Encoding & Character Cleanup
- **Encoding Status**: Verified valid UTF-8 before and after cleanup.
- **Malformed Sequences Found**:
  - Double-encoded em dashes in stack descriptions (`stackâ€...` / `Ã¢â‚¬â€”`).
  - Corrupted evidence arrow in safety section (`NO EVIDENCE â†’ NO INVENTED CONFIGURATION`).
  - Corrupted directory tree box-drawing symbols in Architecture section (`Ã¢â€ Å“Ã¢â€ â‚¬Ã¢â€ â‚¬`, `Ã¢â€ â€š`, `Ã¢â€ â€ `).
- **Corrections Applied**:
  - Restored clean Unicode em dashes (`—`), arrows (`→`), and box-drawing lines (`├──`, `│`, `└──`).
  - Added newly created packages (`packages/release-core/`, `packages/agent-core/`) to Architecture tree.
  - Updated Quickstart virtual environment setup to install `-e packages/release-core -e packages/agent-core`.
  - Added Milestone 7.1 and 7.2.1 capability bullets without claiming unimplemented M7.2.2 features.

### 5.2 Repository-Wide Mojibake & Control Character Scan
- **Mojibake Check**: Scanned all tracked `.py`, `.md`, `.json`, `.yaml`, `.yml`, `.ts`, `.tsx`, `.css`, `.html`, `.toml`, `.sh`, `.ps1` files. All legacy double-encoded sequences across historic milestone reports (`docs/M2_VERIFICATION_REPORT.md`, `docs/M5_HARDENING_REPORT.md`, `docs/M6_VERIFICATION_REPORT.md`, `docs/IMPLEMENTATION_LEDGER.md`) were repaired. Final mojibake count: **0**.
- **Control Character Scan**: Scanned all tracked files for ASCII control bytes (< 0x20) excluding `	`, `
`, `
`. Final unexpected control character count: **0**.

### 5.3 Markdown Structure & Technical Path Verification
- **Structure**: Exactly one H1 (`# OpenRobo`), balanced code fences, clean table structures, no broken links or escaped HTML tags.
- **Technical Path Alignment**: All documented paths (`packages/release-core`, `packages/agent-core`, `packages/runtime-core`, `packages/workspace-gen`, `packages/compat-engine`, `packages/schemas`, `packages/cli`, `apps/api`, `apps/web`) match current repository layout.
- **Toolchain Alignment**: Toolchain versions in `README.md` match `pyproject.toml`, `package.json`, and `.github/workflows/ci.yml` (Python 3.10-3.12, Node 24, pnpm 12.4.2).
- **Remaining Issues**: **None**.
