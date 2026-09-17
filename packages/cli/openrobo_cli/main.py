import asyncio
import json
from pathlib import Path
from typing import Optional

import typer
from openrobo_schemas import validate_resource_manifest, validate_stack_manifest
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from openrobo_cli.workspace import workspace_app

__version__ = "0.5.0"

app = typer.Typer(name="openrobo", help="OpenRobo CLI — Open-Source Global Robotics Commons Tool", add_completion=False)
ingest_app = typer.Typer(name="ingest", help="Ingest open-source robotics repositories into OpenRobo manifests", add_completion=False)
app.add_typer(ingest_app, name="ingest")
app.add_typer(workspace_app, name="workspace")

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
    """
    OpenRobo local-first CLI utility for discovery, manifest validation, and workspace generation.
    """
    pass


@app.command("search")
def search(
    query: Optional[str] = typer.Argument(None, help="Search terms (e.g. 'nav2', 'slam', 'realsense')"),
    resource_type: Optional[str] = typer.Option(None, "--type", "-t", help="Filter by resource type"),
    domain: Optional[str] = typer.Option(None, "--domain", "-d", help="Filter by robotics domain"),
    capability: Optional[str] = typer.Option(None, "--capability", "-c", help="Filter by capability"),
    limit: int = typer.Option(20, "--limit", "-l", help="Maximum results to display"),
    seed_file: Optional[Path] = typer.Option(None, "--seed-file", "-s", help="Path to seed resources JSON for offline search"),
):
    """
    Search the OpenRobo registry using full-text and fuzzy relevance ranking.
    """
    from apps.api.models.resource import ResourceModel
    from apps.api.services.search.ranking import calculate_relevance_score
    from apps.api.services.search.search_service import SearchService

    # Load resources from seed dataset if offline/local
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

    # Filter and score
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
    """
    Validate a local JSON resource or stack manifest against canonical OpenRobo schemas.
    """
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
    """
    Inspect a public GitHub robotics repository and generate canonical OpenRobo resource manifests.
    """
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
    """
    Display current OpenRobo CLI environment information.
    """
    console.print("[bold cyan]OpenRobo Infrastructure Platform[/bold cyan]")
    console.print(f"CLI Version: {__version__}")
    console.print("License: Apache-2.0")
    console.print("Status: Local-first offline mode ready.")


if __name__ == "__main__":
    app()
