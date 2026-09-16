# Security Policy

The OpenRobo project takes the security and integrity of robotics software infrastructure seriously. This document outlines our security policies, supported versions, and procedures for reporting potential vulnerabilities.

---

## Supported Versions

Only the latest release and the current active development branch (`main`) receive security updates and patches.

| Version / Branch | Supported          |
| ---------------- | ------------------ |
| `main`           | :white_check_mark: |
| `< 0.2.0`        | :x:                |

---

## Ingestion & Static Analysis Threat Model

OpenRobo performs automated static metadata extraction on third-party and public robotics repositories. To ensure the safety of developer workstations and server environments, OpenRobo enforces the following threat boundaries:

1. **Zero Untrusted Code Execution**: OpenRobo static ingestion inspecting `package.xml`, `CMakeLists.txt`, and repository manifests **never executes** upstream Python or C++ scripts, setup scripts, or binaries.
2. **Safe XML/Manifest Parsing**: All XML parsing utilizes defused/hardened parsers resistant to XML Entity Expansion (Billion Laughs) and External Entity (XXE) resolution attacks.
3. **SSRF & Network Isolation**: Network requests made by ingestion adapters are restricted to whitelisted public VCS APIs (e.g. GitHub REST/raw content APIs).
4. **Credential Isolation**: OpenRobo tools do not persist, log, or transmit personal API keys or cloud tokens.

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
