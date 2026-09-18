# Contributing to OpenRobo

Thank you for your interest in contributing to **OpenRobo**! OpenRobo is a vendor-neutral, community-driven robotics platform dedicated to standardizing component metadata, reasoning about cross-package compatibility, and generating reproducible developer environments for robotics engineers worldwide.

---

## Code of Conduct

All contributors and community participants are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Development Prerequisites

OpenRobo is designed for cross-platform development on **Linux**, **macOS**, and **Windows**:

- **Node.js**: `v18+` or `v20+`
- **pnpm**: `v8+` or `v9+`
- **Python**: `3.10`, `3.11`, or `3.12`
- **PostgreSQL**: `16+` (for production search indexes; SQLite in-memory is supported for local unit tests)
- **Git**

---

## Local Repository Setup

1. **Fork & Clone**:
   ```bash
   git clone https://github.com/<your-username>/OpenRobo.git
   cd OpenRobo
   ```

2. **Install Node Workspaces**:
   ```bash
   pnpm install
   ```

3. **Install Python Packages (Editable Mode)**:
   ```bash
   # In your virtual environment:
   python -m pip install -e packages/schemas -e packages/compat-engine -e packages/cli -e "apps/api[test]"
   ```

4. **Verify Environment**:
   ```bash
   pnpm run check
   ```

---

## Development Workflow

### 1. Branching Strategy
- Create feature or bugfix branches from `main`:
  - `feat/feature-name`
  - `fix/issue-description`
  - `docs/documentation-update`

### 2. Local Services
- **FastAPI Backend**: `pnpm run dev:api` (Runs on `http://localhost:8000`)
- **Next.js Web Frontend**: `pnpm run dev:web` (Runs on `http://localhost:3000`)
- **Seed Robotics Registry**: `pnpm run seed`

### 3. Pre-PR Quality Gates
Before opening a pull request, ensure the full check suite passes:
```bash
# Full automated gate (Linter + Schema Validator + Python Pytest + Web Vitest + Next.js Build)
pnpm run check

# Or individual checks:
pnpm run lint          # Ruff & ESLint
pnpm run validate      # Draft 2020-12 Schema Validator
pnpm run test          # Pytest & Vitest
pnpm run build         # Next.js production build
```

---

## Contribution Areas

### 1. Adding Resource Manifests
OpenRobo resource manifests follow the JSON Schema at `schemas/resource.schema.json`. You can add verified manifests to `samples/` or ingest directly via the CLI:
```bash
openrobo ingest github https://github.com/ros-navigation/navigation2
```

### 2. Enhancing Search & Ranking
Search indexing and ranking algorithms live in `apps/api/services/search/`. All ranking logic must remain deterministic and reproducible.

### 3. Extending Compatibility Graph
Compatibility edge rules and constraint checkers live in `packages/compat-engine/`.

---

## Commit & Pull Request Guidelines

- **Commit Style**: Use [Conventional Commits](https://www.conventionalcommits.org/):
  - `feat: add ros2_control hardware interface detector`
  - `fix: correct trigram rank normalization for single-token queries`
  - `docs: update quickstart guide for Windows development`
  - `test: add unit test for multi-taxonomy facet counter`
- **Pull Requests**:
  - Reference relevant issues (e.g. `Closes #12`).
  - Provide clear reproduction or verification steps in your PR description.
  - Ensure all CI tests pass before requesting review.

---

## Questions and Support

Feel free to open an issue or start a discussion on GitHub if you have questions or ideas for OpenRobo. We welcome all contributions from the robotics community!
