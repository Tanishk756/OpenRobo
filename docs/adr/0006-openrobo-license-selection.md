# ADR-0006: OpenRobo Project License Selection (Apache-2.0)

- **Status**: Accepted
- **Date**: 2026-08-31
- **Authors**: OpenRobo Architecture Team

## Context

OpenRobo requires an open-source license for its core platform codebase (monorepo apps, packages, schemas, API, CLI, and compatibility engine).

Requirements:
1. OpenRobo's own code is licensed under Apache-2.0.
2. Upstream resources retain their own licenses and copyright ownership.
3. License compatibility must be evaluated for each specific integration/distribution scenario. OpenRobo does NOT claim blanket compatibility between Apache-2.0 and every GPL-3.0 distribution scenario.
4. OpenRobo must preserve upstream attribution, notices, and license requirements.
5. OpenRobo does not provide legal advice.

## Dependency and License Compatibility Analysis

We evaluated the primary open-source software license families:

| License Option | Permissive | Patent Grant | Corporate / Industry Adoption | Ecosystem Interoperability | Recommendation |
|---|---|---|---|---|---|
| **Apache License 2.0** | Yes | **Yes (Explicit)** | **Very High** | High alignment with ROS 2 & Gazebo ecosystems | **SELECTED** |
| **MIT License** | Yes | No (Implicit) | Very High | Broad compatibility | Secondary Choice |
| **GNU GPL v3.0** | Copyleft | Yes | Limited / High Friction | Strong copyleft restricts commercial integration in some contexts | Rejected for Core |
| **AGPL v3.0** | Network Copyleft | Yes | Low | High friction for cloud API hostings | Rejected for Core |

### Key Principles & Caveats:
1. **Explicit Patent License**: Apache-2.0 includes an express grant of patent rights (Section 3) and an automatic patent termination clause if a party initiates patent litigation against any contributor. This is critical for robotics platforms involving hardware-software interfaces and autonomous systems.
2. **Ecosystem Interoperability**: Apache-2.0 is the default license for ROS 2 (`rclcpp`, `rclpy`, `ros2_control`) and Gazebo Sim. Adopting Apache-2.0 ensures seamless alignment with the modern ROS 2 ecosystem.
3. **No Blanket Compatibility Claims**: License compatibility depends on how components are linked, combined, or distributed. For example, distributing Apache-2.0 source code combined with GPL-3.0 components creates downstream distribution constraints under GPL-3.0 rules. OpenRobo does NOT declare blanket compatibility across all license combinations.
4. **Metadata Registry Policy**: OpenRobo is a metadata and provenance registry (not a code mirror). Indexing GPL, BSD, MIT, or proprietary packages does not alter or supersede upstream license terms.
5. **No Legal Advice**: Compatibility evaluations provided by OpenRobo are informational heuristics and do not constitute professional legal counsel.

## Decision

We select **Apache License 2.0** as the official project license for OpenRobo's core codebase.

The repository root includes the standard Apache License 2.0 text (`LICENSE`), `LICENSE_PLACEHOLDER.md` has been updated with legal caveats, and all package manifests specify `"license": "Apache-2.0"`.

## Consequences

### Positive
- Clear, standardized permissive licensing with explicit patent protections for all contributors.
- Direct ecosystem alignment with ROS 2, Gazebo, and modern robotics foundations.
- Enables broad adoption by researchers, startups, educational institutions, and commercial robotics developers.

### Negative / Trade-offs
- Downstream redistributors of modified OpenRobo source files must retain copyright notices and state modifications as required by Apache-2.0 Section 4.
