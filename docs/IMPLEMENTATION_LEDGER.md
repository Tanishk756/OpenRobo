# OpenRobo Implementation Ledger

This document tracks all functional requirements across OpenRobo milestones, recording verification evidence, test coverage, and known limitations.

---

## Milestone 0 — Foundation & Repository Architecture

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M0-01** | Canonical JSON Schemas | `VERIFIED` | Draft 2020-12 schemas for resource, graph, stack | `scripts/validate_schemas.py` | `schemas/*.json` | None | Maintain schema evolution ADRs |
| **REQ-M0-02** | Monorepo Structure & Tooling | `VERIFIED` | pnpm workspace + Python editable packages | `pnpm run check` | Root configs | None | Standardized cross-platform scripts |
| **REQ-M0-03** | Zero-Extra-Infrastructure Core | `VERIFIED` | FastAPI + PostgreSQL + Next.js 14 stack | Monorepo test suite | `apps/` & `packages/` | None | Ongoing maintenance |

---

## Milestone 1 — Registry Engine & Resource Discovery

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M1-01** | Resource Registry API | `VERIFIED` | Async CRUD, pagination, filtering, SQLAlchemy models | `apps/api/tests/test_resources.py` | `apps/api/routers/resources.py` | Seed dataset limited to 20 initial items | Ingest real-world packages in future milestones |
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
| **REQ-M5-01** | Colcon Workspace & Bringup Synthesis | `VERIFIED` | Deterministic synthesis of REP-149 package.xml, CMakeLists.txt, AST-validated launch.py, and parameter YAMLs | `packages/workspace-gen/tests/test_generator.py` | `packages/workspace-gen/` | Generic components receive commented `.example` templates | Add more verified adapters in M6+ |
| **REQ-M5-02** | Containerization & Dev Containers | `VERIFIED` | Multi-stage Dockerfiles mapped to ROS distros, Docker Compose services, VS Code Dev Container definitions | `packages/workspace-gen/tests/test_generator.py` | `packages/workspace-gen/generators/` | Real Docker build execution requires active host daemon | Provide automated CI container smoke test |
| **REQ-M5-03** | Cryptographic Lockfile & Determinism | `VERIFIED` | `openrobo.lock.json` with SHA-256 digests, component revisions, normalized ZIP timestamps | `packages/workspace-gen/tests/test_generator.py` | `packages/workspace-gen/lockfile.py` | Unreleased packages marked with UNKNOWN revision | Git commit hash extraction |
| **REQ-M5-04** | Path Traversal & Security Hardening | `VERIFIED` | Strict relative path sanitizer blocking `..`, drive letters, device names, control chars | `packages/workspace-gen/tests/test_security.py` | `packages/workspace-gen/filesystem.py` | None | Monorepo standard |
| **REQ-M5-05** | Workspace API & ZIP Download | `VERIFIED` | REST endpoints for preview, generate, and streaming ZIP downloads | `apps/api/tests/test_workspace_api.py` | `apps/api/routers/workspace.py` | Memory-bounded streaming | Direct cloud bucket upload |
| **REQ-M5-06** | CLI Workspace Commands | `VERIFIED` | `openrobo workspace preview/generate/archive` with Rich diagnostic tree | `packages/cli/tests/test_cli.py` | `packages/cli/openrobo_cli/workspace.py` | None | Complete |
| **REQ-M5-07** | Web Workspace Preview UI | `VERIFIED` | In-browser workspace file tree browser, syntax viewer, and one-click ZIP download | `apps/web/tests/unit/workspace.test.tsx` | `apps/web/app/stack-builder/WorkspaceModal.tsx` | None | Complete |

---

## Milestone 6 — Simulation & Runtime Integration

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M6-01** | Simulator Adapter Interface | `PLANNED` | Adapter interfaces for Gazebo, Webots, MuJoCo | Adapter unit tests | Pending | Scaffolding generated in M5 | Implement runtime simulator bridge |
| **REQ-M6-02** | ROS Graph Introspection & Health | `PLANNED` | Runtime node/topic health monitoring and rosbag telemetry | Introspection tests | Pending | Requires live ROS runtime | Implement runtime client |

---

## Milestone 7 — Community & Governance

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M7-01** | Community Submission & Moderation | `PLANNED` | Community submission pull-request & verification system | Workflow tests | Pending | Automated anti-spam safeguards needed | Design submission portal |

---

## Milestone 8 — AI Abstraction Layer & pgvector

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M8-01** | Model Agnostic AI Provider Interface | `PLANNED` | Unified API for Local LLMs (Ollama) & Hosted LLMs with pgvector RAG | Provider unit tests | Pending | Optional feature only | Implement `AIProvider` base class & pgvector |

---

## Milestone 9 — Production Hardening & Observability

| Requirement ID | Requirement Description | Status | Implementation Details | Tests | Evidence | Known Limitations | Next Action |
|---|---|---|---|---|---|---|---|
| **REQ-M9-01** | Security Hardening & Observability | `PLANNED` | Rate limiting, SSRF guardrails, Prometheus metrics | Security & load tests | Pending | Infrastructure production setup | Implement security middleware |