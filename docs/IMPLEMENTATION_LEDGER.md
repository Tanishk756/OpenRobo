# OpenRobo Implementation Ledger

This ledger is the single source of truth for architectural requirements, validation evidence, known limitations, and next actions across all milestones of the OpenRobo platform.

---

## Milestone 0 — Foundation & Repository Baseline

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M0-01** | Canonical Schemas | `VERIFIED` | Draft 2020-12 JSON Schemas for resources, graphs, stacks | `scripts/validate_schemas.py` | `schemas/*.schema.json` | None | Maintain backward compatibility |
| **REQ-M0-02** | Python Schema Package | `VERIFIED` | `openrobo-schemas` validation package with `jsonschema` | `tests/` in package | `packages/schemas-py/` | None | Monorepo standard |
| **REQ-M0-03** | Monorepo Architecture | `VERIFIED` | pnpm workspace + Python virtual env | Root CI workflows | `pnpm-workspace.yaml`, `pyproject.toml` | None | Green baseline |

---

## Milestone 1 — Registry Engine & Resource Discovery

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M1-01** | Resource Registry API | `VERIFIED` | Async CRUD, pagination, filtering, SQLAlchemy models | `apps/api/tests/test_resources.py` | `apps/api/routers/resources.py` | Seed dataset limited to initial items | Ingest real-world packages |
| **REQ-M1-02** | Resource Explorer UI | `VERIFIED` | High-density dark mode UI with drawers & badges | `apps/web/tests/unit/resources.test.tsx` | `apps/web/app/resources/` | Client-side search for basic filters | Deep search integrated in M2 |
| **REQ-M1-03** | Static Repository Ingestion | `VERIFIED` | Safe non-executing GitHub package.xml parser | `apps/api/tests/test_ingestion.py` | `apps/api/services/ingestion/` | Unauthenticated rate limit 60 req/hr | Optional token support |

---

## Milestone 2 — Search Engine & Advanced Taxonomy Indexing

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M2-01** | Full-Text & Fuzzy Search | `VERIFIED` | PostgreSQL tsvector + GIN + pg_trgm similarity | `apps/api/tests/test_search.py` | `apps/api/services/search/` | SQLite fallback uses tokenized python ranking | Production Postgres GIN recommended |
| **REQ-M2-02** | Dynamic Faceted Search | `VERIFIED` | Real-time counts across types, domains, licenses | `apps/api/tests/test_search.py` | `apps/api/routers/search.py` | Facets computed over filtered subset | Full faceted aggregation |
| **REQ-M2-03** | CLI Search | `VERIFIED` | Rich-rendered terminal search with table highlights | `packages/cli/tests/test_cli.py` | `packages/cli/openrobo_cli/main.py` | Offline search requires seed dataset | Online API sync option |

---

## Milestone 3 — Knowledge Graph & Compatibility Intelligence

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M3-01** | Graph Data Model & API | `VERIFIED` | Nodes & typed directional edges (DEPENDS_ON, CONFLICTS_WITH, etc.) | `apps/api/tests/test_graph_api.py` | `apps/api/models/graph.py` | Graph edge dataset is curated | Continuous crawler ingestion |
| **REQ-M3-02** | Compatibility Engine | `VERIFIED` | NetworkX constraint propagation, distro rules, SemVer, cycle detection | `packages/compat-engine/tests/` | `packages/compat-engine/` | Dynamic runtime metrics simulated statically | Hardware verification lab |
| **REQ-M3-03** | Dependency Resolution Engine | `VERIFIED` | Automated candidate resolution with minimal edits | `packages/compat-engine/tests/test_resolver.py` | `packages/compat-engine/openrobo_compat/resolver.py` | Greedy resolution strategy | SAT solver for complex multi-variant stacks |

---

## Milestone 4 — Interactive Robotics Stack Builder

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M4-01** | Stack Manifest API & Persistence | `VERIFIED` | Stack CRUD, import/export, validation endpoints | `apps/api/tests/test_stacks_api.py` | `apps/api/routers/stacks.py` | None | Monorepo standard |
| **REQ-M4-02** | 3-Panel Visual Stack Studio | `VERIFIED` | Resource library, composition canvas, live diagnostics | `apps/web/tests/unit/stack_builder.test.tsx` | `apps/web/app/stack-builder/` | Browser local memory for temporary edits | Database sync available |
| **REQ-M4-03** | Starter Templates & One-Click Fix | `VERIFIED` | Pre-configured AMR / manipulator templates and automated resolution application | `apps/web/tests/unit/stack_builder.test.tsx` | `apps/web/app/stack-builder/` | 3 initial templates | Expand template catalog |

---

