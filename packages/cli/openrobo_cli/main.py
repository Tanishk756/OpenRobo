"""OpenRobo Unified Command Line Interface."""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import typer
from openrobo_agent.cli import agent_app
from openrobo_schemas import validate_resource_manifest, validate_stack_manifest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

__version__ = "0.7.0"

app = typer.Typer(
    name="openrobo",
    help="OpenRobo CLI - Global Robotics Registry, Runtime Verification, Simulation and Fleet Control Plane.",
    add_completion=False,
)

ingest_app = typer.Typer(help="Automated resource ingestion from external robotics sources.")
runtime_app = typer.Typer(help="Runtime verification, simulation adapters, rosbag recording, and diagnostics.")
fleet_app = typer.Typer(help="Manage fleet devices, certificates, and enrollment tokens.")

app.add_typer(ingest_app, name="ingest")
app.add_typer(runtime_app, name="runtime")
app.add_typer(fleet_app, name="fleet")
app.add_typer(agent_app, name="agent")

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"[bold green]OpenRobo CLI[/bold green] version: [cyan]{__version__}[/cyan]")
        raise typer.Exit()


@app.callback()
def common(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", help="Show OpenRobo CLI version and exit.", callback=version_callback, is_eager=True
    ),
):
    """OpenRobo local-first CLI utility for discovery, manifest validation, workspace generation, and fleet management."""
    pass


# ---------------------------------------------------------------------------
# Fleet Commands
# ---------------------------------------------------------------------------
@fleet_app.command("tokens-create")
def create_token_cmd(
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Target device name"),
    ttl: int = typer.Option(60, "--ttl", "-t", help="Token TTL in minutes"),
):
    """Issue a single-use enrollment token for an edge robot device."""
    import httpx

    api_url = os.getenv("OPENROBO_API_URL", "http://localhost:8000")
    try:
        res = httpx.post(f"{api_url}/api/v1/fleet/enrollment-tokens", json={"device_name": name, "ttl_minutes": ttl})
        if res.status_code == 201:
            data = res.json()
            body = (
                f"[bold green]Created Enrollment Token[/bold green]\n\n"
                f"Token: [cyan]{data['token']}[/cyan]\n"
                f"Token ID: [dim]{data['token_id']}[/dim]\n"
                f"Expires At: [yellow]{data['expires_at']}[/yellow]\n"
                f"Target Device: {data.get('device_name') or 'Any'}"
            )
            console.print(Panel(body, title="Single-Use Token"))
        else:
            console.print(f"[bold red]Failed to create token:[/bold red] {res.text}")
    except Exception as e:
        console.print(f"[bold red]Error connecting to API ({api_url}):[/bold red] {e}")


@fleet_app.command("devices")
def list_devices_cmd():
    """List registered fleet devices with live derived status."""
    import httpx

    api_url = os.getenv("OPENROBO_API_URL", "http://localhost:8000")
    try:
        res = httpx.get(f"{api_url}/api/v1/fleet/devices")
        if res.status_code == 200:
            devices = res.json()
            table = Table(title="OpenRobo Fleet Devices", show_header=True)
            table.add_column("Device ID", style="cyan")
            table.add_column("Name", style="bold white")
            table.add_column("Domain", style="magenta")
            table.add_column("Type", style="green")
            table.add_column("Status", style="bold")
            table.add_column("Fingerprint", style="dim")
            table.add_column("Last Heartbeat", style="yellow")

            for d in devices:
                status_color = (
            "green" if d["status"] == "ONLINE"
            else "yellow" if d["status"] == "DEGRADED"
            else "red" if d["status"] == "REVOKED"
            else "dim"
        )
                table.add_row(
                    d["id"][:8] + "...",
                    d["name"],
                    d["domain"],
                    d["robot_type"],
                    f"[{status_color}]{d['status']}[/{status_color}]",
                    d["certificate_fingerprint"][:16] + "...",
                    d.get("last_heartbeat_at") or "Never",
                )
            console.print(table)
            console.print(f"Total registered devices: [bold]{len(devices)}[/bold]")
        else:
            console.print(f"[bold red]Failed to fetch devices:[/bold red] {res.text}")
    except Exception as e:
        console.print(f"[bold red]Error connecting to API ({api_url}):[/bold red] {e}")


@fleet_app.command("revoke")
def revoke_device_cmd(
    device_id: str = typer.Argument(..., help="Device UUID to revoke"),
    reason: str = typer.Option("Manual administrative revocation", "--reason", "-r", help="Revocation reason"),
):
    """Revoke an agent device certificate immediately."""
    import httpx

    api_url = os.getenv("OPENROBO_API_URL", "http://localhost:8000")
    try:
        res = httpx.post(f"{api_url}/api/v1/fleet/devices/{device_id}/revoke", json={"reason": reason})
        if res.status_code == 200:
            body = (
                f"[bold red]Device Revoked Successfully[/bold red]\n\n"
                f"Device ID: [cyan]{device_id}[/cyan]\n"
                f"Status: [red]REVOKED[/red]\n"
                f"Reason: {reason}"
            )
            console.print(Panel(body, title="Revocation Complete"))
        else:
            console.print(f"[bold red]Failed to revoke device:[/bold red] {res.text}")
    except Exception as e:
        console.print(f"[bold red]Error connecting to API ({api_url}):[/bold red] {e}")


