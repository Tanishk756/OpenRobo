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
