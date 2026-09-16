# OpenRobo

Open-source robotics commons: discover, build, simulate, deploy, and contribute.

## Status
**Milestone 1 — Registry Engine & Resource Discovery** (VERIFIED & COMPLETE).

## Core Principles
- Free to use
- Open source (Apache-2.0)
- Vendor neutral
- Hardware agnostic
- AI/model agnostic
- All robotics domains
- Local-first & offline-friendly
- License-aware
- Reproducible & community driven

## Quick Start (Cross-Platform)

### 1. Install Dependencies
```bash
# Node workspace packages
pnpm install

# Python packages (editable mode)
python -m pip install -e packages/schemas -e packages/compat-engine -e packages/cli -e "apps/api[test]"
```

### 2. Run Validation & Test Suite
```bash
pnpm run check
```

### 3. Start Development Services
- **Backend API**: `pnpm run dev:api` (Runs FastAPI at `http://localhost:8000`)
- **Web Frontend**: `pnpm run dev:web` (Runs Next.js at `http://localhost:3000`)
- **Seed Registry Data**: `pnpm run seed`

### 4. Ingest Robotics Repositories
```bash
# CLI ingestion
openrobo ingest github https://github.com/ros-navigation/navigation2

# REST API ingestion
curl -X POST http://localhost:8000/api/v1/ingestion/github \
  -H "Content-Type: application/json" \
  -d '{"repository_url": "https://github.com/ros-navigation/navigation2"}'
```

For detailed setup instructions on both Windows and Linux, see [`docs/LOCAL_DEVELOPMENT.md`](docs/LOCAL_DEVELOPMENT.md).
