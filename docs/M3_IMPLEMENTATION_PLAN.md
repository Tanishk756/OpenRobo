# Milestone 3 Implementation Plan: Knowledge Graph & Compatibility Intelligence

## Objective
Implement **Milestone 3 — Knowledge Graph, Compatibility Intelligence & Constraint Reasoning** in OpenRobo. Build the reasoning engine that evaluates whether robotics packages, drivers, algorithms, hardware interfaces, and platform environments can function together without breaking.

---

## 1. Scope & Core Capabilities

### 1.1 Knowledge Graph Predicates
Implement bidirectional graph evaluation for canonical relationship edges defined in `schemas/graph.schema.json`:
- `DEPENDS_ON`: Direct package or system library dependency.
- `COMPATIBLE_WITH`: Confirmed bidirectional compatibility.
- `INCOMPATIBLE_WITH`: Hard conflict (e.g. incompatible API versions or conflicting message types).
- `RUNS_ON`: Target OS or CPU architecture requirement (e.g. Ubuntu 24.04 on aarch64).
- `SUPPORTS`: Platform / hardware support (e.g. ROS 2 Jazzy, Gazebo Harmonic).
- `REQUIRES`: Hardware or driver prerequisite (e.g. LiDAR hardware driver, CUDA runtime).
- `PROVIDES`: Interface capability (e.g. `/cmd_vel` geometry_msgs, Nav2 plugin).
- `TESTED_WITH`: Verified integration test pair.

### 1.2 Constraint Reasoning Engine (`packages/compat-engine`)
- **Compatibility Matrix Generator**: Compute full compatibility matrix given a candidate list of resources.
- **Rule Evaluator**:
  - ROS distribution compatibility (e.g. Jazzy vs Humble).
  - Operating system & kernel compatibility (Ubuntu 24.04, Debian Bookworm, Windows 11).
  - CPU architecture compatibility (x86_64, aarch64, armv7l).
  - Semantic version constraint matching (SemVer ranges `^4.0.0`, `>=2.1.0,<3.0.0`).
- **Conflict Explainer**: Provide actionable human-readable explanations when conflicts occur:
  - *Example*: `"nav2_bringup (v1.3.0) requires ros_version == 'Jazzy', but active environment specifies 'Humble'."*
  - *Example*: `"realsense2_camera (v4.54.1) conflicts with librealsense2 (< 2.50.0)."`

### 1.3 Graph & Compatibility REST APIs
- `GET /api/v1/graph/edges`: Query relationship edges between resources.
- `POST /api/v1/graph/edges`: Register new verified compatibility edges.
- `POST /api/v1/compatibility/evaluate`: Evaluate compatibility for a candidate set of resources against target platform constraints.
- `GET /api/v1/compatibility/matrix`: Retrieve compatibility matrix for a specific robotics domain or robot model.

### 1.4 Web UI Graph & Compatibility Visualizer
- **Compatibility Matrix View**: Interactive grid view on `/resources/[id]` showing tested ROS distros, platforms, and compatible companion packages.
- **Conflict Callout Badges**: Red/amber status badges indicating verified compatibility vs known incompatibilities.
- **Evidence Level Tracking**: Visual indicator displaying whether compatibility was verified via `ci_verified`, `vendor_tested`, `community_reported`, or `inferred`.

---

## 2. Deliverables & Milestones Breakdown

### Phase 1: Database & Model Extensions
- Alembic migration for graph edge indexes and fast adjacency lookups.
- SQLAlchemy repository methods for multi-hop graph traversals.

### Phase 2: Engine Implementation (`packages/compat-engine`)
- `compat_engine/engine.py`: Core constraint solver and path finder.
- `compat_engine/rules.py`: Declarative rule definitions for ROS, OS, and hardware constraints.
- `compat_engine/explainer.py`: Human-readable diagnostics generator.

### Phase 3: REST API Routers
- `apps/api/routers/graph.py`: Graph edge CRUD and querying.
- `apps/api/routers/compatibility.py`: Batch evaluation endpoint.

### Phase 4: Frontend Integration
- Add Compatibility Matrix tab to Resource Detail Drawer.
- Visual dependency graph component.

### Phase 5: Testing & Verification
- Unit tests for constraint solver (cycle detection, transitive dependency resolution, conflict isolation).
- Integration tests against seed robotics dataset.
- Vitest UI component tests.

---

## 3. Success Metrics
- 100% test coverage on compatibility constraint resolution algorithms.
- Sub-50ms evaluation time for 50-node candidate stacks.
- Deterministic conflict explanations for all constraint failures.
