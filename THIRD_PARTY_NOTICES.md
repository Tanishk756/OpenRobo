# Third-Party Notices & External Tool Integrations

OpenRobo is licensed under the **Apache License, Version 2.0**.

This document describes external tools and third-party projects with which OpenRobo provides optional integration boundaries.

---

## 1. Connection Inspector (Optional External Tool)

- **Upstream Project**: `connection_inspector` / `connection_inspector-release`
- **Maintainer / Creator**: Dyno Robotics
- **Upstream License**: **GNU General Public License v3.0 (GPL-3.0-only)**
- **Integration Boundary**: External Process / CLI Execution Only

### OpenRobo Licensing & Isolation Policy:
1. **No Source Vendoring**: OpenRobo does **not** copy, vendor, or redistribute upstream `connection_inspector` C++ source code or binary libraries in this repository.
2. **No Static/Dynamic Linking**: OpenRobo packages are strictly Apache-2.0 and do not statically or dynamically link GPL-3.0-only code.
3. **Process-Level Boundary**: OpenRobo interacts with `connection_inspector` exclusively by detecting whether the package is installed in the user's local ROS environment (`ros2 pkg prefix connection_inspector`) and running safe external process commands (`inspect_cli` or GUI launch) on explicit user request.
4. **Independent Native Reasoning**: OpenRobo maintains its own native, machine-readable ROS 2 graph introspection, QoS matrix comparison, and stack verification engine (`openrobo_runtime`), treating Connection Inspector as an optional external specialist tool.

---

## 2. Robotics Simulators

OpenRobo integrates with robotics simulation environments via command-line adapters and file-generation bridges:
- **Gazebo (Harmonic / Fortress)**: Apache-2.0 / Open Source Robotics Foundation (OSRF)
- **Webots**: Apache-2.0 / Cyberbotics
- **MuJoCo**: Apache-2.0 / Google DeepMind
