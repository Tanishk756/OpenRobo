"""OpenRobo CLI Runtime Commands (Milestone 6)."""

from pathlib import Path
from typing import Optional

import typer
from openrobo_runtime import (
    BuildRunner,
    ConnectionInspectorAdapter,
    ExecutionProviderType,
    GazeboAdapter,
    MujocoAdapter,
    ProviderDetector,
    RosbagInspector,
    WebotsAdapter,
)
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

runtime_app = typer.Typer(
    name="runtime",
    help="Runtime verification, simulation adapters, and connection introspection.",
)
console = Console()


@runtime_app.command("providers")
def list_providers():
    """List available containerized and local build execution providers."""
    detector = ProviderDetector()
    results = detector.detect_all()

    table = Table(title="OpenRobo Execution Providers", show_header=True, header_style="bold cyan")
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Status", style="bold")
    table.add_column("Version", style="green")
    table.add_column("Details", style="dim")

    for _key, p in results.items():
        status_color = "[green]AVAILABLE[/green]" if p.status.value == "AVAILABLE" else f"[yellow]{p.status.value}[/yellow]"
        table.add_row(p.provider_type.value, status_color, p.version or "N/A", p.details or "")

    console.print(table)


@runtime_app.command("build-verify")
def build_verify(
    workspace_dir: Path = typer.Argument(..., help="Path to generated workspace directory"),
    distro: str = typer.Option("humble", "--distro", "-d", help="Target ROS 2 distribution"),
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Execution provider: docker, podman, local_process"),
    timeout: int = typer.Option(300, "--timeout", "-t", help="Execution timeout in seconds"),
):
    """Run controlled build verification on a generated workspace."""
    if not workspace_dir.exists():
        console.print(f"[bold red]Error:[/bold red] Directory '{workspace_dir}' does not exist.")
        raise typer.Exit(code=1)

    prov_type = None
    if provider:
        try:
            prov_type = ExecutionProviderType(provider.lower())
        except ValueError:
            console.print(f"[bold red]Error:[/bold red] Unknown provider '{provider}'. Choose from docker, podman, local_process.")
            raise typer.Exit(code=1)

    runner = BuildRunner()
    console.print(f"[cyan]Running build verification for '{workspace_dir}'...[/cyan]")
    res = runner.verify_workspace_build(
        workspace_dir=str(workspace_dir),
        target_distro=distro,
        requested_provider=prov_type,
        timeout_sec=timeout,
    )

    color = "green" if res.status.value == "PASSED" else "red"
    console.print(
        Panel(
            f"[bold {color}]Status: {res.status.value}[/bold {color}]\n"
            f"Provider: {res.provider.value}\n"
            f"Duration: {res.duration_ms:.1f} ms\n"
            f"Docker Build: {res.docker_build_status}\n"
            f"Colcon Build: {res.colcon_status}\n"
            f"Errors: {len(res.errors)} | Warnings: {len(res.warnings)}",
            title="Build Verification Result",
        )
    )

    if res.errors:
        console.print("[bold red]Errors:[/bold red]")
        for err in res.errors:
            console.print(f"  - [red]{err}[/red]")


@runtime_app.command("connection-inspector")
def connection_inspector(
    distro: Optional[str] = typer.Option(None, "--distro", "-d", help="Target ROS 2 distribution"),
):
    """Check external Connection Inspector status and licensing boundary."""
    adapter = ConnectionInspectorAdapter()
    report = adapter.detect(target_distro=distro)

    table = Table(title="Connection Inspector Status", show_header=True, header_style="bold cyan")
    table.add_column("Property", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    st_str = f"[green]{report.status.value}[/green]" if report.status.value == "INSTALLED" else f"[yellow]{report.status.value}[/yellow]"
    table.add_row("Status", st_str)
    table.add_row("Detected Prefix", report.detected_prefix or "None")
    table.add_row("Version", report.version or "None")
    table.add_row("Executables", ", ".join(report.executables) if report.executables else "None")
    table.add_row("Licensing Notice", f"[bold yellow]{report.licensing_notice}[/bold yellow]")

    console.print(table)


@runtime_app.command("simulators")
def simulators():
    """List detected robotics simulators (Gazebo, Webots, MuJoCo)."""
    gz = GazeboAdapter().detect()
    wb = WebotsAdapter().detect()
    mj = MujocoAdapter().detect()

    table = Table(title="Simulation Adapters", show_header=True, header_style="bold cyan")
    table.add_column("Simulator", style="cyan", no_wrap=True)
    table.add_column("Installed", style="bold")
    table.add_column("Version", style="green")
    table.add_column("Details", style="dim")

    for sim in [gz, wb, mj]:
        inst_str = "[green]YES[/green]" if sim.get("installed") else "[yellow]NO[/yellow]"
        table.add_row(sim.get("simulator", "unknown"), inst_str, sim.get("version") or "N/A", sim.get("details", ""))

    console.print(table)


@runtime_app.command("rosbag")
def inspect_bag(
    bag_path: Path = typer.Argument(..., help="Path to rosbag2 directory or SQLite3 .db3 file"),
):
    """Inspect rosbag2 storage metadata and topic metrics."""
    if not bag_path.exists():
        console.print(f"[bold red]Error:[/bold red] Rosbag path '{bag_path}' does not exist.")
        raise typer.Exit(code=1)

    res = RosbagInspector.inspect_bag_directory(str(bag_path))
    if "error" in res:
        console.print(f"[bold red]Rosbag Inspection Error:[/bold red] {res['error']}")
        raise typer.Exit(code=1)

    table = Table(title=f"Rosbag Information ({bag_path.name})", show_header=True, header_style="bold cyan")
    table.add_column("Topic", style="cyan", no_wrap=True)
    table.add_column("Message Type", style="magenta")
    table.add_column("Message Count", style="green", justify="right")

    for t in res.get("topics", []):
        table.add_row(t.get("name", ""), t.get("type", ""), str(t.get("message_count", 0)))

    console.print(table)
    summary_line = (
        f"Total Messages: [bold]{res.get('message_count', 0)}[/bold] | "
        f"Duration: [bold]{res.get('duration_sec', 0.0):.2f}s[/bold] | "
        f"Storage: [bold]{res.get('storage_identifier', 'unknown')}[/bold]"
    )
    console.print(summary_line)
