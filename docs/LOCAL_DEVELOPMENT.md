# OpenRobo — Local Development Guide

## Setup Instructions

### Prerequisites
- Node.js 18+ & `pnpm` (v8+)
- Python 3.11+ & `pip`
- Docker & Docker Compose (for PostgreSQL 16)

### 1. Install Dependencies
Run from the repository root:
```bash
make install
```
This installs:
- Node monorepo packages (`pnpm install`)
- Editable Python packages (`packages/schemas`, `packages/compat-engine`, `packages/cli`, `apps/api`)

### 2. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### 3. Start PostgreSQL Database
```bash
make db-up
```

### 4. Run Schema Validation & Test Suite
```bash
make validate-schemas
make test
```

### 5. Start Development Servers
- Backend API (Port 8000):
  ```bash
  uvicorn apps.api.main:app --reload --port 8000
  ```
- Web Frontend (Port 3000):
  ```bash
  pnpm --filter openrobo-web dev
  ```

### 6. Developer Commands (`Makefile`)
- `make lint`: Run Ruff and ESLint checks.
- `make validate-schemas`: Validate JSON schema draft 2020-12 specs.
- `make test`: Run backend Pytest and frontend Vitest suites.
- `make test-e2e`: Run Playwright E2E browser tests.
- `make build`: Compile Next.js web application.
