<div align="center">

# OpenRobo

**Open-source robotics platform for discovering components, reasoning about compatibility, building robot stacks, verifying builds, and inspecting runtime connections.**

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

Robotics software engineering is fragmented across hundreds of isolated repositories, disparate ROS packages, custom sensor drivers, and fragile dependency chains. Integrating a robot stackÃ¢â‚¬â€from LiDAR SLAM and arm kinematics to hardware interfaces and simulationÃ¢â‚¬â€often requires hours of manual dependency debugging.

**OpenRobo** provides a standardized, vendor-neutral software registry, intelligent compatibility engine, stack builder, automated workspace synthesis, and runtime verification platform for modern robotics:
- **Discover Components**: Search thousands of ROS 2 packages, hardware drivers, simulation models, and algorithms with weighted full-text and fuzzy typo-tolerant indexing.
- **Understand Compatibility**: Graph-based constraint validation mapping cross-package compatibility across ROS distributions, CPU architectures, and OS kernels.
- **Build Robot Stacks**: Compose modular robotics architectures with interactive dependency checking and one-click conflict resolution (`/stack-builder`).
- **Generate Workspaces**: Synthesize deterministic, reproducible Colcon workspaces, REP-149 bringup meta-packages, AST-validated launch scripts, multi-stage Dockerfiles, Dev Containers, and lockfiles (`openrobo.lock.json`).
- **Verify Builds & Introspect Runtimes**: Execute controlled colcon/container builds, compare planned stack intent against observed live ROS 2 graphs, evaluate QoS compatibility, integrate optional Connection Inspector diagnostics, and inspect telemetry (`/runtime`).

---

## Implemented Features (Available Now)

- [x] **Canonical Robotics Schemas**: JSON Schema (Draft 2020-12) standards for resource manifests (`resource.schema.json`), compatibility graphs (`graph.schema.json`), and robot stacks (`stack.schema.json`).
- [x] **Knowledge Graph & Compatibility Intelligence**: Deterministic reasoning layer evaluating ROS 2 distributions (Humble, Jazzy, Iron, Rolling), OS, CPU architecture (x86_64, aarch64), SemVer constraints, required hardware/capabilities, cycle detection, and conflict propagation with sub-50ms matrix performance.
- [x] **Zero-Extra-Infrastructure Search Engine**: PostgreSQL-backed weighted full-text search (`tsvector`, GIN indexes) with `pg_trgm` fuzzy similarity matching and multi-taxonomy faceting.
- [x] **Interactive Robotics Stack Builder**: Visual 3-panel stack composition studio (`/stack-builder`) with real-time constraint evaluation, starter templates, dependency auto-resolution proposals, and manifest import/export.
- [x] **Hardened Workspace & Deployment Generator**: Synthesizes strictly-typed, statically-validated ROS 2 colcon workspaces, launch pipelines, parameter configurations, least-privilege Dockerfiles, Docker Compose definitions, VS Code Dev Containers, setup scripts, and byte-reproducible ZIP bundles.
- [x] **Strict Generator Evidence & Safety Model**: Enforces "NO EVIDENCE Ã¢â€ â€™ NO INVENTED CONFIGURATION". Components distinguish `VERIFIED_ADAPTER`, `USER_CONFIGURED`, `METADATA_DRIVEN`, and `GENERIC_SCAFFOLD` (scaffolding `.example` templates with explicit required manual configuration steps).
- [x] **Reproducible Lockfiles & Provenance**: Generates cryptographic lockfiles (`openrobo.lock.json`) capturing component digests, repository URLs, build types, upstream licenses, evidence levels, and workspace readiness states.
- [x] **Controlled Build Verification Runner (Milestone 6)**: Pluggable execution engine (`openrobo_runtime`) supporting Docker, Podman, and Local OS providers with timeouts, working-directory constraints, environment allowlists, and exit code capture to transition workspaces from `STATICALLY_VALIDATED` to `BUILD_VERIFIED`.
- [x] **Native ROS Graph & QoS Introspection (Milestone 6)**: Machine-readable comparison of planned stack intent against observed running nodes and topics, detecting orphaned publishers/subscribers, type mismatches, and QoS incompatibilities (Reliability, Durability).
- [x] **Optional Connection Inspector Integration (Milestone 6)**: External tool adapter safely detecting installed `connection_inspector` ROS 2 packages (`inspect_cli`, GUI) via process boundary while strictly isolating GPL-3.0 upstream code from OpenRobo's Apache-2.0 core.
- [x] **Robotics Simulation Adapters (Milestone 6)**: Unified simulation interface (`SimulationAdapter`) with environment detection for Gazebo (Harmonic/Fortress), Webots, and MuJoCo.
- [x] **Rosbag2 Telemetry Foundation (Milestone 6)**: Metadata and topic message count introspection for SQLite3 rosbag datasets.
- [x] **Runtime Studio Web UI (`/runtime`) (Milestone 6 & 6.1)**: Interactive robotics dashboard visualizing execution provider states, simulator readiness, ROS 2 computational graph connections, node health, QoS diagnostics, explicit Demo Mode toggle, and real backend API streaming.
- [x] **Live Runtime Wiring & Truthful Verification (Milestone 6.1)**: Guarded ROS 2 graph collector (`rclpy` & CLI fallback), `RuntimeContract` explicit verification, `TYPE_MISMATCH` detection, LocalProcessProvider environment allowlist, and path traversal containment.
- [x] **Unified CLI**: Typer/Rich command-line suite for schema validation, static GitHub ingestion, ranked registry search, workspace generation (`openrobo workspace`), and runtime verification (`openrobo runtime`).
- [x] **Cross-Platform Compatibility**: Full first-class support for Linux, macOS, and Windows development workflows.

