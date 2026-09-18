# CLI subcommands for remote deployment orchestration and release catalog management.

import os
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
deployment_cli = typer.Typer(help="Manage fleet deployment orchestration and canary rollouts.")
release_cli = typer.Typer(help="Manage release catalog and trusted artifact sources.")


def get_api_url() -> str:
    return os.getenv("OPENROBO_API_URL", "http://127.0.0.1:8000")


def get_headers() -> dict:
    admin_key = os.getenv("OPENROBO_ADMIN_KEY", "dev-admin-key")
    return {
        "Content-Type": "application/json",
        "X-OpenRobo-Admin-Key": admin_key,
    }


# ==================== RELEASE COMMANDS ====================


@release_cli.command("register")
def register_release(
    release_id: str = typer.Option(..., "--release-id", "-r", help="Unique canonical release identifier"),
    version: str = typer.Option(..., "--version", "-v", help="Release version (e.g. 1.0.0)"),
    manifest_digest: str = typer.Option(..., "--manifest-digest", help="SHA-256 digest of canonical manifest JSON"),
    artifact_digest: str = typer.Option(..., "--artifact-digest", help="SHA-256 digest of artifact archive"),
    workspace_digest: str = typer.Option(..., "--workspace-digest", help="SHA-256 workspace digest"),
    release_key_id: str = typer.Option(..., "--release-key-id", help="Signing key ID (e.g. key-2026-prod-01)"),
    artifact_source_id: str = typer.Option(..., "--artifact-source-id", help="Configured artifact source ID"),
    target_os: str = typer.Option("linux", "--target-os", help="Target operating system"),
    target_arch: str = typer.Option("x86_64", "--target-arch", help="Target CPU architecture"),
    target_ros_distro: Optional[str] = typer.Option(None, "--target-ros-distro", help="Target ROS distro (e.g. humble)"),
):
    url = f"{get_api_url()}/api/v1/releases"
    payload = {
        "release_id": release_id,
        "release_version": version,
        "manifest_digest": manifest_digest,
        "artifact_digest": artifact_digest,
        "workspace_digest": workspace_digest,
        "release_key_id": release_key_id,
        "artifact_source_id": artifact_source_id,
        "target_os": target_os,
        "target_architecture": target_arch,
        "target_ros_distro": target_ros_distro,
    }

    try:
        resp = httpx.post(url, json=payload, headers=get_headers(), timeout=10.0)
        if resp.status_code == 201:
            data = resp.json()
            msg = f"[bold green]SUCCESS:[/bold green] Release '{release_id}' registered successfully!\nStatus: {data['status']}"
            console.print(Panel(msg, title="Release Catalog"))
        else:
            console.print(f"[bold red]Error ({resp.status_code}):[/bold red] {resp.text}")
            raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Request failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@release_cli.command("list")
