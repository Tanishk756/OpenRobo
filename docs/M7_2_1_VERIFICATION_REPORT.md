# OpenRobo Milestone 7.2.1 — Verification Report

**Date:** September 18, 2026  
**Status:** VERIFIED & EMPIRICALLY TESTED  
**Branch:** `feature/m7-2-1-signed-artifacts`  
**Milestone:** M7.2.1 — Signed Release Artifacts, Safe Extraction & Local A/B Deployment Foundation  
**Maintainer:** Tanishk Singhal  

---

## 1. Executive Summary & Deliverables

Milestone 7.2.1 establishes the cryptographic packaging, verification, safe extraction, and local A/B deployment partition foundation for OpenRobo OTA updates.

Key deliverables verified:
- **Canonical Release Manifest (`ReleaseManifest`)**: Bit-for-bit deterministic canonical JSON serialization (`canonical_manifest_bytes`) guaranteeing identical SHA-256 digests across equivalent manifests.
- **Ed25519 Detached Release Signatures**: `ReleaseSigner` produces detached base64 signatures; `ReleaseVerifier` validates signatures, public key trust, expiration, and revocation.
- **Deterministic Archive Builder (`create_deterministic_archive`)**: Generates reproducible `.tar.gz` archives with normalized mtime (0), owner metadata (uid=0, gid=0), permissions (0o755/0o644), sorted paths, and strict automatic secret/private key filtering.
- **Safe Artifact Extractor (`SafeArtifactExtractor`)**: Hardened quarantine extraction rejecting path traversal (`../`, `..\`, absolute POSIX paths, Windows drive paths, UNC paths, duplicate paths, NUL bytes), symlink/hardlink escapes, device files, and decompression resource exhaustion limits.
- **Post-Extraction Integrity Verification**: Recalculates individual file SHA-256 hashes and sizes post-extraction, confirming exact match against manifest.
- **Platform-Specific Pre-Flight Policy (`DeploymentSafetyPolicy`)**: Evaluates battery, motion, and e-stop state constraints, strictly enforcing `on_unknown_state: "BLOCK_DEPLOYMENT"` (unknown telemetry blocks deployment).
- **Dual Partition A/B Slot Manager (`ABSlotManager`)**: Manages `slot-a`, `slot-b`, and atomic `current` pointer switching, protecting active slots from staging overwrites.
- **Mechanical Rollback Primitive (`rollback_to_previous`)**: Reverts active pointer to the preserved `PREVIOUS` slot without data loss, marking faulted slots `FAILED`.
- **Real Filesystem Acceptance**: Full end-to-end acceptance test proving `v1 -> Stage -> Activate -> v2 -> Stage -> Activate -> Rollback to v1` across live disk directories.

---

## 2. Test Execution & Evidence

### Test Summary
- **Python Tests**: **189 passed** (100% passing across 36 test files, +25 new tests in M7.2.1).
- **Frontend Tests**: **19 passed** (100% passing across 6 test suites).
- **Schema Validation**: 100% valid Draft 2020-12 schemas.
- **Linters**: Ruff & ESLint clean (zero warnings/errors).
- **Next.js Production Build**: Optimized static export succeeded.

### Test Coverage Breakdown for M7.2.1
| Test Module | Coverage Dimension | Result |
|---|---|---|
| `packages/release-core/tests/test_manifest.py` | Canonical JSON determinism, manifest digest, workspace digest | **PASSED** |
| `packages/release-core/tests/test_signing.py` | Ed25519 signing/verification, key trust, expiration, revocation, manifest tampering | **PASSED** |
| `packages/release-core/tests/test_archive.py` | Deterministic build stability, automated secret/key exclusion | **PASSED** |
| `packages/release-core/tests/test_extraction.py` | Traversal rejection (`../`, `..\`, absolute, drive, UNC, symlinks, bombs, hash mismatch) | **PASSED** |
| `packages/release-core/tests/test_policy.py` | Safety policy threshold evaluation, unknown state blocking | **PASSED** |
| `packages/agent-core/tests/test_slots.py` | A/B slot lifecycle, active protection, atomic activation, previous slot preservation | **PASSED** |
| `packages/cli/tests/test_release_cli.py` | `openrobo release build/verify` and `openrobo agent deployment slots` CLI runner | **PASSED** |
| `tests/integration/test_local_ota_deployment.py` | Real filesystem v1 -> v2 -> rollback lifecycle acceptance | **PASSED** |

---

## 3. Trust Boundaries & Non-Negotiable Invariants

1. **No Unverified Staging**: An edge agent will never extract an archive unless its detached Ed25519 signature verifies against a trusted public key and its SHA-256 matches the manifest.
2. **No Secret Packaging**: The release packager automatically denies `*.key`, `*.pem`, `.env`, tokens, credentials, and caches.
3. **No In-Place Overwrites**: The active slot is read-only and protected; staging occurs strictly in the inactive partition.
4. **Previous Slot Preservation**: Activating a new slot marks the previous slot as `PREVIOUS` without deleting files, maintaining a verified rollback candidate.
5. **Unknown is Not Safe**: If telemetry for any enabled safety check is missing, stale, or unrecognized, the safety evaluation returns `UNKNOWN` and deployment is blocked.
