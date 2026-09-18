# OpenRobo — Milestone 0 (M0) Implementation Plan (Revised)

**Milestone**: M0 — Repository Foundation & Architecture Baseline
**Goal**: Establish a production-grade polyglot monorepo structure, unified developer tooling, canonical JSON schemas, SQLAlchemy 2.x ORM & Alembic baseline, Knowledge Graph edge schema, Vitest/Playwright test harness, and Apache-2.0 licensing without creating fake UI or placeholder code.

---

## Task Breakdown & Action Steps

### Phase 1: Workspace & Tooling Setup
1. **Root Package & License Configuration**:
   - Replace `LICENSE_PLACEHOLDER.md` with official Apache-2.0 `LICENSE` file (per ADR-0006).
   - Create root `package.json` with `pnpm` workspace scripts (`dev`, `build`, `lint`, `test`, `test:e2e`).
   - Create `pnpm-workspace.yaml` defining `apps/*` and `packages/*`.
   - Create root `pyproject.toml` for Python workspace tooling (Ruff, Pytest).
   - Create `.gitignore` ignoring Node modules, Python venvs, `.next/`, `__pycache__`, and Playwright test artifacts.

2. **Directory Structure Creation**:
   - `apps/web`: Next.js 14 Web UI shell structure (configured with Vitest, React Testing Library, and Playwright).
   - `apps/api`: FastAPI Python backend service shell structure (configured with SQLAlchemy 2.x, Alembic, and Pydantic v2).
   - `packages/schemas`: Shared canonical JSON Schema assets and model definitions.
   - `packages/cli`: Python CLI entrypoint package (`openrobo`).
   - `packages/compat-engine`: OpenRobo Knowledge Graph and compatibility reasoning package.

3. **Unified Developer Interface**:
   - Create `Makefile` with targets: `install`, `dev`, `build`, `test`, `test-e2e`, `lint`, `validate-schemas`.
   - Create `docker-compose.yml` configured for local PostgreSQL 16 development database.

---

### Phase 2: Schema & Knowledge Graph Standardization
1. **JSON Schema Refinement (`packages/schemas`)**:
   - Expand `schemas/resource.schema.json` with complete property definitions for evidence levels, SPDX licenses, dependencies, platform constraints, and hardware specifications.
   - Create `schemas/graph.schema.json` for Knowledge Graph relationship edges.
   - Create `schemas/stack.schema.json` for reproducible stack manifests.
   - Create schema validation script `scripts/validate_schemas.py`.

2. **Database Architecture & ORM Baseline (`apps/api`)**:
   - Implement **SQLAlchemy 2.x Declarative ORM models** (`apps/api/models`) for `Resource`, `ResourceVersion`, `Domain`, `Capability`, `GraphNode`, `GraphEdge`, `CompatibilityResult`, and `StackManifest`.
   - Initialize **Alembic migration environment** (`apps/api/alembic`) with initial baseline migration script.
   - Implement **Pydantic v2 validation schemas** (`apps/api/schemas`) strictly separated from ORM models.

---

### Phase 3: CI/CD Pipeline Configuration
1. **GitHub Actions Workflows (`.github/workflows/`)**:
   - `ci.yml`: Runs Node/pnpm linting, Vitest frontend tests, Playwright browser E2E tests, Python Ruff checks, and Pytest execution.
   - `schema-validate.yml`: Executes JSON Schema validation against canonical schema definitions.

---

### Phase 4: Test Infrastructure Baseline
1. **Test Suites**:
   - `apps/api/tests/`: Pytest suite verifying backend server startup, FastAPI OpenAPI schema generation, and SQLAlchemy 2.x ORM models.
   - `apps/web/tests/`: Vitest + React Testing Library setup for component tests, and Playwright config for browser E2E workflows.
   - `packages/compat-engine/tests/`: Pytest suite for NetworkX Knowledge Graph algorithms.
   - `packages/cli/tests/`: Pytest suite verifying `openrobo --help` and CLI entrypoints.

---

## M0 Acceptance & Verification Criteria

To mark M0 **VERIFIED**, all of the following criteria must pass:
1. `LICENSE` exists containing official Apache License 2.0 text.
2. `make install` installs all Node and Python dependencies cleanly.
3. `make lint` passes with 0 lint errors across TypeScript and Python codebases.
4. `make validate-schemas` passes for all schema files in `schemas/`.
5. `make test` executes all unit and component tests (Vitest + Pytest) with 100% pass rate.
6. `make build` compiles `apps/web` and `apps/api` without build errors.
7. CI workflow definitions in `.github/workflows/` validate without syntax errors.

---

## Post-M0 Progression Boundary

Upon review and approval of M0 by maintainers, development will immediately advance to **Milestone 1 — Registry Engine & Core API**.