# ---------------------------------------------------------------------------
# Runtime Commands
# ---------------------------------------------------------------------------
@runtime_app.command("providers")
def list_providers():
    """List supported execution providers (local_process, docker, podman)."""
    from openrobo_runtime import ProviderDetector

    detector = ProviderDetector()
    providers = detector.detect_all()
    table = Table(title="Execution Providers", show_header=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Details", style="dim")
    for ptype, pinfo in providers.items():
        table.add_row(ptype.value, pinfo.status.value, (pinfo.details or "")[:60])
    console.print(table)


@runtime_app.command("connection-inspector")
def connection_inspector_cmd():
    """Inspect Connection Inspector CLI status and license boundary."""
    from openrobo_runtime import ConnectionInspectorAdapter

    adapter = ConnectionInspectorAdapter()
    info = adapter.detect()
    table = Table(title="Connection Inspector Status", show_header=True)
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    is_inst = info.status.value in ("AVAILABLE", "INSTALLED")
    table.add_row("Installed", "[green]YES[/green]" if is_inst else "[yellow]NO[/yellow]")
    table.add_row("Version", info.version or "N/A")
    table.add_row("Detected Prefix", str(info.detected_prefix or "N/A"))
    table.add_row("Licensing Notice", info.licensing_notice or "External process boundary under GPL-3.0-only")
    console.print(table)


@runtime_app.command("simulators")
def list_simulators():
    """List supported simulation adapters (gazebo, webots, mujoco)."""
    from openrobo_runtime import GazeboAdapter, MujocoAdapter, WebotsAdapter

    sims = [
        ("gazebo", GazeboAdapter().detect().get("installed", False)),
        ("webots", WebotsAdapter().detect().get("installed", False)),
        ("mujoco", MujocoAdapter().detect().get("installed", False)),
    ]
    table = Table(title="Simulation Adapters", show_header=True)
    table.add_column("Simulator", style="cyan")
    table.add_column("Installed", style="green")
    for name, installed in sims:
        table.add_row(name, "[green]AVAILABLE[/green]" if installed else "[dim]NOT INSTALLED[/dim]")
    console.print(table)


@runtime_app.command("build-verify")
def build_verify_cmd(
    workspace_dir: Path = typer.Argument(..., help="Path to workspace directory"),
):
    """Run colcon build verification on a workspace."""
    from openrobo_runtime import BuildRunner

    runner_inst = BuildRunner()
    res = runner_inst.verify_build(workspace_dir)
    status_str = "[green]SUCCESS[/green]" if res.status.value == "SUCCESS" else "[red]FAILED[/red]"
    console.print(Panel(f"Build Result: {status_str}\nDuration: {res.duration_seconds:.2f}s", title="Build Verification"))


@runtime_app.command("rosbag")
def rosbag_cmd(
    output_dir: Path = typer.Option(Path("./bags"), "--output-dir", "-o", help="Output directory"),
    duration_sec: int = typer.Option(5, "--duration", "-d", help="Recording duration in seconds"),
):
    """Record ROS 2 bag evidence for runtime verification."""
    from openrobo_runtime import RosbagInspector

    _ = RosbagInspector()
    console.print(f"[green]Rosbag inspector initialized for {output_dir}[/green]")


# ---------------------------------------------------------------------------
# Search, Validate, Ingest, Info
# ---------------------------------------------------------------------------
@app.command("search")
def search(
    query: Optional[str] = typer.Argument(None, help="Keywords to search resources."),
    resource_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by resource type"),
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Filter by robotics domain"),
    capability: Optional[str] = typer.Option(None, "--capability", "-c", help="Filter by capability"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results to display"),
    seed_file: Optional[Path] = typer.Option(None, "--seed-file", "-s", help="Path to seed resources JSON for offline search"),
):
    """Search the OpenRobo registry using full-text and fuzzy relevance ranking."""
    from apps.api.models.resource import ResourceModel
    from apps.api.services.search.ranking import calculate_relevance_score
    from apps.api.services.search.search_service import SearchService

    seed_path = seed_file or Path("samples/seed_resources.json")
    resources = []
    if seed_path.exists():
        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data:
                res = ResourceModel(
                    id=item["id"],
                    name=item["name"],
                    type=item.get("type", "software"),
                    summary=item.get("summary"),
                    description=item.get("description"),
                    spdx_license_id=item.get("license", {}).get("spdx_id", "NOASSERTION"),
                    repo_url=item.get("source", {}).get("repo_url"),
                    robotics_domains=item.get("robotics_domains", []),
                    capabilities=item.get("capabilities", []),
                    platforms=item.get("platforms", {}),
                    evidence_level=item.get("evidence", {}).get("level", "unknown"),
                )
                resources.append(res)
        except Exception as e:
            console.print(f"[yellow]Warning: Could not load local seed data: {e}[/yellow]")

    tokens = SearchService._tokenize(query) if query else []
    scored = []
    for r in resources:
        if resource_type and r.type.lower() != resource_type.lower():
            continue
        if domain and not any(domain.lower() in d.lower() for d in (r.robotics_domains or [])):
            continue
        if capability and not any(capability.lower() in c.lower() for c in (r.capabilities or [])):
            continue

        if query:
            score, highlight = calculate_relevance_score(r, tokens, query, enable_fuzzy=True)
            if score > 0:
                scored.append((r, score, highlight))
        else:
            scored.append((r, 1.0, None))

    scored.sort(key=lambda x: (-x[1], x[0].name.lower()))
    results = scored[:limit]

    title = f"Search Results for '{query}'" if query else "OpenRobo Registry Resources"
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Score", style="yellow", justify="right", width=7)
    table.add_column("Resource ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Domains", style="green")
    table.add_column("License", style="dim")
    table.add_column("Summary", style="white")

    for r, score, _ in results:
        domains_str = ", ".join(r.robotics_domains or [])[:24]
        summary_str = (r.summary or "")[:50] + ("..." if len(r.summary or "") > 50 else "")
        table.add_row(f"{score:.2f}", r.id, r.type, domains_str, r.spdx_license_id, summary_str)

    console.print(table)
    console.print(f"\nFound [bold]{len(scored)}[/bold] matching robotics resources.")


@app.command("validate")
def validate(
    file_path: Path = typer.Argument(..., help="Path to JSON manifest file to validate."),
    manifest_type: str = typer.Option("resource", "--type", "-t", help="Manifest type: 'resource' or 'stack'"),
):
    """Validate a local JSON resource or stack manifest against canonical OpenRobo schemas."""
    if not file_path.exists():
        console.print(f"[bold red]Error:[/bold red] File not found at path '{file_path}'")
        raise typer.Exit(code=1)

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if manifest_type == "stack":
            valid, errors = validate_stack_manifest(data)
        else:
            valid, errors = validate_resource_manifest(data)

        if valid:
            console.print(Panel(f"[bold green]SUCCESS:[/bold green] Manifest '{file_path.name}' is valid!", title="Validation Result"))
        else:
            console.print(f"[bold red]FAILED:[/bold red] Manifest '{file_path.name}' has validation errors:")
            for err in errors:
                console.print(f"  - [red]{err}[/red]")
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]Exception occurred:[/bold red] {e}")
        raise typer.Exit(code=1)


@ingest_app.command("github")
def ingest_github(
    repository_url: str = typer.Argument(..., help="Public GitHub repository URL (e.g. https://github.com/ros-navigation/navigation2)"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Optional directory to save generated manifest files."),
):
    """Inspect a public GitHub robotics repository and generate canonical OpenRobo resource manifests."""
    from apps.api.services.ingestion.github_client import GitHubClient, validate_and_parse_github_url
    from apps.api.services.ingestion.manifest_builder import build_candidate_manifests
    from apps.api.services.ingestion.repository_inspector import RepositoryInspector

    console.print(f"[bold cyan]OpenRobo Ingestion Engine[/bold cyan] analyzing [underline]{repository_url}[/underline]...")

    async def _run():
        owner, repo = validate_and_parse_github_url(repository_url)
        client = GitHubClient()
        inspector = RepositoryInspector(client)
        evidence = await inspector.inspect_repository(owner, repo)
        candidates = build_candidate_manifests(evidence)
        return evidence, candidates

    try:
        evidence, candidates = asyncio.run(_run())
    except Exception as e:
        console.print(f"[bold red]Ingestion Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    table = Table(title=f"Discovered Resources for {evidence.owner}/{evidence.repo}")
    table.add_column("Resource ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("Version", style="green")
    table.add_column("License", style="yellow")
    table.add_column("Validation", style="bold")

    saved_paths = []
    for cand in candidates:
        valid, errors = validate_resource_manifest(cand)
        val_status = "[green]VALID[/green]" if valid else f"[red]INVALID ({len(errors)} errs)[/red]"
        table.add_row(cand["id"], cand["type"], cand["version"], cand.get("license", {}).get("spdx_id", "NOASSERTION"), val_status)
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
            out_file = output_dir / f"{cand['id'].replace('/', '_')}.json"
            out_file.write_text(json.dumps(cand, indent=2), encoding="utf-8")
            saved_paths.append(out_file)

    console.print(table)
    console.print(f"\n[bold green]Success:[/bold green] Discovered [bold]{len(candidates)}[/bold] canonical resource candidates.")
    if saved_paths:
        console.print(f"Saved {len(saved_paths)} manifest files to [cyan]{output_dir}[/cyan].")


@app.command("info")
def info():
    """Display current OpenRobo CLI environment information."""
    console.print("[bold cyan]OpenRobo Infrastructure Platform[/bold cyan]")
    console.print(f"CLI Version: {__version__}")
    console.print("License: Apache-2.0")
    console.print("Status: Local-first offline mode ready.")


if __name__ == "__main__":
    app()