## Milestone 5 — Workspace & Deployment Generation

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M5-01** | Colcon Workspace & Bringup Synthesis | `VERIFIED` | Deterministic synthesis of REP-149 package.xml, CMakeLists.txt, AST-validated launch.py, and parameter YAMLs | `packages/workspace-gen/tests/test_generator.py` | `packages/workspace-gen/` | Basic adapter matching replaced in M5.1 | Hardened in M5.1 |
| **REQ-M5-02** | Containerization & Dev Containers | `VERIFIED` | Multi-stage Dockerfiles mapped to ROS distros, Docker Compose services, VS Code Dev Container definitions | `packages/workspace-gen/tests/test_generator.py` | `packages/workspace-gen/generators/` | Real Docker build execution requires active host daemon | Provide automated CI container smoke test |
| **REQ-M5-03** | Cryptographic Lockfile & Determinism | `VERIFIED` | `openrobo.lock.json` with SHA-256 digests, component revisions, normalized ZIP timestamps | `packages/workspace-gen/tests/test_generator.py` | `packages/workspace-gen/lockfile.py` | Magic string "UNKNOWN" replaced in M5.1 | Structured lockfile in M5.1 |
| **REQ-M5-04** | Path Traversal & Security Hardening | `VERIFIED` | Strict relative path sanitizer blocking `..`, drive letters, device names, control chars | `packages/workspace-gen/tests/test_security.py` | `packages/workspace-gen/filesystem.py` | None | Monorepo standard |
| **REQ-M5-05** | Workspace API & ZIP Download | `VERIFIED` | REST endpoints for preview, generate, and streaming ZIP downloads | `apps/api/tests/test_workspace_api.py` | `apps/api/routers/workspace.py` | Memory-bounded streaming | Direct cloud bucket upload |
| **REQ-M5-06** | CLI Workspace Commands | `VERIFIED` | `openrobo workspace preview/generate/archive` with Rich diagnostic tree | `packages/cli/tests/test_cli.py` | `packages/cli/openrobo_cli/workspace.py` | None | Complete |
| **REQ-M5-07** | Web Workspace Preview UI | `VERIFIED` | In-browser workspace file tree browser, syntax viewer, and one-click ZIP download | `apps/web/tests/unit/workspace.test.tsx` | `apps/web/app/stack-builder/WorkspaceModal.tsx` | None | Complete |

---

## Milestone 5.1 — Generator Trust, Safety & Deployment Hardening

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M5.1-01** | Evidence & Confidence Model | `VERIFIED` | Structured `ComponentEvidence` levels (`VERIFIED_ADAPTER`, `USER_CONFIGURED`, `METADATA_DRIVEN`, `GENERIC_SCAFFOLD`) | `packages/workspace-gen/tests/test_generator.py` | `openrobo_workspace/models.py`, `planner.py` | None | Standard evidence model |
| **REQ-M5.1-02** | Deterministic Adapter Registry | `VERIFIED` | Removed substring matching; exact canonical ID matching for Nav2, SLAM, ros2_control, Gazebo | `packages/workspace-gen/tests/test_generator.py` | `openrobo_workspace/adapters/registry.py` | None | Immunity to false positive IDs |
| **REQ-M5.1-03** | ros2_control Safety & Geometry | `VERIFIED` | Removed guessed wheel/joint geometry; emits `.example` with required manual steps unless user-configured | `packages/workspace-gen/tests/test_generator.py` | `openrobo_workspace/adapters/ros2_control.py` | Requires user URDF joint names | Documented in README & lockfile |
| **REQ-M5.1-04** | Nav2 / SLAM / Gazebo Hardening | `VERIFIED` | Separated safe framework defaults from platform specifics; supported user frame/topic overrides | `packages/workspace-gen/tests/test_generator.py` | `openrobo_workspace/adapters/` | None | Complete |
| **REQ-M5.1-05** | package.xml & Escaping Safety | `VERIFIED` | `<exec_depend>` only for valid ROS package names; XML escaping and maintainer metadata resolution | `packages/workspace-gen/tests/test_generator.py` | `openrobo_workspace/generators/package_xml.py` | None | REP-149 compliant |
| **REQ-M5.1-06** | Docker Least-Privilege | `VERIFIED` | Removed default `privileged: true` and `/dev:/dev` mounts; explicit device passthrough | `packages/workspace-gen/tests/test_generator.py` | `openrobo_workspace/generators/compose.py` | Simulation profile optional | Complete |
| **REQ-M5.1-07** | Shell Injection Hardening | `VERIFIED` | Debian & pip regex validation, `shlex.quote`, rejection of control chars and subshells | `packages/workspace-gen/tests/test_security.py` | `openrobo_workspace/generators/rosdep.py` | None | Fully hardened |
| **REQ-M5.1-08** | Workspace Readiness & Static Validator | `VERIFIED` | Formal `WorkspaceValidator` (AST, XML, YAML, JSON); explicit readiness states in API, CLI, and Web UI | `packages/workspace-gen/tests/test_generator.py` | `openrobo_workspace/validator.py`, `models.py` | Real Docker build not executed in generator | Distinguishes static from runtime |

---

## Milestone 6 — Simulation & Runtime Integration

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M6-01** | Simulator Adapter Interface | `PLANNED` | Adapter interfaces for Gazebo, Webots, MuJoCo | Adapter unit tests | Pending | Scaffolding generated in M5.1 | Implement runtime simulator bridge |
| **REQ-M6-02** | ROS Graph Introspection & Health | `PLANNED` | Runtime node/topic health monitoring and rosbag telemetry | Introspection tests | Pending | Requires live ROS runtime | Implement runtime client |
