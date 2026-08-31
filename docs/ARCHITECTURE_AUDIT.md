# OpenRobo — Architecture Audit & Systems Engineering Report (Revised)

**Date**: 2026-08-31  
**Author**: Principal Autonomous Engineering Team  
**Scope**: Complete repository audit, specification analysis, revised architecture design, gap analysis, and updated M0 preparation.

---

## 1. Executive Summary & Repository Audit

The **OpenRobo** repository currently serves as a specification foundation. An audit of the existing codebase reveals:

- **Source Files**: `MASTER_ANTIGRAVITY_BUILD_PROMPT.md`, `README.md`, `LICENSE_PLACEHOLDER.md`, `schemas/resource.schema.json`, and 13 markdown files in `docs/` (`00_MASTER_SPECIFICATION.md` through `12_ROADMAP.md`).
- **Implementation State**: **0 lines of application code**. There is currently no active web application, API server, database ORM, CLI executable, build script, package configuration (`package.json`, `pyproject.toml`), or automated test harness.
- **Scope Confirmation**: OpenRobo is confirmed to operate as a **metadata and provenance registry**, indexing upstream open-source robotics projects without mirroring full code repositories or large binary assets.

---

## 2. Requirements-to-Implementation Gap Analysis

| Category | Product Requirement | Current Repository State | Gap Assessment |
|---|---|---|---|
| **Monorepo / Build** | Polyglot multi-package workspace | Missing `package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, Docker setup | **Critical Gap**: No development environment or build harness exists. |
| **Database Architecture** | SQLAlchemy 2.x + Alembic + Pydantic v2 separation | Abstract description in `03_ARCHITECTURE.md` | **Critical Gap**: No SQLAlchemy ORM models, Alembic migrations, or Pydantic validation schemas exist. |
| **Knowledge Graph** | Foundation for discovery, compatibility, stack building, & AI | Unimplemented in current repo | **Critical Gap**: No Knowledge Graph edge definitions or predicate model. |
| **Metadata Standard** | Draft 2020-12 JSON Schema for resources | Minimal `schemas/resource.schema.json` | **Major Gap**: Existing schema lacks typed sub-schemas for evidence, hardware specs, and graph relations. |
| **Testing Strategy** | Vitest + RTL + Playwright (Web) & Pytest (Backend) | No test configuration | **Critical Gap**: No automated test suites or runners configured. |
| **Search & Filtering** | Postgres FTS + `pg_trgm` fuzzy matching | Spec calls for PostgreSQL search | **Critical Gap**: Search indexer and query handlers not implemented. |
| **Compatibility Engine** | Explainable 4-state engine with 6-level evidence | Spec `05_COMPATIBILITY_ENGINE.md` | **Critical Gap**: No dependency graph evaluator or reasoning engine exists. |
| **CLI Utility** | Local-first `openrobo` CLI | Spec `01_PRODUCT_REQUIREMENTS.md` | **Critical Gap**: No executable CLI package. |
| **License Decision** | Apache-2.0 core project license | `LICENSE_PLACEHOLDER.md` present | **Decision Completed**: Apache-2.0 selected after legal/compatibility review (ADR-0006). |

---

## 3. Revised Production Architecture & OpenRobo Knowledge Graph

OpenRobo is designed as a **decoupled, local-first hybrid architecture** powered by the **OpenRobo Knowledge Graph**:

```text
               +----------------------------------------+
               |            Next.js Web App             |
               |     (Explore, Stack Builder, UI)       |
               +-------------------+--------------------+
                                   |
                                   v  (REST / OpenAPI)
               +-------------------+--------------------+
               |         FastAPI Backend Service        |
               | (Pydantic v2 Validation & Routers)     |
               +---------+--------------------+---------+
                         |                    |
                         v                    v
         +---------------+----+     +---------+----------------+
         |  SQLAlchemy 2.x /  |     | OpenRobo Knowledge Graph |
         |   Alembic DB       |     |  Engine (NetworkX / Py)  |
         |  (PostgreSQL 16)   |     +--------------------------+
         +--------------------+
