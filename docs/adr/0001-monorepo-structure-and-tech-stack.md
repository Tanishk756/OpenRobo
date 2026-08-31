# ADR-0001: Monorepo Structure and Core Technology Stack

- **Status**: Accepted
- **Date**: 2026-08-31
- **Authors**: OpenRobo Architecture Team

## Context

OpenRobo requires a cohesive repository structure and technology stack to support:
1. Web User Interface (Resource discovery, stack composition, project views)
2. Backend API Service (Registry CRUD, compatibility evaluation, ingestion)
3. Command Line Interface (CLI for local-first workflows)
4. Schema Specifications (JSON Schema definitions for resources and stacks)
5. OpenRobo Knowledge Graph & Reasoning Engine (Dependency tracking and compatibility analysis)

The system must remain local-first, vendor-neutral, zero-cost compatible, and highly accessible to robotics engineers and developers.

## Decision

We adopt a **polyglot monorepo structure** managed via standard, open tooling:

1. **Frontend (`apps/web`)**: Next.js (App Router), React, TypeScript, Vanilla CSS Modules / Tailwind CSS. Optimized for fast rendering, high density, dark mode, keyboard navigation, and desktop-first responsiveness.
   - **Frontend Testing**: Vitest, React Testing Library (RTL) for unit/component testing, and Playwright for browser End-to-End (E2E) testing.
2. **Backend Services (`apps/api`)**: Python 3.12+ with FastAPI.
   - **ORM**: SQLAlchemy 2.x for clean database access and mapping.
   - **Migrations**: Alembic for versioned schema migrations.
   - **Validation**: Pydantic v2 for API request/response validation and domain schemas.
   - *Architecture Principle*: Keep ORM models, migration scripts, and Pydantic validation schemas strictly separated.
3. **Core Schemas (`packages/schemas`)**: Standardized JSON Schema draft 2020-12 files and exported TypeScript/Pydantic types.
4. **CLI Package (`packages/cli`)**: Python CLI built using `typer` and `rich`, providing offline manifest validation, search, stack creation, knowledge graph query, and local workspace generation.
5. **Compatibility & Graph Engine (`packages/compat-engine`)**: Python module wrapping NetworkX / graph algorithms to process resource dependency networks and compatibility rule evaluation over the OpenRobo Knowledge Graph.
6. **Monorepo Tooling**: `pnpm` workspaces for TypeScript/Web assets and `uv` / `virtualenv` workspace management for Python packages.

## Structure

```text
OpenRobo/
├── .github/workflows/      # CI/CD pipelines
├── apps/
│   ├── web/                # Next.js frontend application (Vitest + RTL + Playwright)
│   └── api/                # FastAPI REST backend service (SQLAlchemy 2.x + Alembic + Pydantic v2)
├── packages/
│   ├── schemas/            # JSON Schemas and data models
│   ├── cli/                # `openrobo` CLI utility
│   └── compat-engine/      # OpenRobo Knowledge Graph & Compatibility Engine
├── docs/
│   ├── adr/                # Architecture Decision Records
│   ├── ARCHITECTURE_AUDIT.md
│   ├── IMPLEMENTATION_LEDGER.md
│   └── M0_IMPLEMENTATION_PLAN.md
├── schemas/                # Master canonical schemas
├── docker-compose.yml      # Local development environment (PostgreSQL 16)
├── Makefile                # Unified developer CLI commands
└── README.md
```

## Consequences

### Positive
- Strict separation of concerns between SQLAlchemy 2.x (ORM), Alembic (DB migrations), and Pydantic v2 (API Validation).
- Robust testing strategy pairing Pytest (backend/CLI/graph) with Vitest, React Testing Library, and Playwright (frontend/E2E).
- Python backend enables native integration with robotics math, graph processing, and future AI tooling.
- Local CLI shares Pydantic schemas and compatibility engine directly with backend API.

### Negative / Trade-offs
- Polyglot Node.js + Python tooling requires running both `pnpm` and `uv`/`python3` toolchains during development.
