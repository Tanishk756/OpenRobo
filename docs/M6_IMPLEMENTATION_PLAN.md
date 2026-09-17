# Milestone 6 — Simulation & Runtime Integration (Implementation Plan)

**Milestone:** M6 — Simulation & Runtime Integration
**Status:** PROPOSED & PLANNED (Do NOT Implement in M5.1)
**Author:** Tanishk Singhal / OpenRobo Maintainers

---

## 1. Milestone Objective

Milestone 6 expands OpenRobo from static stack design and workspace synthesis (M5.1) into **live simulation orchestration, container build verification, and runtime introspection**.

M6 transitions generated workspaces across the formal OpenRobo Readiness Continuum:

```
[ STATICALLY_VALIDATED ]   (Milestone 5.1 — Syntax, AST, XML, YAML Validated)
          ↓
[ BUILD_VERIFIED ]         (Milestone 6.1 — Headless Container & Colcon Build Verification)
          ↓
[ RUNTIME_VERIFIED ]       (Milestone 6.2 — Live Simulation, Node Heartbeat & QoS Introspection)
```

---

## 2. Core Architectural Pillars

```
+-------------------------------------------------------------------------+
|                  OpenRobo Simulation & Runtime (M6)                     |
+-------------------------------------------------------------------------+
   |                             |                          |
   v                             v                          v
[ Simulation Orchestration ]  [ Runtime Introspection ]  [ Telemetry & Bags ]
 - Gazebo (Harmonic/Fortress)  - Node / Topic Status      - Rosbag2 Ingestion
 - Webots 2024                 - QoS Profile Matching     - Latency Profiling
 - MuJoCo Physics Engine       - Rate & Drop Metrics      - Diagnostics / MCAP
```

### 2.1 Deep Simulation Adapters
- **Gazebo (Harmonic / Fortress)**:
  - World file definitions, SDF robot spawn adapters, sensor plugin mappings (`gz_sensor_plugins`).
  - Automated `ros_gz_bridge` bidirectional topic routing for LiDAR, Camera, IMU, JointStates, and CmdVel.
- **Webots**:
  - Webots robot supervisor controller, `.wbt` world generation, differential drive & arm kinematics drivers.
- **MuJoCo**:
  - MJCF XML physics model importer and fast reinforcement learning simulation bindings.

### 2.2 Container Build Execution & Colcon Verification
- Controlled container build runners executing inside Docker/Podman environments to upgrade workspace readiness from `STATICALLY_VALIDATED` to `BUILD_VERIFIED`.
- Captures compiler diagnostics, missing system dependencies, and rosdep resolution logs.

### 2.3 ROS 2 Graph Introspection & Health Monitoring
- Lightweight introspector service (`openrobo-runtime` / rclpy daemon) querying active ROS 2 computational graph:
  - Discovered active nodes, publishers, subscriptions, services, and actions.
  - QoS profile compatibility analysis (e.g. Transient Local vs Volatile, Best Effort vs Reliable).
  - Real-time message frequency and jitter measurements.
- Health status reporter displaying graph topology vs planned stack design to verify `RUNTIME_VERIFIED` status.

### 2.4 Rosbag2 Telemetry & Log Ingestion
- MCAP and SQLite3 rosbag recording orchestrator.
- Static log inspector analyzing recorded bag files for dropped frames, topic stalls, and transform (`tf2`) tree discrepancies.

---

## 3. Implementation Phasing for M6

1. **M6.1 — Build Verification Runner**: Automated headless container compilation service verifying colcon build outputs.
2. **M6.2 — Simulation Bridge & World Generation**: Generates explicit SDF / URDF / ros_gz_bridge definitions for simulation stacks.
3. **M6.3 — Live ROS Graph Introspector**: WebSocket-streamed node and topic health inspection daemon.
4. **M6.4 — Web & CLI Runtime Visualizer**: Real-time graph visualization in Next.js web studio and CLI.
