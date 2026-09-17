"""Workspace README generator."""

from openrobo_workspace.models import GeneratedFile, WorkspaceGenerationPlan


def generate_workspace_readme(plan: WorkspaceGenerationPlan) -> GeneratedFile:
    lines = [
        f"# {plan.stack_name} — Generated ROS 2 Workspace",
        "",
        "This robotics workspace was deterministically synthesized by the **OpenRobo Workspace Generator** (Milestone 5).",
        "",
        "## Stack Overview",
        "",
        f"- **Stack ID:** `{plan.stack_id}`",
        f"- **Description:** {plan.description or 'OpenRobo robotics stack deployment'}",
        f"- **Target ROS Distro:** `{plan.target_distro}`",
        f"- **Target OS:** `{plan.target_os}` (`{plan.target_arch}`)",
        f"- **Compatibility Verdict:** `{plan.compatibility_verdict}`",
        "",
        "## Components & Resolution",
        "",
        "| Resource ID | Name | Version | Build Type | Strategy |",
        "|---|---|---|---|---|",
    ]

    for comp in sorted(plan.components, key=lambda c: c.resource_id):
        btype = comp.build_type.value if comp.build_type else "unknown"
        lines.append(
            f"| `{comp.resource_id}` | {comp.name} | `{comp.resolved_version}` | `{btype}` | `{comp.source_strategy.value}` |"
        )

    lines.extend([
        "",
        "## Workspace Directory Layout",
        "",
        "```",
        f"{plan.workspace_name}/",
        "├── openrobo.manifest.json       # Canonical Stack Manifest",
        "├── openrobo.lock.json           # Reproducible Lockfile & Digests",
        "├── README.md                    # This documentation",
        "├── setup/",
        "│   ├── install_dependencies.sh  # APT & pip provisioning script",
        "│   ├── install_dependencies.ps1 # Windows / helper provisioning script",
        "│   └── rosdep-install.sh        # ROS dependency installer",
        "├── src/",
        f"│   └── {plan.bringup_package_name}/        # Meta / Bringup package",
        "│       ├── package.xml          # Package manifest (REP-149)",
        "│       ├── CMakeLists.txt       # ament_cmake build definition",
        "│       ├── launch/",
        "│       │   └── robot_bringup.launch.py # Composite launch file",
        "│       └── config/              # Component parameters & configs",
        "├── docker/",
        "│   ├── Dockerfile               # Multi-stage container definition",
        "│   └── docker-compose.yml       # Modular container compose services",
        "└── .devcontainer/",
        "    └── devcontainer.json        # VS Code Remote - Containers config",
        "```",
        "",
        "## Getting Started",
        "",
        "### 1. Local Linux / WSL2 Environment",
        "",
        "Ensure ROS 2 is installed and sourced on your system.",
        "",
        "```bash",
        "# 1. Install system and python dependencies",
        "chmod +x setup/*.sh",
        "./setup/install_dependencies.sh",
        "./setup/rosdep-install.sh",
        "",
        "# 2. Build the workspace",
        "colcon build --symlink-install",
        "",
        "# 3. Source the workspace",
        "source install/setup.bash",
        "",
        "# 4. Launch the bringup stack",
        f"ros2 launch {plan.bringup_package_name} robot_bringup.launch.py",
        "```",
        "",
        "### 2. Docker & Containerized Environment",
        "",
        "To build and run inside an isolated container with all dependencies pre-configured:",
        "",
        "```bash",
        "cd docker",
        "docker compose up --build",
        "```",
        "",
        "### 3. VS Code Dev Container",
        "",
        "1. Open this workspace directory in VS Code.",
        "2. When prompted, click **'Reopen in Container'** (or open Command Palette and run `Dev Containers: Reopen in Container`).",
        "3. Once loaded, the terminal is pre-configured with ROS 2 environment sourced.",
        "",
    ])

    if plan.warnings:
        lines.extend([
            "## Generation Notes & Warnings",
            "",
        ])
        for w in plan.warnings:
            lines.append(f"- ⚠️ {w}")
        lines.append("")

    if plan.unsupported_components:
        lines.extend([
            "## Generic / Manual Configuration Required",
            "",
            "The following components did not have specialized bringup adapters and have been scaffolded with placeholder configurations:",
            "",
        ])
        for u in plan.unsupported_components:
            lines.append(f"- `{u}`: See `src/{plan.bringup_package_name}/config/{u}.yaml.example` for manual parameter setup.")
        lines.append("")

    lines.extend([
        "## Provenance & Attribution",
        "",
        "All third-party components retain their upstream licenses and repositories.",
        "See `openrobo.lock.json` for full cryptographic digests, source URLs, and component licenses.",
        "",
    ])

    return GeneratedFile(path="README.md", content="\n".join(lines))
