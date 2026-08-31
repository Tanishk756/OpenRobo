# OpenRobo — Master Specification

## Vision
OpenRobo is a free, open-source, vendor-neutral infrastructure platform for the global robotics ecosystem.

It connects existing open-source robotics software, hardware, simulation, AI, datasets, designs, documentation, and complete robot projects in one place.

Core journey:

**Discover → Understand → Build → Simulate → Deploy → Contribute**

## Non-negotiable requirements
1. OpenRobo itself is open source.
2. Core functionality is free to users.
3. Architecture supports all robotics domains from day one.
4. Existing projects retain their original ownership and licenses.
5. The platform must not require a single vendor, cloud, or AI provider.
6. Local-first workflows are first-class.
7. The system must be extensible through open schemas and APIs.
8. Compatibility must be explicit and explainable.
9. Reproducibility and dependency traceability are first-class concerns.
10. Security and license compliance must be designed in from the beginning.

## Domains
Aerial, ground, marine, underwater, manipulation, humanoid, legged, industrial, medical/research, space, swarm/multi-agent, and future user-defined domains.

## Resource types
Software, hardware, robot, firmware, driver, dataset, AI model, simulation, environment, CAD, PCB, documentation, tutorial, paper, benchmark, and complete project.

## Core modules
- Registry
- Search/discovery
- Project/resource pages
- Metadata and schemas
- Compatibility engine
- Dependency graph
- Stack builder
- Workspace generator
- CLI
- Simulation integrations
- Deployment integrations
- Community/contribution system
- AI abstraction layer
- API/SDK

## Architectural rule
OpenRobo should integrate and federate existing ecosystems rather than fork or absorb them.

## MVP
The first production foundation must support resource discovery, standardized metadata, project pages, search, submissions, compatibility metadata, basic stack composition, API access, CLI access, and local execution.