def list_releases():
    url = f"{get_api_url()}/api/v1/releases"
    try:
        resp = httpx.get(url, headers=get_headers(), timeout=10.0)
        if resp.status_code == 200:
            releases = resp.json()
            table = Table(title="Control Plane Release Catalog", show_header=True, header_style="bold cyan")
            table.add_column("Release ID", style="cyan")
            table.add_column("Version", style="magenta")
            table.add_column("Target", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Key ID", style="dim")
            table.add_column("Source", style="white")

            for r in releases:
                target_str = f"{r['target_os']}/{r['target_architecture']}"
                if r.get("target_ros_distro"):
                    target_str += f" ({r['target_ros_distro']})"
                table.add_row(
                    r["release_id"],
                    r["release_version"],
                    target_str,
                    r["status"],
                    r["release_key_id"],
                    r["artifact_source_id"],
                )
            console.print(table)
        else:
            console.print(f"[bold red]Error ({resp.status_code}):[/bold red] {resp.text}")
            raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Request failed:[/bold red] {e}")
        raise typer.Exit(code=1)


# ==================== DEPLOYMENT COMMANDS ====================


@deployment_cli.command("create")
def create_deployment(
    release_id: str = typer.Option(..., "--release-id", "-r", help="Release ID to deploy"),
    canary_stages: Optional[str] = typer.Option(None, "--canary-stages", help="Comma-separated stage percentages (e.g. 20,50,100)"),
    device_ids: Optional[str] = typer.Option(None, "--device-ids", help="Comma-separated target device IDs"),
    domain: Optional[str] = typer.Option(None, "--domain", help="Target domain filter"),
    robot_type: Optional[str] = typer.Option(None, "--robot-type", help="Target robot type filter"),
    idempotency_key: Optional[str] = typer.Option(None, "--idempotency-key", help="Idempotency key"),
):
    url = f"{get_api_url()}/api/v1/deployments"

    stages = []
    strategy_type = "IMMEDIATE_ALL"
    if canary_stages:
        strategy_type = "CANARY"
        for idx, pct_str in enumerate(canary_stages.split(",")):
            pct = int(pct_str.strip())
            stages.append({"stage_index": idx, "target_percentage": pct, "require_approval": True})

    target_filter = {}
    if device_ids:
        target_filter["device_ids"] = [d.strip() for d in device_ids.split(",")]
    if domain:
        target_filter["domains"] = [domain.strip()]
    if robot_type:
        target_filter["robot_types"] = [robot_type.strip()]

    payload = {
        "release_id": release_id,
        "rollout_strategy": {
            "strategy_type": strategy_type,
            "stages": stages,
        },
        "target_filter": target_filter,
        "idempotency_key": idempotency_key,
    }

    try:
        resp = httpx.post(url, json=payload, headers=get_headers(), timeout=10.0)
        if resp.status_code == 201:
            data = resp.json()
            msg = (
                f"[bold green]SUCCESS:[/bold green] Deployment created!\n"
                f"ID: {data['id']}\n"
                f"Status: {data['status']}\n"
                f"Generation: {data['generation']}\n"
                f"Total Stages: {data['total_stages']}\n"
                f"Version: {data['version']}"
            )
            console.print(Panel(msg, title="Deployment Orchestration"))
        else:
            console.print(f"[bold red]Error ({resp.status_code}):[/bold red] {resp.text}")
            raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Request failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@deployment_cli.command("list")
def list_deployments():
    url = f"{get_api_url()}/api/v1/deployments"
    try:
        resp = httpx.get(url, headers=get_headers(), timeout=10.0)
        if resp.status_code == 200:
            deployments = resp.json()
            table = Table(title="Fleet Deployments", show_header=True, header_style="bold cyan")
            table.add_column("Deployment ID", style="cyan")
            table.add_column("Release ID", style="magenta")
            table.add_column("Status", style="yellow")
            table.add_column("Stage", justify="center", style="green")
            table.add_column("Generation", justify="right", style="dim")
            table.add_column("Version", justify="right", style="white")

            for d in deployments:
                stage_str = f"{d['current_stage'] + 1}/{d['total_stages']}"
                table.add_row(
                    d["id"],
                    d["release_id"],
                    d["status"],
                    stage_str,
                    str(d["generation"]),
                    str(d["version"]),
                )
            console.print(table)
        else:
            console.print(f"[bold red]Error ({resp.status_code}):[/bold red] {resp.text}")
            raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Request failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@deployment_cli.command("show")
def show_deployment(deployment_id: str = typer.Argument(..., help="Deployment UUID")):
    url = f"{get_api_url()}/api/v1/deployments/{deployment_id}"
    try:
        resp = httpx.get(url, headers=get_headers(), timeout=10.0)
        if resp.status_code == 200:
            d = resp.json()
            msg = (
                f"[bold cyan]Deployment:[/bold cyan] {d['id']}\n"
                f"[bold]Release ID:[/bold] {d['release_id']}\n"
                f"[bold]Status:[/bold] {d['status']}\n"
                f"[bold]Current Stage:[/bold] {d['current_stage'] + 1} of {d['total_stages']}\n"
                f"[bold]Generation:[/bold] {d['generation']}\n"
                f"[bold]Version (optimistic lock):[/bold] {d['version']}\n"
                f"[bold]Created At:[/bold] {d['created_at']}"
            )
            console.print(Panel(msg, title="Deployment Details"))

            if d.get("stages"):
                table = Table(title="Stage Rollout Progress", show_header=True, header_style="bold cyan")
                table.add_column("Stage", justify="center")
                table.add_column("Target %", justify="right")
                table.add_column("Total", justify="right")
                table.add_column("Staged", justify="right", style="yellow")
                table.add_column("Active", justify="right", style="green")
                table.add_column("Failed", justify="right", style="red")

                for s in d["stages"]:
                    table.add_row(
                        str(s["stage_index"]),
                        f"{s['target_percentage']}%",
                        str(s["total_devices"]),
                        str(s["staged"]),
                        str(s["active"]),
                        str(s["failed"]),
                    )
                console.print(table)
        else:
            console.print(f"[bold red]Error ({resp.status_code}):[/bold red] {resp.text}")
            raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Request failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@deployment_cli.command("approve")
def approve_deployment(
    deployment_id: str = typer.Argument(..., help="Deployment UUID"),
    stage_index: int = typer.Option(..., "--stage-index", "-s", help="Current stage index (0-indexed)"),
    action: str = typer.Option(..., "--action", "-a", help="Approval action"),
    expected_version: int = typer.Option(..., "--expected-version", "-v", help="Optimistic concurrency expected deployment version"),
    expected_state: str = typer.Option(..., "--expected-state", help="Expected current deployment state"),
    notes: Optional[str] = typer.Option(None, "--notes", help="Audit notes for approval"),
):
    url = f"{get_api_url()}/api/v1/deployments/{deployment_id}/approve"
    payload = {
        "stage_index": stage_index,
        "action": action,
        "expected_version": expected_version,
        "expected_state": expected_state,
        "notes": notes,
    }

    try:
        resp = httpx.post(url, json=payload, headers=get_headers(), timeout=10.0)
        if resp.status_code == 200:
            d = resp.json()
            msg = (
                f"[bold green]SUCCESS:[/bold green] Approval recorded!\n"
                f"New State: {d['status']}\n"
                f"New Version: {d['version']}\n"
                f"Current Stage: {d['current_stage'] + 1} of {d['total_stages']}"
            )
            console.print(Panel(msg, title="Stage Progression Approval"))
        else:
            console.print(f"[bold red]Error ({resp.status_code}):[/bold red] {resp.text}")
            raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Request failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@deployment_cli.command("cancel")
def cancel_deployment(
    deployment_id: str = typer.Argument(..., help="Deployment UUID"),
):
    url = f"{get_api_url()}/api/v1/deployments/{deployment_id}/cancel"
    try:
        resp = httpx.post(url, headers=get_headers(), timeout=10.0)
        if resp.status_code == 200:
            d = resp.json()
            panel_msg = f"[bold yellow]CANCELLED:[/bold yellow] Deployment {deployment_id} has been cancelled.\nStatus: {d['status']}"
            console.print(Panel(panel_msg, title="Deployment Cancelled"))
        else:
            console.print(f"[bold red]Error ({resp.status_code}):[/bold red] {resp.text}")
            raise typer.Exit(code=1)
    except Exception as e:
        console.print(f"[bold red]Request failed:[/bold red] {e}")
        raise typer.Exit(code=1)
