# Stack Builder

Users describe a robot/application and select constraints.

Example:
- domain: UGV
- goal: autonomous indoor navigation
- compute: ARM64 SBC
- sensors: LiDAR + IMU + camera
- simulator: Gazebo

The builder resolves candidate components, shows compatibility, exposes conflicts, and exports a reproducible stack manifest.

The builder must allow manual overrides and must explain why each component was selected.
