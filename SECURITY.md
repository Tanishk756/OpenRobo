# Security Policy

The OpenRobo project takes the security and integrity of robotics software infrastructure seriously. This document outlines our security policies, supported versions, and procedures for reporting potential vulnerabilities.

---

## Supported Versions

Only the latest release and the current active development branch (`main`) receive security updates and patches.

| Version / Branch | Supported          |
| ---------------- | ------------------ |
| `main`           | :white_check_mark: |
| `0.5.x`          | :white_check_mark: |
| `< 0.5.0`        | :x:                |

---

## Security Model & Hardening Safeguards

OpenRobo enforces strict security controls across both metadata ingestion and workspace synthesis:

### 1. Ingestion & Static Analysis Threat Model
- **Zero Untrusted Code Execution**: Static repository ingestion inspecting `package.xml`, `CMakeLists.txt`, and repository manifests **never executes** upstream Python or C++ scripts, setup scripts, or binaries.
- **Safe XML/Manifest Parsing**: All XML parsing utilizes hardened parsers resistant to XML Entity Expansion (Billion Laughs) and External Entity (XXE) resolution attacks.
- **SSRF & Network Isolation**: Network requests made by ingestion adapters are restricted to approved VCS APIs (e.g. GitHub REST/raw content APIs).
- **Credential Isolation**: OpenRobo tools do not persist, log, or transmit personal API keys or cloud tokens.

### 2. Workspace Generator & Deployment Hardening (Milestone 5.1)
- **Least-Privilege Docker Profiles**: Generated Docker Compose configurations do NOT enable `privileged: true` or mount unrestricted `/dev:/dev` by default. Container profiles default to least privilege and require explicit device passthrough (e.g. `/dev/ttyUSB0`) only when configured.
- **Shell & PowerShell Command Injection Defenses**: All generated provisioning scripts (`install_dependencies.sh`, `rosdep-install.sh`, `install_dependencies.ps1`) strictly validate Debian/APT package names and Python pip requirements against canonical regexes, rejecting newline injections, command separators (`;`, `&&`, `|`), subshell executions (`` ` ``, `$()`), and arbitrary URLs. Safe quoting (`shlex.quote`) is universally enforced.
- **XML & YAML Safe Serialization**: User-controlled inputs (stack names, descriptions, maintainer details) are XML-escaped via `xml.sax.saxutils.escape` before inclusion in `package.xml`, and YAML configs are serialized using `yaml.safe_dump` rather than raw string concatenation.
- **Path Traversal & Archive Extraction Defenses**: Generated relative file paths and ZIP archive entries reject directory traversal (`..`, `../`), Windows drive letters (`C:`), Windows reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`, `LPT1-9`), and null bytes.
- **Evidence-Backed Generation**: Every generated component parameter and launch snippet is tagged with an explicit confidence level (`VERIFIED_ADAPTER`, `USER_CONFIGURED`, `METADATA_DRIVEN`, or `GENERIC_SCAFFOLD`). The generator never invents hardware dimensions or joint mappings without user input.

---

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

If you discover an exploitable security vulnerability, flaw in static ingestion security, or API authorization defect:

1. Use **[GitHub Private Vulnerability Reporting](https://github.com/Tanishk756/OpenRobo/security/advisories/new)** to submit a confidential security advisory directly to the project maintainers.
2. Provide a clear proof-of-concept (PoC), reproduction steps, affected versions, and potential impact assessment.

### Response Process
- Maintainers will acknowledge receipt of the advisory within **48 hours**.
- We will provide an assessment and work on a fix in a private security fork.
- Once a patched release is ready, a coordinated security advisory and credit will be published.
## Runtime Execution & Environment Security (M6.1)

OpenRobo enforces strict security controls on local process and container execution:
- **Environment Allowlist**: Only approved environment variables (`ROS_DISTRO`, `ROS_DOMAIN_ID`, `RMW_IMPLEMENTATION`, `AMENT_PREFIX_PATH`, `PATH`) are passed to child processes. Potentially hazardous variables (`LD_PRELOAD`, `PYTHONPATH` overrides, shell injection strings) are rejected.
- **Filesystem Sandboxing**: Workspace build verification and rosbag telemetry reading enforce canonical path boundary checks to prevent directory traversal and symlink escapes.
- **Process Ownership**: All spawned ROS processes and Connection Inspector executions are tracked by PID and terminate cleanly with parent runtime sessions.

### 3. Edge Agent Identity, mTLS & Fleet Management (Milestone 7.1.1)
- **Zero Remote Arbitrary Execution**: The agent only supports a strict read-oriented operations enum (`PING`, `GET_AGENT_INFO`, `GET_RUNTIME_STATUS`, `GET_ROS_ENVIRONMENT`, `GET_ROS_GRAPH`, `GET_RUNTIME_DIAGNOSTICS`, `GET_CONNECTION_INSPECTOR_STATUS`, `GET_SIMULATOR_STATUS`). Remote execution primitives (`SHELL`, `EXEC`, `RUN_SCRIPT`) are explicitly prohibited.
- **Cryptographic Device PKI**: Device identity root is `device_id` (UUIDv4) + locally generated private key (`0600` permissions) + signed X.509 certificate.
- **mTLS & Trusted Reverse Proxy Boundaries**: Agent transport presents genuine TLS client certificates via Python `ssl.SSLContext`. Proxy identity headers are accepted strictly from configured trusted proxy subnets.
- **Single-Use Enrollment Tokens & Anti-Race**: High-entropy tokens stored as SHA-256 hashes with atomic SQL consumption checking `is_used=false AND expires_at > now`.
- **Replay Protection & Device Isolation**: Sliding-window ±60s clock skew check and bounded in-memory deduplication store. Cross-device writes are blocked with `403 Forbidden`.

### Release Artifact & OTA Deployment Security (M7.2.1)
1. **Ed25519 Detached Signing**: Every release manifest is canonicalized to deterministic JSON and digitally signed. Agents strictly require a verified signature from a trusted, unexpired, unrevoked public key prior to staging.
2. **Safe Extraction Sandbox**: `SafeArtifactExtractor` rigorously rejects `../`, absolute paths, Windows drive paths, UNC paths, symlink escapes, and archive bombs.
3. **Dual A/B Partition Isolation**: The active workspace slot is protected from in-place overwrites. Staging occurs in the inactive partition, followed by atomic pointer replacement and mechanical rollback capability.
