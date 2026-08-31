# Security

Security is a first-class requirement.

Initial controls:
- dependency scanning
- secret detection
- input validation
- repository URL validation
- sandboxing for untrusted build/test workloads
- least-privilege service accounts
- signed/reproducible artifacts where practical
- audit logs
- SBOM support
- rate limiting
- secure defaults

Untrusted robotics code must never execute directly inside the main application process.
