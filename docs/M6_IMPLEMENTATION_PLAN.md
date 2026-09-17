# Milestone 6 — Simulation & Runtime Integration (Implementation Plan)

**Milestone:** M6 — Simulation & Runtime Integration  
**Status:** PROPOSED & PLANNED (Do NOT Implement in M5)  
**Author:** OpenRobo Maintainers  

---

## 1. Milestone Objective

Milestone 6 expands OpenRobo from static stack design and workspace synthesis into **live simulation orchestration and runtime introspection**. M6 bridges generated colcon workspaces with actual execution engines (Gazebo, Webots, MuJoCo) and provides live health and telemetry monitoring for running ROS 2 computation graphs.

---

## 2. Core Architectural Pillars

```
+-------------------------------------------------------------+
|             OpenRobo Simulation & Runtime (M6)               |
+-------------------------------------------------------------+
   |                             |                          |
   v                             v                          v
[ Simulation Adapters ]  [ Graph Introspection ]  [ Telemetry & Bags ]
 - Gazebo (Harmonic)       - Node / Topic Status     - Rosbag2 Ingestion
 - Webots 2024             - QoS Profile Matching    - Latency Profiling
 - MuJoCo Physics          - Rate & Drop Metrics     - Diagnostics / MCAP
```

### 2.1 Deep Simulation Adapters
- **Gazebo (Harmonic / Fortress)**:
  - World file definitions, SDF robot spawn adapters, sensor plugin mappings (`gz_sensor_plugins`).
  - Automated `ros_gz_bridge` bidirectional topic routing for LiDAR, Camera, IMU, JointStates, and CmdVel.
- **Webots**:
  - Webots robot supervisor controller, `.wbt` world generation, differential drive & arm kinematics drivers.
- **MuJoCo**:
  - MJCF XML physics model importer and fast reinforcement learning simulation bindings.

### 2.2 ROS 2 Graph Introspection & Health Monitoring
- Lightweight introspector service (`openrobo-runtime` / rclpy daemon) querying active ROS 2 computational graph:
  - Discovered active nodes, publishers, subscriptions, services, and actions.
  - QoS profile compatibility analysis (e.g. Transient Local vs Volatile, Best Effort vs Reliable).
  - Real-time message frequency and jitter measurements.
- Health status reporter displaying graph topology vs planned stack design.

### 2.3 Rosbag2 Telemetry & Log Ingestion
- MCAP and SQLite3 rosbag recording orchestrator.
- Static log inspector analyzing recorded bag files for dropped frames, topic stalls, and transform (`tf2`) tree discrepancies.

---

## 3. Package Structure (Proposed)

```
packages/simulation-adapters/
    openrobo_sim/
        __init__.py
        models.py
        gazebo/
            world_builder.py
            bridge_router.py
            sdf_spawner.py
        webots/
            world_builder.py
            supervisor.py
        mujoco/
            mjcf_importer.py

packages/runtime-monitor/
    openrobo_runtime/
        __init__.py
        introspection.py
        qos_checker.py
        diagnostics.py
        bag_inspector.py
```

---

## 4. Phased Implementation Roadmap

1. **Phase 1: Simulation Abstraction Model**: Define `SimulationAdapter` base interface and environment target models.
2. **Phase 2: Gazebo Deep Integration**: Implement automated SDF world builder and `ros_gz_bridge` YAML synthesizers.
3. **Phase 3: Webots & MuJoCo Bridges**: Add Webots supervisor driver and MuJoCo physics importer.
4. **Phase 4: Runtime Introspection Service**: Build rclpy-based graph inspector querying running ROS nodes and QoS mismatches.
5. **Phase 5: Rosbag Telemetry Engine**: Ingest and profile MCAP bags with diagnostic metrics.
6. **Phase 6: Web Studio Runtime Tab**: Live graph viewer and health dashboard in Next.js web application.

---

## 5. Non-Goals for Milestone 6
- Live cloud fleet deployment (reserved for M7+).
- Proprietary simulation platforms (Isaac Sim deep proprietary bindings will follow after open standards).