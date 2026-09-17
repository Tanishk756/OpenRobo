<div align="center">

# OpenRobo

**Open-source robotics platform for discovering components, reasoning about compatibility, building robot stacks, and generating reproducible developer environments.**

[![OpenRobo CI](https://github.com/Tanishk756/OpenRobo/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Tanishk756/OpenRobo/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.10%20|%203.11%20|%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14.1-black?logo=next.js&logoColor=white)](https://nextjs.org/)
[![ROS 2](https://img.shields.io/badge/ROS_2-Jazzy%20|%20Humble-22314E?logo=ros&logoColor=white)](https://docs.ros.org/)
[![Architecture](https://img.shields.io/badge/Architecture-Zero--Extra--Infrastructure-green.svg)](#architecture)

</div>

---

## What is OpenRobo?

Robotics software engineering is fragmented across hundreds of isolated repositories, disparate ROS packages, custom sensor drivers, and fragile dependency chains. Integrating a robot stack—from LiDAR SLAM and arm kinematics to hardware interfaces and simulation—often requires hours of manual dependency debugging.

**OpenRobo** provides a standardized, vendor-neutral software registry, intelligent compatibility engine, stack builder, and automated workspace synthesis platform for modern robotics:
- **Discover Components**: Search thousands of ROS 2 packages, hardware drivers, simulation models, and algorithms with weighted full-text and fuzzy typo-tolerant indexing.
- **Understand Compatibility**: Graph-based constraint validation mapping cross-package compatibility across ROS distributions, CPU architectures, and OS kernels.
- **Build Robot Stacks**: Compose modular robotics architectures with interactive dependency checking and one-click conflict resolution (`/stack-builder`).
- **Generate Workspaces**: Synthesize deterministic, reproducible Colcon workspaces, REP-149 bringup meta-packages, AST-validated launch scripts, multi-stage Dockerfiles, Dev Containers, and lockfiles (`openrobo.lock.json`).

---

## Implemented Features (Available Now)

- [x] **Canonical Robotics Schemas**: JSON Schema (Draft 2020-12) standards for resource manifests (`resource.schema.json`), compatibility graphs (`graph.schema.json`), and robot stacks (`stack.schema.json`).
- [x] **Knowledge Graph & Compatibility Intelligence**: Deterministic reasoning layer evaluating ROS 2 distributions (Humble, Jazzy, Iron, Rolling), OS, CPU architecture (x86_64, aarch64), SemVer constraints, required hardware/capabilities, cycle detection, and conflict propagation with sub-50ms matrix performance.
- [x] **Zero-Extra-Infrastructure Search Engine**: PostgreSQL-backed weighted full-text search (`tsvector`, GIN indexes) with `pg_trgm` fuzzy similarity matching and multi-taxonomy faceting.
- [x] **Interactive Robotics Stack Builder**: Visual 3-panel stack composition studio (`/stack-builder`) with real-time constraint evaluation, starter templates, dependency auto-resolution proposals, and manifest import/export.
- [x] **Hardened Workspace & Deployment Generator (Milestone 5.1)**: Synthesizes strictly-typed, statically-validated ROS 2 colcon workspaces, launch pipelines, parameter configurations, least-privilege Dockerfiles, Docker Compose definitions, VS Code Dev Containers, setup scripts, and byte-reproducible ZIP bundles.
- [x] **Strict Generator Evidence & Safety Model**: Enforces "NO EVIDENCE → NO INVENTED CONFIGURATION". Components distinguish `VERIFIED_ADAPTER`, `USER_CONFIGURED`, `METADATA_DRIVEN`, and `GENERIC_SCAFFOLD` (scaffolding `.example` templates with explicit required manual configuration steps).
- [x] **Deterministic Adapter Registry**: Eliminates dangerous substring matching with canonical dictionary matching for Nav2, SLAM Toolbox, ros2_control, and Gazebo.
- [x] **Reproducible Lockfiles & Provenance**: Generates cryptographic lockfiles (`openrobo.lock.json`) capturing component digests, repository URLs, build types, upstream licenses, evidence levels, and workspace readiness states.
- [x] **Static Robotics Repository Ingestion**: Safe, non-executing static analysis of GitHub repositories extracting ROS `package.xml` manifests, dependencies, maintainers, and licenses with full provenance tracking.
- [x] **Unified CLI**: Typer/Rich command-line suite for schema validation, static GitHub ingestion, ranked registry search, and workspace preview/generation/archive (`openrobo workspace`).
- [x] **Cross-Platform Compatibility**: Full first-class support for Linux, macOS, and Windows development workflows.

---

## Architecture

OpenRobo is structured as a zero-extra-infrastructure monorepo managed with **pnpm** and **Python virtual environments**:

```
OpenRobo/
├── schemas/                      # Canonical JSON Schema v2020-12 Definitions
│   ├── resource.schema.json      # Component metadata & platform matrix schema
│   ├── graph.schema.json         # Compatibility & dependency edge schema
│   └── stack.schema.json         # Complete robot stack assembly schema
├── packages/
│   ├── schemas-py/               # Python schema validation library (openrobo-schemas)
│   ├── compat-engine/            # Compatibility reasoning & graph engine (openrobo-compat)
│   ├── workspace-gen/            # Hardened ROS 2 workspace generator (openrobo-workspace)
│   └── cli/                      # Typer/Rich unified CLI application (openrobo)
├── apps/
│   ├── api/                      # FastAPI async REST API service
│   └── web/                      # Next.js 14 App Router interactive web frontend
├── scripts/                      # Schema validators & seed database scripts
└── docs/                         # Architecture Decision Records & Milestone Plans
```

---

## Quickstart & Local Setup

### Prerequisites

- **Node.js**: `v18.17.0+` or `v20.x`
- **pnpm**: `v8.0.0+` (`corepack enable pnpm`)
- **Python**: `3.10`, `3.11`, or `3.12`
- **PostgreSQL**: `14+` (with `pg_trgm` extension) or in-memory SQLite for testing

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/Tanishk756/OpenRobo.git
cd OpenRobo

# Install Node & Frontend dependencies
pnpm install

# Setup Python Virtual Environment & CLI
python -m venv .venv
source .venv/bin/activate    # On Windows: .venv\Scripts\Activate.ps1
pip install -e "packages/schemas-py" -e "packages/compat-engine" -e "packages/workspace-gen" -e "packages/cli" -e "apps/api"
```

### 2. Verify Repository Baseline

```bash
pnpm run check
```

---

## License & Maintainer

OpenRobo is open-source software licensed under the **[Apache License 2.0](LICENSE)**.

**Owner & Maintainer:** [Tanishk Singhal](https://github.com/Tanishk756)
