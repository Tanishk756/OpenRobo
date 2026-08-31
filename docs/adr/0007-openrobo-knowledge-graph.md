# ADR-0007: OpenRobo Knowledge Graph Architecture

- **Status**: Accepted
- **Date**: 2026-08-31
- **Authors**: OpenRobo Architecture Team

## Context

The global robotics ecosystem consists of tightly interconnected software components, hardware devices, drivers, firmware, mathematical models, simulators, datasets, and complete robot projects. Representing these assets as isolated database rows or flat lists is insufficient to handle complex operations like multi-package compatibility validation, stack synthesis, dependency resolution, hardware-software matching, and AI-driven reasoning.

OpenRobo requires a **core architectural abstraction**: the **OpenRobo Knowledge Graph**.

## Decision

1. **Foundational Role**:
   The OpenRobo Knowledge Graph is established as the primary graph model underpinning:
   - **Robotics Discovery**: Traversed graph exploration of connected sensors, drivers, packages, and projects.
   - **Dependency Resolution**: Calculating transitive software/hardware dependency trees.
   - **Compatibility Reasoning**: Evaluating compatibility and conflict paths across software versions, operating systems, and hardware interfaces.
   - **Stack Building**: Automated composition of valid multi-layer stacks based on graph constraints.
   - **Simulation Integration**: Linking robot description models (URDF/SDF) to simulator adapters and virtual environments.
   - **AI / RAG Grounding**: Providing structured graph context for RAG queries and recommendation models.

2. **Core Predicate / Relationship Types**:
   The Knowledge Graph models directed edges (`Subject` --[`Predicate`]--> `Object`) supporting at minimum:
   - `depends-on`: Strict software or runtime dependency.
   - `optional-dependency`: Non-mandatory optional package or feature dependency.
   - `conflicts-with`: Incompatibility relationship between packages or platforms.
   - `compatible-with`: Verified or inferred compatibility claim.
   - `tested-with`: Integration test verification relation.
   - `provides`: Abstract capability or interface provision (e.g. SLAM, ROS2 controller).
   - `implements`: Implementation of an interface or standard protocol.
   - `driver-for`: Software driver providing control for hardware device.
   - `hardware-for`: Hardware component designated for a robot or system type.
   - `simulation-model-for`: Simulation asset (URDF, SDF, MJCF) representing a physical robot/sensor.
   - `simulated-by`: Robot or package supported by a specific simulator adapter (Gazebo, Webots, MuJoCo).
   - `runs-on`: OS, CPU architecture, GPU, or compute hardware execution target.
   - `requires`: System-level requirement (e.g., CUDA 12.0, Python 3.12, ROS 2 Jazzy).
   - `used-by`: Reverse usage relation.
   - `part-of`: Subsystem or component containment.
   - `alternative-to`: Functional replacement or alternative package.
   - `derived-from`: Upstream fork, port, or derived project provenance.

3. **Persistence Strategy**:
   - **PostgreSQL Normalized Relational Graph**: The graph is persisted in PostgreSQL using `graph_nodes` (Resources/Versions/Platforms) and `graph_edges` tables, indexed with B-Tree and GIN indexes.
   - **In-Memory Traversal**: For high-performance dependency tree resolutions and stack constraint checks, subgraphs are loaded into Python `NetworkX` graph instances within `packages/compat-engine`.
   - **No Dedicated Graph Database**: Neo4j, AWS Neptune, or other specialized graph databases are explicitly avoided. PostgreSQL relational storage combined with Python `NetworkX` algorithms fulfills all scale and zero-cost requirements.

## Consequences

### Positive
- Unified graph abstraction powers discovery, compatibility, stack composition, and AI RAG seamlessly.
- Strict predicate taxonomy ensures predictable, typed graph edges.
- Operates entirely within PostgreSQL without extra cloud infrastructure or graph DB licensing fees.

### Negative / Trade-offs
- Recursive graph queries over large deep graphs must use efficient SQL `WITH RECURSIVE` queries or cached in-memory NetworkX graphs to maintain sub-millisecond API response times.
