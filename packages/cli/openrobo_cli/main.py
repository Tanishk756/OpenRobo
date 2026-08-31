import json
from pathlib import Path
from typing import Optional

import typer
from openrobo_schemas import validate_resource_manifest, validate_stack_manifest
from rich.console import Console
from rich.panel import Panel

__version__ = "0.1.0"

app = typer.Typer(
    name="openrobo",
    help="OpenRobo CLI — Open-Source Global Robotics Commons Tool",
    add_completion=False
)
console = Console()

def version_callback(value: bool):
    if value:
        console.print(f"[bold green]OpenRobo CLI[/bold green] version: [cyan]{__version__}[/cyan]")
        raise typer.Exit()

@app.callback()
def common(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show OpenRobo CLI version and exit.",
        callback=version_callback,
        is_eager=True
    )
):
    """
    OpenRobo local-first CLI utility for discovery, manifest validation, and workspace generation.
    """
    pass

@app.command("validate")
def validate(
    file_path: Path = typer.Argument(..., help="Path to JSON manifest file to validate."),
    manifest_type: str = typer.Option("resource", "--type", "-t", help="Manifest type: 'resource' or 'stack'")
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
