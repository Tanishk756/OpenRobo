# OpenRobo — Local Development Guide

This guide covers setup and daily development workflows on both **Windows** (PowerShell / Command Prompt) and **Linux/macOS** (Bash / Make).

---

## Prerequisites
- **Node.js**: 20+ (LTS) or 24+
- **pnpm**: 8+ or 12+ (`npm install -g pnpm`)
- **Python**: 3.11+ or 3.12+ & `pip`
- **Docker** (optional for production PostgreSQL testing; in-memory SQLite is used automatically for unit tests)

---

## 1. Quick Start (Cross-Platform via pnpm)

OpenRobo provides cross-platform task runner scripts in root `package.json` that work identically across Windows and Linux without requiring `make`.

### Install Dependencies
```bash
pnpm install
python -m pip install -e packages/schemas -e packages/compat-engine -e packages/cli -e "apps/api[test]"
```

### Run Full Test Suite & Validation
```bash
pnpm run check
```
*(Runs Python linting, Web linting, schema validation, Pytest suite, Vitest suite, and Next.js production build).*

---

## 2. Running Development Servers

### Start Backend API (FastAPI)
```bash
pnpm run dev:api
# Or: python -m uvicorn apps.api.main:app --reload --port 8000
```
Interactive OpenAPI Docs: [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
Health Endpoint: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

### Start Web Frontend (Next.js 14)
```bash
pnpm run dev:web
# Or: pnpm --filter openrobo-web run dev
```
Web App: [http://localhost:3000](http://localhost:3000)
Resource Explorer: [http://localhost:3000/resources](http://localhost:3000/resources)

---

## 3. Seeding the Registry Database
Populate the database with 20+ canonical robotics manifests across ROS 2 packages, hardware drivers, robots, simulations, frameworks, and observability tools:
```bash
pnpm run seed
# Or: python scripts/seed_data.py
```

---

## 4. Developer Command Reference

| Task | Cross-Platform Command | Linux/Mac `make` Target |
|---|---|---|
| **Run Full Verification** | `pnpm run check` | `make lint test build` |
| **Run All Tests** | `pnpm test` | `make test` |
| **Run Python Tests** | `pnpm run test:python` | `python -m pytest` |
| **Run Frontend Tests** | `pnpm run test:web` | `pnpm --filter openrobo-web test` |
| **Run Schema Validator** | `pnpm run validate` | `make validate-schemas` |
| **Run Linters** | `pnpm run lint` | `make lint` |
| **Build Web App** | `pnpm run build` | `make build` |
| **Seed Database** | `pnpm run seed` | `make seed` |
| **Start PostgreSQL** | `docker compose up -d postgres` | `make db-up` |
| **Stop PostgreSQL** | `docker compose down` | `make db-down` |

---

## 5. Environment Variables (`.env`)

| Variable | Default | Description |
|---|---|---|
| `ENVIRONMENT` | `development` | `development`, `staging`, or `production` |
| `API_PORT` | `8000` | FastAPI server listening port |
| `DATABASE_URL` | `postgresql+asyncpg://openrobo:openrobo_dev_password@localhost:5432/openrobo_db` | Production PostgreSQL async connection string |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL used by the Next.js frontend to reach FastAPI |

---

## 6. Test Database Isolation Strategy
* **Unit & Integration Tests**: Backend tests use an in-memory SQLite fixture (`sqlite+aiosqlite:///:memory:`) configured in `apps/api/tests/conftest.py` with FastAPI dependency overrides. Tests execute deterministically and completely isolated without requiring Docker or active PostgreSQL.
* **Production Deployment**: Uses PostgreSQL 16 with asynchronous `asyncpg` and Alembic migrations (`alembic upgrade head`).
