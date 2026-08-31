# ADR-0003: Compatibility Engine and Evidence Model

- **Status**: Proposed
- **Date**: 2026-08-31
- **Authors**: OpenRobo Architecture Team

## Context

Robotics projects frequently fail during integration due to hidden incompatibilities between OS distributions (e.g., Ubuntu 22.04 vs 24.04), CPU architectures (x86_64 vs ARM64), ROS versions (Humble vs Jazzy vs Noetic), driver interfaces, or middleware protocols.

OpenRobo requires an explainable compatibility engine that evaluates combinations of software, hardware, and runtime constraints.

Furthermore, OpenRobo must never present unverified guesses as verified facts.

## Decision

1. **Compatibility Status Model**:
   - `COMPATIBLE`: All version, platform, and interface constraints are verified or explicitly matching.
   - `CONDITIONAL`: Compatible subject to specific flags, hardware options, or non-tested transitive dependencies.
   - `INCOMPATIBLE`: Explicit constraint violation (e.g., ROS 1 package on ROS 2 Jazzy, or missing ARM64 binary/build support).
   - `UNKNOWN`: Insufficient metadata or evidence to determine compatibility.

2. **Evidence Model**:
   Every compatibility claim must attach an `evidence` object with one of the following levels:
   - `UPSTREAM_DECLARED`: Stated in package manifest or documentation by upstream maintainers.
   - `AUTOMATICALLY_DETECTED`: Extracted via AST/manifest parsing (e.g., `package.xml`, `CMakeLists.txt`).
   - `CI_VERIFIED`: Built or unit-tested in automated CI pipelines.
   - `INTEGRATION_TESTED`: Empirically verified in real or simulated hardware integrations.
   - `COMMUNITY_REPORTED`: Submitted by users with environment details.
   - `INFERRED`: Rule-based deduction based on baseline compatibility heuristics.

3. **Rule & Graph Reasoning Engine**:
   Implemented as an extensible Python evaluation pipeline (`packages/compat-engine`). The engine accepts target environment constraints and traverses the resource dependency DAG (Directed Acyclic Graph), aggregating evaluation rules and returning explicit human-readable explanations.

## Consequences

### Positive
- Users receive transparent, explainable compatibility breakdowns.
- Inferred or unverified compatibilities are explicitly labeled as `INFERRED` or `UNKNOWN`, building user trust.
- Rule engine is standalone and runnable both in API backend and CLI.

### Negative / Trade-offs
- Graph traversal logic requires strict cycle detection and performance optimization for deeply nested dependencies.
