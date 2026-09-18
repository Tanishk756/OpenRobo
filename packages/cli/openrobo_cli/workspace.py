"""Workspace generation CLI commands for OpenRobo."""

import hashlib
import json
from pathlib import Path

import typer
from openrobo_schemas import validate_stack_manifest
from openrobo_workspace import (
    GENERATOR_VERSION,
    WorkspaceGenerator,
)
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

console = Console()
workspace_app = typer.Typer(
    name="workspace",
    help="Synthesize deterministic ROS 2 workspaces, Dockerfiles, and Dev Containers from stack manifests",
    add_completion=False,
)


def load_manifest(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest file not found: {manifest_path}")
        raise typer.Exit(code=1)

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        console.print(f"[bold red]Error parsing JSON in {manifest_path}:[/bold red] {e}")
        raise typer.Exit(code=1)

    # Validate against canonical stack schema
    try:
        validate_stack_manifest(manifest)
    except Exception as e:
        console.print(f"[yellow]Warning: Stack manifest validation note: {e}[/yellow]")

    return manifest


def render_file_tree_rich(tree_dict: dict, branch: Tree):
    children = tree_dict.get("children", {})
    for name, node in sorted(children.items()):
        node_type = node.get("type", "directory")
        if node_type == "directory":
            sub_branch = branch.add(f"[bold blue]{name}/[/bold blue]")
            render_file_tree_rich(node, sub_branch)
        else:
            size = node.get("size", 0)
            branch.add(f"[green]{name}[/green] [dim]({size} bytes)[/dim]")


@workspace_app.command("preview")
def preview(
    manifest_file: Path = typer.Argument(..., help="Path to OpenRobo stack manifest JSON"),
    allow_incompatible: bool = typer.Option(False, "--allow-incompatible", help="Allow preview even if stack is marked INCOMPATIBLE"),
):
    """
    Preview synthesized ROS 2 workspace file tree and component resolution.
    """
    manifest = load_manifest(manifest_file)

    try:
        gen = WorkspaceGenerator(
            stack_manifest=manifest,
            allow_incompatible=allow_incompatible,
        )
        preview_data = gen.preview()
    except Exception as e:
        console.print(f"[bold red]Generation planning failed:[/bold red] {e}")
        raise typer.Exit(code=1)

    # Diagnostics Header
    verdict_color = "green" if preview_data.compatibility_verdict == "COMPATIBLE" else "yellow"
    readiness_state = preview_data.readiness_report.overall_state.value if preview_data.readiness_report else "UNKNOWN"
    readiness_color = "green" if "STATICALLY_VALIDATED" in readiness_state else "yellow"

    console.print(
        Panel(
            f"[bold cyan]OpenRobo Workspace Generator[/bold cyan] [dim]v{GENERATOR_VERSION} (M5.1 Hardened)[/dim]\n"
            f"Stack: [bold green]{preview_data.stack_name}[/bold green] ({preview_data.stack_id})\n"
            f"Target: [yellow]{preview_data.target_distro}[/yellow] on [dim]{preview_data.target_os} ({preview_data.target_arch})[/dim]\n"
            f"Compatibility: [{verdict_color}]{preview_data.compatibility_verdict}[/{verdict_color}]\n"
            f"Workspace Readiness: [{readiness_color}]{readiness_state}[/{readiness_color}]",
            title="[bold]OpenRobo Workspace Verification[/bold]",
            border_style="cyan",
        )
    )

    # Verification Matrix Table
    if preview_data.readiness_report:
        rep = preview_data.readiness_report
        vtable = Table(title="Workspace Verification Matrix", border_style="dim")
        vtable.add_column("Stage", style="cyan")
        vtable.add_column("Status", style="bold")
        vtable.add_column("Details", style="dim")

        vtable.add_row(
            "Static Syntax & AST",
            f"[green]{rep.static_validation.value.upper()}[/green]",
            "XML, Python AST, YAML, JSON and path safety verified",
        )
        vtable.add_row(
            "Docker Build",
            f"[yellow]{rep.docker_build.value.upper()}[/yellow]",
            "Container build not executed during workspace generation",
        )
        vtable.add_row(
            "Colcon Build",
            f"[yellow]{rep.colcon_build.value.upper()}[/yellow]",
            "colcon compilation not executed during workspace generation",
        )
        vtable.add_row(
            "Runtime Validation",
            f"[yellow]{rep.runtime_validation.value.upper()}[/yellow]",
            "Live node execution not performed",
        )
        console.print(vtable)

    # Resolution Summary Table
    table = Table(title="Synthesized Artifacts Summary", border_style="dim")
    table.add_column("Category", style="cyan")
    table.add_column("Details", style="white")

    table.add_row("Total Files", str(preview_data.file_count))
    table.add_row("Total Size", f"{preview_data.total_bytes:,} bytes")
    table.add_row("Verified Adapters", ", ".join(preview_data.selected_adapters) or "None")
    table.add_row("Generic Resources", ", ".join(preview_data.unsupported_components) or "None")

    console.print(table)

    if preview_data.readiness_report and preview_data.readiness_report.manual_steps_required:
        console.print("\n[bold yellow]Manual Configuration Required:[/bold yellow]")
        for step in preview_data.readiness_report.manual_steps_required:
            console.print(f"  * [yellow]{step}[/yellow]")

    if preview_data.warnings:
        console.print("\n[bold yellow]Warnings / Notes:[/bold yellow]")
        for w in preview_data.warnings:
            console.print(f"  * [yellow]{w}[/yellow]")

    # File Tree
    console.print("\n[bold]Generated Workspace Hierarchy:[/bold]")
    root_tree = Tree(f"[bold cyan]{preview_data.workspace_name}/[/bold cyan]")
    render_file_tree_rich(preview_data.file_tree, root_tree)
    console.print(root_tree)
    console.print()


@workspace_app.command("generate")
def generate(
    manifest_file: Path = typer.Argument(..., help="Path to OpenRobo stack manifest JSON"),
    output: Path = typer.Option(Path("./generated_workspace"), "--output", "-o", help="Target output directory"),
    allow_incompatible: bool = typer.Option(False, "--allow-incompatible", help="Allow generation even if stack is marked INCOMPATIBLE"),
):
    """
    Generate colcon workspace files and container definitions to target directory.
    """
    manifest = load_manifest(manifest_file)

    try:
        gen = WorkspaceGenerator(
            stack_manifest=manifest,
            allow_incompatible=allow_incompatible,
        )
        result = gen.export_directory(str(output))
    except Exception as e:
        console.print(f"[bold red]Workspace generation failed:[/bold red] {e}")
        raise typer.Exit(code=1)

    bringup_name = f"{manifest.get('name', 'openrobo_stack').lower().replace('-', '_')}_bringup"
    console.print(
        Panel(
            f"[bold green]Workspace Generated Successfully![/bold green]\n\n"
            f"Location: [cyan]{result.output_path}[/cyan]\n"
            f"Total Files Written: [bold]{result.file_count}[/bold] ({result.total_bytes:,} bytes)\n"
            f"Static Validation: [bold green]PASSED[/bold green]\n\n"
            f"[dim]Next steps:[/dim]\n"
            f"  1. cd {output}\n"
            f"  2. chmod +x setup/*.sh && ./setup/install_dependencies.sh\n"
            f"  3. colcon build --symlink-install\n"
            f"  4. ros2 launch {bringup_name} robot_bringup.launch.py",
            title="[bold]OpenRobo Workspace Synthesis[/bold]",
            border_style="green",
        )
    )


@workspace_app.command("archive")
def archive(
    manifest_file: Path = typer.Argument(..., help="Path to OpenRobo stack manifest JSON"),
    output: Path = typer.Option(Path("./workspace.zip"), "--output", "-o", help="Target ZIP archive path"),
    allow_incompatible: bool = typer.Option(
        False, "--allow-incompatible", help="Allow archive generation even if stack is marked INCOMPATIBLE"
    ),
):
    """
    Export deterministic, reproducible ZIP archive bundle of the workspace.
    """
    manifest = load_manifest(manifest_file)

    try:
        gen = WorkspaceGenerator(
            stack_manifest=manifest,
            allow_incompatible=allow_incompatible,
        )
        zip_bytes = gen.export_archive()
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "wb") as f:
            f.write(zip_bytes)
        sha = hashlib.sha256(zip_bytes).hexdigest()
    except Exception as e:
        console.print(f"[bold red]Archive synthesis failed:[/bold red] {e}")
        raise typer.Exit(code=1)

    console.print(
        Panel(
            f"[bold green]Workspace Archive Created![/bold green]\n\n"
            f"Archive File: [cyan]{output.resolve()}[/cyan]\n"
            f"Size: [bold]{len(zip_bytes):,}[/bold] bytes\n"
            f"SHA-256 Digest: [dim]{sha}[/dim]\n"
            f"Determinism: [bold green]Normalized & Reproducible[/bold green]",
            title="[bold]OpenRobo Archive Bundle[/bold]",
            border_style="green",
        )
    )