```

### Core Architectural Concept: OpenRobo Knowledge Graph
The **Knowledge Graph** is the foundational data and reasoning abstraction powering:
- **Discovery**: Traversed graph exploration of connected hardware, drivers, packages, and projects.
- **Compatibility**: Evaluating multi-node compatibility paths across OS distributions, ROS versions, and hardware targets.
- **Dependency Resolution**: Transitive software and hardware dependency calculation.
- **Stack Synthesis**: Automated generation of valid multi-layer robotics stacks based on graph constraints.
- **Simulation Integration**: Linking robot description models (URDF/SDF) to simulator adapters (Gazebo, Webots, MuJoCo).
- **AI / RAG Grounding**: Providing structured graph context for recommendations and RAG assistants.

#### Knowledge Graph Edge Predicates:
The graph represents directed relations including:
- `depends-on`, `optional-dependency`, `conflicts-with`, `compatible-with`, `tested-with`, `provides`, `implements`, `driver-for`, `hardware-for`, `simulation-model-for`, `simulated-by`, `runs-on`, `requires`, `used-by`, `part-of`, `alternative-to`, `derived-from`.

---

## 4. Technology Stack & Component Separation

- **Frontend (`apps/web`)**: Next.js (App Router), React, TypeScript, Vanilla CSS Modules / Tailwind CSS.
- **Backend Framework (`apps/api`)**: Python 3.12 + FastAPI.
  - **ORM / Persistence**: SQLAlchemy 2.x for clean database access.
  - **Migrations**: Alembic for version-controlled database schema migrations.
  - **Validation & Domain Models**: Pydantic v2 for API request/response validation.
  - *Strict Rule*: ORM models, migration scripts, and Pydantic schemas remain strictly decoupled.
- **CLI Utility (`packages/cli`)**: Python CLI (`openrobo`) built with `Typer` and `Rich`.
- **Reasoning Engine (`packages/compat-engine`)**: Python `NetworkX` graph traversal and rule evaluation.

---

## 5. Revised Testing Strategy

- **Web Frontend (`apps/web`)**:
  - **Unit & Component Testing**: Vitest + React Testing Library (RTL).
  - **End-to-End Browser Testing**: Playwright for cross-browser workflow verification (Explore, Search, Stack Builder).
- **Backend & Graph Engine (`apps/api`, `packages/compat-engine`, `packages/cli`)**:
  - **Unit & Integration Testing**: Pytest with FastAPI `TestClient` and async database test fixtures.
- **Schema Validation**: Automated Python schema validator script checking canonical JSON Schema draft 2020-12 files.

---

## 6. Revised Database & Persistence Strategy

- **Database Engine**: PostgreSQL 16+ serving as the unified relational and graph data store.
  - Core features utilized in M0–M7: Relational tables, JSON/JSONB fields, Full-Text Search (`tsvector`), and Trigram fuzzy matching (`pg_trgm`).
  - **`pgvector` Deferral**: `pgvector` is explicitly deferred until Milestone 8 (AI / RAG).
- **Knowledge Graph Persistence**: Persisted directly in PostgreSQL using relational node and edge tables (`graph_nodes`, `graph_edges`). Graph algorithms run in-memory via Python `NetworkX` or recursive SQL (`WITH RECURSIVE`). Specialized graph databases (e.g. Neo4j) are excluded unless future scale measurements justify them.

---

## 7. Open-Source & License Compatibility Decision

- **Project License Selection**: **Apache License 2.0** is selected for OpenRobo's own codebase (ADR-0006).
- **License Analysis**: Apache-2.0 provides explicit patent rights grants, strong community protection, and full compatibility with ROS 2 (Apache-2.0), Gazebo (Apache-2.0), PX4 (BSD-3-Clause), and downstream GPL-3.0 integrations.
- **Indexed Upstream Projects**: Original licenses and copyright notices of indexed projects are 100% preserved.

---

## 8. Scalability & Technical Risks

1. **Recursive Graph Traversal Latency**: Deep multi-hop graph queries could slow API response times.  
   *Mitigation*: Execute recursive graph traversals using B-Tree indexed SQL `WITH RECURSIVE` queries or load subgraphs into in-memory `NetworkX` instances; cache evaluated subgraphs.
2. **Rate Limits on External Metadata Ingestion**: Ingesting GitHub repositories may hit API rate limits.  
   *Mitigation*: Support GitHub API tokens, HTTP `ETag` conditional caching, and background task queues.

---

## 9. Architecture Decision Records (ADRs) Summary

- **ADR-0001**: Monorepo Structure & Core Technology Stack (Next.js + FastAPI + Python CLI).
- **ADR-0002**: Database, Search, and Knowledge Graph Persistence Architecture (PostgreSQL 16, SQLAlchemy 2.x, Alembic, Pydantic v2, `pgvector` deferred).
- **ADR-0003**: Compatibility Engine and Evidence Model (4-state compatibility, 6-level evidence).
- **ADR-0004**: AI Provider Abstraction and Local-First Architecture (Optional `AIProvider` interface).
- **ADR-0005**: Open-Source License and Compliance Policy (SPDX enforcement & metadata registry model).
- **ADR-0006**: OpenRobo Project License Selection (Apache-2.0 selected after legal/compatibility review).
- **ADR-0007**: OpenRobo Knowledge Graph Architecture (Core graph abstraction, 17+ relationship predicates, PostgreSQL relational persistence).

---

## 10. Unresolved Product & Architecture Decisions

1. **Upstream Asset Indexing Boundaries**: Confirming specific metadata file depth (e.g., `package.xml`, `CMakeLists.txt`, `pyproject.toml`, `README.md`, `LICENSE`) extracted during ingestion. (Recommendation: Extract manifest metadata and top-level documentation summaries only).
2. **Community Evidence Submission Thresholds**: Determining moderation requirements for community-submitted compatibility reports. (Recommendation: Mandatory verification tag `COMMUNITY_REPORTED` until verified by CI).

---

## 11. Concrete M0 Implementation Plan

See `docs/M0_IMPLEMENTATION_PLAN.md` for the updated milestone execution breakdown.
