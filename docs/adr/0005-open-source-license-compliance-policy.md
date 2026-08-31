# ADR-0005: Open-Source License and Compliance Policy

- **Status**: Accepted
- **Date**: 2026-08-31
- **Authors**: OpenRobo Architecture Team

## Context

OpenRobo acts as a global index and metadata platform for open-source robotics projects.
To maintain trust across the community and legal integrity:
1. Upstream projects retain 100% of their copyright, ownership, and original licensing terms.
2. OpenRobo metadata must store standardized SPDX identifiers.
3. OpenRobo must never remove copyright notices or imply upstream endorsement.
4. OpenRobo's own codebase license must be selected cleanly to foster broad open-source adoption.

## Decision

1. **SPDX Standard**: All resource manifests, backend data models, and API responses must include `spdx_identifier` (e.g., `Apache-2.0`, `MIT`, `GPL-3.0-only`, `BSD-3-Clause`).
2. **Upstream Attribution**: Web UI and API outputs will clearly display `Upstream Maintainer`, `Original Repository`, and link to canonical source host.
3. **No Code Mirroring**: OpenRobo indexers extract metadata and manifest files (`package.xml`, `README.md`, `LICENSE`, `pyproject.toml`) without mirroring full upstream source code unless explicitly authorized or for temporary ephemeral inspection.
4. **License Compatibility Warnings**: The Compatibility Engine flags potential copyleft vs. permissive license mixing when composing multi-package stacks (e.g., combining GPL-3.0 components with proprietary or incompatible permissive modules).
5. **OpenRobo Core License Decision**: OpenRobo adopts **Apache-2.0** for its core codebase (see ADR-0006), maximizing global open-source adoption, community contributions, and explicit patent protection, while indexed projects remain under their respective original licenses.

## Consequences

### Positive
- Strict legal clarity and compliance with open-source norms.
- Transparent license risk warnings for engineers composing robotics stacks.
- Clear Apache-2.0 licensing for OpenRobo core repository.

### Negative / Trade-offs
- License detection requires handling custom or non-standard license files, falling back to `NOASSERTION` or `UNKNOWN` when SPDX cannot be automatically determined.
