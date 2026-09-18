"""Workspace README generator."""

from openrobo_workspace.models import GeneratedFile, WorkspaceGenerationPlan


def generate_workspace_readme(plan: WorkspaceGenerationPlan) -> GeneratedFile:
    m_name = plan.maintainer.name if plan.maintainer else "OpenRobo User"
    m_email = f" <{plan.maintainer.email}>" if (plan.maintainer and plan.maintainer.email) else " *(Email not specified)*"
    maintainer_display = f"{m_name}{m_email}"

    lines = [
        f"# {plan.stack_name} — Generated ROS 2 Workspace",
        "",
        "This robotics workspace was deterministically synthesized by the **OpenRobo Workspace Generator** (Milestone 5.1 Hardened).",
        "",
        "## Stack Overview",
        "",
        f"- **Stack ID:** `{plan.stack_id}`",
        f"- **Description:** {plan.description or 'OpenRobo robotics stack deployment'}",
        f"- **Target ROS Distro:** `{plan.target_distro}`",
        f"- **Target OS:** `{plan.target_os}` (`{plan.target_arch}`)",
        f"- **Compatibility Verdict:** `{plan.compatibility_verdict}`",
        f"- **Maintainer:** {maintainer_display}",
        "",
        "## Workspace Readiness & Verification Status",
        "",
        "| Verification Stage | Status | Notes |",
        "|---|---|---|",
        f"| **Static Analysis** | `{plan.readiness_report.static_validation.value.upper()}` | Syntax, XML, and YAML verified |",
        f"| **Docker Build** | `{plan.readiness_report.docker_build.value.upper()}` | Container build not executed in generator |",
        f"| **Colcon Build** | `{plan.readiness_report.colcon_build.value.upper()}` | Compilation not executed in generator |",
        f"| **Runtime Validation** | `{plan.readiness_report.runtime_validation.value.upper()}` | Live node execution not performed |",
        f"| **Overall Readiness** | **`{plan.readiness_report.overall_state.value}`** | |",
        "",
        "## Components & Generation Evidence",
        "",
        "Every generated component artifact is backed by an explicit evidence level (no guessed or invented configuration):",
        "",
        "| Resource ID | Name | Version | Strategy | Evidence Level | Adapter |",
        "|---|---|---|---|---|---|",
    ]

    for comp in sorted(plan.components, key=lambda c: c.resource_id):
        ev_level = comp.evidence.level.value if comp.evidence else "UNKNOWN"
        if comp.evidence and comp.evidence.adapter_id:
            adapter_str = f"{comp.adapter_name} (v{comp.evidence.adapter_version})"
        else:
            adapter_str = "None (Scaffold)"
        lines.append(
            f"| `{comp.resource_id}` | {comp.name} | `{comp.resolved_version}` | "
            f"`{comp.source_strategy.value}` | `{ev_level}` | {adapter_str} |"
        )

    if plan.readiness_report.manual_steps_required:
        lines.extend(
            [
                "",
                "## Required Manual Configuration Steps",
                "",
                "> [!IMPORTANT]",
                "> The following configuration steps must be performed before building or running this workspace:",
                "",
            ]
        )
        for step in plan.readiness_report.manual_steps_required:
            lines.append(f"- [ ] {step}")

    lines.extend(
        [
            "",
            "## Workspace Directory Layout",
            "",
            "```",
            f"{plan.workspace_name}/",
            "├── openrobo.manifest.json       # Canonical Stack Manifest",
            "├── openrobo.lock.json           # Reproducible Lockfile & Evidence Hashes",
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
            "To build and run inside an isolated container with least-privilege security settings:",
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
        ]
    )

    if plan.warnings:
        lines.extend(
            [
                "## Generation Notes & Warnings",
                "",
            ]
        )
        for w in plan.warnings:
            lines.append(f"- ⚠️ {w}")
        lines.append("")

    lines.extend(
        [
            "## Provenance & Attribution",
            "",
            "All third-party components retain their upstream licenses and repositories.",
            "See `openrobo.lock.json` for full cryptographic digests, source URLs, and component licenses.",
            "",
        ]
    )

    return GeneratedFile(path="README.md", content="\n".join(lines))
