# Milestone 5.1 - Generator Trust, Safety & Deployment Hardening Report

**Milestone:** M5.1 - Generator Trust, Safety & Deployment Hardening
**Project:** OpenRobo
**Owner / Maintainer:** Tanishk Singhal
**Date:** September 17, 2026
**Status:** COMPLETED & VERIFIED âœ…

---

## 1. Executive Summary

Milestone 5.1 is a focused, rigorous trust and safety hardening pass on the OpenRobo Workspace Generator (`packages/workspace-gen`). Guided by the foundational principle:

> **NO EVIDENCE â†’ NO INVENTED CONFIGURATION**

The generator now deterministically differentiates:
1. **`VERIFIED_ADAPTER`**: Canonical, tested adapters (Nav2, SLAM Toolbox, ros2_control, Gazebo) registered with exact canonical IDs.
2. **`USER_CONFIGURED`**: Explicit user-supplied hardware joints, frames, topics, or physical dimensions.
3. **`METADATA_DRIVEN`**: Generated strictly from verified registry metadata and ROS package manifests.
4. **`GENERIC_SCAFFOLD`**: Generic `.example` templates emitted with clear manual configuration instructions for unknown or unconfigured hardware.

---

## 2. Hardening Accomplishments by Phase

### Phase 1 & 2: Generation Evidence Model & Adapter Registry
- **Eliminated Substring Matching**: Replaced permissive `"nav2" in id` checks with a deterministic `AdapterRegistry` operating on exact canonical IDs and aliases (`ros-navigation/navigation2`, `nav2`, `ros2_control`, `slam_toolbox`, `gazebo`).
- **False-Positive Immunity**: IDs like `my_nav2_demo`, `custom_gazebo_tools`, and `ros2_control_helper` are rejected by adapters and safely handled as generic scaffolding.
- **Structured Evidence Tracking**: Every component in the plan and lockfile carries a `ComponentEvidence` record (`level`, `source`, `adapter_id`, `adapter_version`, `reason`, `required_manual_steps`).

### Phase 3: ros2_control Safety & Hardware Geometry
- **Removed Hardcoded Guesswork**: Removed all hardcoded wheel joint names (`left_wheel_joint`), wheel separation (`0.287`), and wheel radius (`0.033`).
- **Scaffold Fallback**: If user configuration is absent, the generator emits `ros2_control_params.yaml.example` with clear placeholders and flags required manual configuration steps.
- **Readiness Downgrade**: Unconfigured hardware automatically sets workspace readiness to `BUILD_REQUIRES_CONFIGURATION`.

### Phase 4, 5, 6: Nav2, SLAM Toolbox & Gazebo Hardening
- **Framework Defaults vs Robot Specifics**: Separated safe framework defaults from platform-specific frames and topics.
- **User Overrides**: Supported explicit user configuration of frames (`base`, `odom`, `map`) and topics (`scan`, `odom`).
- **Safe YAML Serialization**: Replaced raw template concatenation with `yaml.safe_dump` across all adapters.

### Phase 7 & 8: package.xml Dependency Correctness & Maintainer Provenance
- **Verified Package Names**: `<exec_depend>` is only emitted for verified ROS packages matching `^[a-z][a-z0-9_]*$`.
- **XML Escaping**: All user-controlled text (stack names, descriptions, maintainer strings) is escaped via `xml.sax.saxutils.escape`.
- **Maintainer Transparency**: Resolved from explicit arguments or `manifest.metadata.maintainer`. If omitted, clearly marked as a placeholder (`unspecified@placeholder.openrobo`).

### Phase 9: Workspace Readiness Model
- Formalized explicit readiness levels:
  - `STATICALLY_VALIDATED`: Static syntax, AST, XML, and YAML structure verified.
  - `BUILD_REQUIRES_CONFIGURATION`: Manual configuration required before build.
  - `BUILD_VERIFIED`: Real Docker/colcon build verified.
  - `RUNTIME_VERIFIED`: Live node runtime execution verified.
- Generator reports `STATICALLY_VALIDATED` honestly, with `docker_build`, `colcon_build`, and `runtime_validation` marked `NOT_EXECUTED`.

### Phase 10 & 11: Docker Least-Privilege & Security Profiles
- **Removed Universal Privileged Mode**: `privileged: true` and `/dev:/dev` volume mounts are completely removed from default compose generation.
- **Explicit Device Passthrough**: Only explicitly declared hardware devices (e.g. `/dev/ttyUSB0`) are mounted in `docker-compose.yml`.

### Phase 12 & 13: Shell Injection Defenses & Safe Serialization
- **Regex Validation**: Validates Debian package names against `^[a-z0-9][a-z0-9+\-.]+$` and pip requirements against `^[a-zA-Z0-9_\-\.><=~!^, ]+$`.
- **Shell Quoting**: Enforces `shlex.quote` on all shell arguments.
- **Adversarial Defenses**: Command separators (`;`, `&&`, `|`), newlines, backticks, and subshells are strictly rejected.

### Phase 15: Lockfile Provenance
- **Structured Fields**: Replaced magic string `"UNKNOWN"` with structured nulls and `"resolution_status": "unresolved"`.
- **Evidence & Readiness Records**: Lockfile (`openrobo.lock.json` v1.1.0) includes complete `generation_evidence` and `workspace_readiness` matrices.

### Phase 17 & 18: Path Security & Static WorkspaceValidator
- **Path Traversal Defenses**: Retained and expanded tests for `..`, Windows drive letters (`C:`), Windows reserved devices (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`), and null bytes.
- **Formal WorkspaceValidator**: Validates package.xml XML syntax, CMakeLists declarations, Python launch ASTs, YAML safe loading, and JSON schemas.

---

## 3. Test Verification Metrics

| Test Suite | Previous (M5) | Hardened (M5.1) | Status |
|---|---|---|---|
| Python Pytest (`packages/workspace-gen`) | 13 | **24** | **100% Passed** |
| Python Pytest (Total Repository) | 78 | **89** | **100% Passed** |
| Frontend Vitest (`apps/web`) | 12 | **12** | **100% Passed** |
| JSON Schema Validation (`scripts/validate_schemas.py`) | 5 | **5** | **100% Passed** |
| Python Code Linting (`ruff`) | 0 errors | **0 errors** | **100% Passed** |
| Frontend ESLint (`next lint`) | 0 errors | **0 errors** | **100% Passed** |
| Frontend Production Build (`next build`) | 6 pages | **6 pages** | **100% Passed** |

---

## 4. Real Build Verification Status

- **Docker Version Check**: Docker CLI v29.7.2 present; Docker Desktop daemon offline on host.
- **Recorded Status**: `NOT EXECUTED â€” Docker daemon unavailable`.

---

## 5. Git Commit Provenance

- **Feature Branch**: `feature/m5.1-generator-hardening`
- **Feature PR Head SHA**: `13681381683ad4a6a70f2c321830a49d4d6531d6`
- **Main Merge Commit SHA**: `4d47992e1c4c6d1d2184e7dcc014b28b3f85a91e`