---

## Architecture

OpenRobo is structured as a zero-extra-infrastructure monorepo managed with **pnpm** and **Python virtual environments**:

```
OpenRobo/
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ schemas/                      # Canonical JSON Schema v2020-12 Definitions
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ resource.schema.json      # Component metadata & platform matrix schema
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ graph.schema.json         # Compatibility & dependency edge schema
Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ stack.schema.json         # Complete robot stack assembly schema
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ packages/
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ schemas/                  # Python schema validation library (openrobo-schemas)
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ compat-engine/            # Compatibility reasoning & graph engine (openrobo-compat)
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ workspace-gen/            # Hardened ROS 2 workspace generator (openrobo-workspace)
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ runtime-core/             # Runtime execution & build verification engine (openrobo-runtime)
Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ cli/                      # Typer/Rich unified CLI application (openrobo)
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ apps/
Ã¢â€â€š   Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ api/                      # FastAPI async REST API service
Ã¢â€â€š   Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ web/                      # Next.js 14 App Router interactive web frontend
Ã¢â€Å“Ã¢â€â‚¬Ã¢â€â‚¬ scripts/                      # Schema validators & seed database scripts
Ã¢â€â€Ã¢â€â‚¬Ã¢â€â‚¬ docs/                         # Architecture Decision Records & Milestone Plans
```

---

## Quickstart & Local Setup

### Prerequisites

- **Node.js**: `v20.x` or `v24.x` (CI uses Node 24)
- **pnpm**: `v12.4.2+` (`corepack enable pnpm`)
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
pip install -e "packages/schemas" -e "packages/compat-engine" -e "packages/workspace-gen" -e "packages/runtime-core" -e "packages/cli" -e "apps/api"
```

### 2. Verify Repository Baseline

```bash
pnpm run check
```

---

## Third-Party Integrations & Licensing Boundaries

OpenRobo is licensed under the **[Apache License 2.0](LICENSE)**.

When interfacing with external third-party robotics diagnostic tools licensed under copyleft terms (such as `connection_inspector`, which is **GPL-3.0-only**), OpenRobo enforces a strict **process-level boundary**:
- OpenRobo does **not** vendor, embed, or redistribute GPL source code.
- OpenRobo communicates with external tools solely via external process execution and CLI interfaces.
- For complete details, see **[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)**.

---

## License & Maintainer

OpenRobo is open-source software licensed under the **[Apache License 2.0](LICENSE)**.

**Owner & Maintainer:** [Tanishk Singhal](https://github.com/Tanishk756)
