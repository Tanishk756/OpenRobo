"""OpenRobo Edge Agent CLI commands including device initialization, enrollment, diagnostics, and local A/B deployment."""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import typer
from openrobo_release import ReleaseManifest, ReleaseVerifier, TrustedReleaseKey
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from openrobo_agent.config import AgentConfig
from openrobo_agent.deployment import (
    ABSlotManager,
    activate_staged_slot,
    rollback_to_previous,
    stage_release_artifact,
)
from openrobo_agent.identity import DeviceIdentityManager
from openrobo_agent.runtime import AgentRuntimeDispatcher
from openrobo_agent.security import check_file_permissions
from openrobo_agent.service import AgentDaemon, SystemdServiceGenerator

agent_app = typer.Typer(help="OpenRobo Edge Agent CLI")
deployment_app = typer.Typer(name="deployment", help="Manage local A/B workspace deployment partitions and rollbacks.")
agent_app.add_typer(deployment_app, name="deployment")
console = Console()


@agent_app.command("init")
def init_agent(
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Custom agent state directory"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Display name for this edge robot"),
):
    """Initialize local agent cryptographic identity (Ed25519 keypair and config)."""
    config = AgentConfig(state_dir=state_dir or AgentConfig.default_state_dir())
    mgr = DeviceIdentityManager(config)
    identity = mgr.get_or_create_identity(display_name=name or "robot-node")

    body = (
        f"[bold green]Initialized Device Identity[/bold green]\n\n"
        f"Device ID: [cyan]{identity.device_id}[/cyan]\n"
        f"Display Name: [yellow]{identity.display_name}[/yellow]\n"
        f"Key Fingerprint: [dim]{identity.public_key_fingerprint}[/dim]\n"
        f"State Directory: [blue]{config.state_dir}[/blue]"
    )
    console.print(Panel(body, title="OpenRobo Agent Identity"))


@agent_app.command("enroll")
def enroll_agent(
    token: str = typer.Option(..., "--token", "-t", help="Single-use enrollment token"),
    url: str = typer.Option("http://localhost:8000", "--url", "-u", help="Control plane API URL"),
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Custom agent state directory"),
):
    """Enroll local device with OpenRobo control plane using single-use token."""
    config = AgentConfig(control_plane_url=url, state_dir=state_dir or AgentConfig.default_state_dir())
    mgr = DeviceIdentityManager(config)

    console.print(f"Connecting to Control Plane at [cyan]{url}[/cyan]...")
    try:
        identity = mgr.enroll(token=token)
        body = (
            f"[bold green]Successfully Enrolled Device![/bold green]\n\n"
            f"Device ID: [cyan]{identity.device_id}[/cyan]\n"
            f"Cert Fingerprint: [dim]{identity.certificate_fingerprint}[/dim]\n"
            f"Cert Serial: [yellow]{identity.certificate_serial}[/yellow]\n"
            f"Certificate Path: [blue]{mgr.cert_path}[/blue]"
        )
        console.print(Panel(body, title="Enrollment Complete"))
    except Exception as e:
        console.print(f"[bold red]Enrollment Failed:[/bold red] {e}")
        raise typer.Exit(code=1)


@agent_app.command("status")
def status_agent(
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Custom agent state directory"),
):
    """Inspect current agent cryptographic identity and certificate status."""
    config = AgentConfig(state_dir=state_dir or AgentConfig.default_state_dir())
    mgr = DeviceIdentityManager(config)

    if not os.path.exists(mgr.key_path):
        console.print("[bold yellow]Agent identity not initialized.[/bold yellow] Run openrobo-agent init first.")
        raise typer.Exit(code=1)

    identity = mgr.load_identity()
    cert_info = mgr.get_certificate_info()

    table = Table(title="OpenRobo Edge Agent Status", show_header=True)
    table.add_column("Property", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Device ID", identity.device_id)
    table.add_row("Display Name", identity.display_name)
    table.add_row("Platform", f"{identity.platform} ({identity.architecture})")
    table.add_row("State Directory", str(config.state_dir))
    table.add_row("Key Fingerprint", identity.public_key_fingerprint)

    if cert_info:
        table.add_row("Cert Fingerprint", cert_info.get("fingerprint", "N/A"))
        table.add_row("Cert Serial", cert_info.get("serial_number", "N/A"))
        table.add_row("Valid Not Before", cert_info.get("not_before", "N/A"))
        table.add_row("Valid Not After", cert_info.get("not_after", "N/A"))
        table.add_row("Expired", "[red]YES[/red]" if cert_info.get("is_expired") else "[green]NO[/green]")
    else:
        table.add_row("Certificate", "[yellow]NOT ENROLLED[/yellow]")

    console.print(table)


@agent_app.command("doctor")
def doctor_agent(
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Custom agent state directory"),
):
    """Run local health checks, permission audits, and ROS 2 diagnostics."""
    config = AgentConfig(state_dir=state_dir or AgentConfig.default_state_dir())
    mgr = DeviceIdentityManager(config)
    dispatcher = AgentRuntimeDispatcher(mgr)

    table = Table(title="OpenRobo Agent Doctor", show_header=True)
    table.add_column("Check", style="bold")
    table.add_column("Status", style="cyan")
    table.add_column("Details", style="dim")

    if os.path.exists(mgr.key_path):
        perm_ok = check_file_permissions(mgr.key_path)
        status_str = "[green]OK (0600)[/green]" if perm_ok else "[yellow]WARN (Permissions)[/yellow]"
        table.add_row("Private Key", status_str, str(mgr.key_path))
    else:
        table.add_row("Private Key", "[red]MISSING[/red]", "Run openrobo-agent init")

    cert_info = mgr.get_certificate_info()
    if cert_info:
        if cert_info.get("is_expired"):
            table.add_row("Certificate", "[red]EXPIRED[/red]", cert_info.get("not_after", ""))
        else:
            table.add_row("Certificate", "[green]VALID[/green]", f"Expires: {cert_info.get('not_after')}")
    else:
        table.add_row("Certificate", "[yellow]NOT ENROLLED[/yellow]", "Run openrobo-agent enroll")

    ros_env = dispatcher.get_ros_environment()
    if ros_env.get("ros_detected"):
        table.add_row("ROS 2 Runtime", "[green]DETECTED[/green]", f"Distro: {ros_env.get('ros_distro', 'unknown')}")
    else:
        table.add_row("ROS 2 Runtime", "[yellow]NOT DETECTED[/yellow]", "No active ROS environment")

    ci_status = dispatcher.get_connection_inspector_status()
    if ci_status.get("installed"):
        table.add_row("Connection Inspector", "[green]INSTALLED[/green]", f"v{ci_status.get('version')}")
    else:
        table.add_row("Connection Inspector", "[dim]NOT INSTALLED[/dim]", "External tool not found")

    console.print(table)


@agent_app.command("service")
def generate_service(
    user: str = typer.Option("openrobo-agent", "--user", "-u", help="Service user"),
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Agent state directory"),
):
    """Generate a hardened, non-root systemd service unit template."""
    config = AgentConfig(state_dir=state_dir or AgentConfig.default_state_dir())
    gen = SystemdServiceGenerator(config, user=user)
    unit_content = gen.generate_unit()
    console.print(Panel(unit_content, title="Generated Systemd Unit (/etc/systemd/system/openrobo-agent.service)"))
    console.print("[dim]Note: OpenRobo does not auto-install services. Review and install manually.[/dim]")


@agent_app.command("run")
def run_agent(
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Custom agent state directory"),
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Control plane API URL"),
):
    """Start the OpenRobo Agent daemon loop."""
    config = AgentConfig(
        control_plane_url=url or "http://localhost:8000",
        state_dir=state_dir or AgentConfig.default_state_dir(),
    )
    daemon = AgentDaemon(config)
    console.print("[bold green]Starting OpenRobo Agent daemon...[/bold green] (Press Ctrl+C to stop)")
    try:
        asyncio.run(daemon.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping agent daemon...[/yellow]")
        asyncio.run(daemon.stop())


# ==========================================
# Deployment Subcommands
# ==========================================

@deployment_app.command("slots")
def list_slots(
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Custom agent state directory"),
):
    """List local A/B workspace slot partitions, active status, and installed releases."""
    config = AgentConfig(state_dir=state_dir or AgentConfig.default_state_dir())
    workspaces_dir = Path(config.state_dir) / "workspaces"
    slot_mgr = ABSlotManager(workspaces_dir)

    active_slot = slot_mgr.get_active_slot()
    prev_slot = slot_mgr.get_previous_slot()

    table = Table(title="OpenRobo A/B Workspace Deployment Slots", show_header=True)
    table.add_column("Slot", style="bold cyan")
    table.add_column("Status", style="bold")
    table.add_column("Release ID", style="magenta")
    table.add_column("Version", style="green")
    table.add_column("Active", justify="center")
    table.add_column("Activated At", style="dim")

    for sid in slot_mgr.SLOT_IDS:
        meta = slot_mgr.get_slot_metadata(sid)
        if sid == active_slot:
            is_act = "[bold green]YES (CURRENT)[/bold green]"
        elif sid == prev_slot:
            is_act = "[yellow]PREVIOUS[/yellow]"
        else:
            is_act = "[dim]NO[/dim]"
        status_style = "[green]" if meta.status == "ACTIVE" else ("[yellow]" if meta.status == "STAGED" else "[white]")
        table.add_row(
            sid,
            f"{status_style}{meta.status.value}[/]",
            meta.release_id or "EMPTY",
            meta.release_version or "-",
            is_act,
            meta.activated_at or "-",
        )

    console.print(table)


@deployment_app.command("stage")
def stage_release(
    archive_path: Path = typer.Argument(..., help="Path to release archive (.tar.gz)"),
    manifest_path: Path = typer.Argument(..., help="Path to release manifest JSON"),
    signature_path: Path = typer.Argument(..., help="Path to detached base64 .sig file"),
    public_key_path: Path = typer.Option(..., "--public-key", "-p", help="Path to trusted Ed25519 public key PEM"),
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Custom agent state directory"),
):
    """Verify and stage a release artifact into the inactive workspace slot."""
    config = AgentConfig(state_dir=state_dir or AgentConfig.default_state_dir())
    workspaces_dir = Path(config.state_dir) / "workspaces"
    slot_mgr = ABSlotManager(workspaces_dir)

    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = ReleaseManifest(**manifest_data)
        sig_b64 = signature_path.read_text(encoding="utf-8").strip()
        pub_pem = public_key_path.read_text(encoding="utf-8")
    except Exception as e:
        console.print(f"[bold red]Error loading release files:[/bold red] {e}")
        raise typer.Exit(code=1)

    trusted_key = TrustedReleaseKey(
        key_id=manifest.release_key_id,
        algorithm="Ed25519",
        public_key_pem=pub_pem,
        created_at=manifest.created_at,
    )
    verifier = ReleaseVerifier(trusted_keys=[trusted_key])

    console.print(f"[cyan]Verifying and staging release '{manifest.release_id}'...[/cyan]")
    ok, msg, meta = stage_release_artifact(
        slot_manager=slot_mgr,
        archive_path=archive_path,
        manifest=manifest,
        signature_b64=sig_b64,
        verifier=verifier,
    )

    if ok:
        console.print(Panel(
            f"[bold green]STAGING SUCCESSFUL[/bold green]\n\n"
            f"Slot:        {meta.slot_id}\n"
            f"Release ID:  {meta.release_id} (v{meta.release_version})\n"
            f"Status:      {meta.status.value}\n\n"
            f"Run [bold cyan]openrobo agent deployment activate {meta.slot_id}[/bold cyan] to activate.",
            title="Deployment Staging",
        ))
    else:
        console.print(Panel(
            f"[bold red]STAGING FAILED[/bold red]\n\n"
            f"Error: {msg}",
            title="Staging Error",
        ))
        raise typer.Exit(code=1)


@deployment_app.command("activate")
def activate_slot(
    slot_id: Optional[str] = typer.Argument(None, help="Slot ID to activate ('slot-a' or 'slot-b'). Auto-detects if omitted."),
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Custom agent state directory"),
):
    """Atomically activate a staged workspace slot."""
    config = AgentConfig(state_dir=state_dir or AgentConfig.default_state_dir())
    workspaces_dir = Path(config.state_dir) / "workspaces"
    slot_mgr = ABSlotManager(workspaces_dir)

    ok, msg, meta = activate_staged_slot(slot_manager=slot_mgr, target_slot_id=slot_id)
    if ok:
        console.print(Panel(
            f"[bold green]ACTIVATION SUCCESSFUL[/bold green]\n\n"
            f"Active Slot: {meta.slot_id}\n"
            f"Release ID:  {meta.release_id} (v{meta.release_version})\n"
            f"Status:      {meta.status.value}",
            title="Deployment Activation",
        ))
    else:
        console.print(Panel(f"[bold red]ACTIVATION FAILED:[/bold red] {msg}", title="Activation Error"))
        raise typer.Exit(code=1)


@deployment_app.command("rollback")
def rollback_slot(
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Custom agent state directory"),
):
    """Roll back to the previous known-good workspace slot."""
    config = AgentConfig(state_dir=state_dir or AgentConfig.default_state_dir())
    workspaces_dir = Path(config.state_dir) / "workspaces"
    slot_mgr = ABSlotManager(workspaces_dir)

    ok, msg, meta = rollback_to_previous(slot_manager=slot_mgr)
    if ok:
        console.print(Panel(
            f"[bold green]ROLLBACK SUCCESSFUL[/bold green]\n\n"
            f"Active Slot: {meta.slot_id}\n"
            f"Restored Release ID: {meta.release_id} (v{meta.release_version})\n"
            f"Status:      {meta.status.value}",
            title="Rollback Result",
        ))
    else:
        console.print(Panel(f"[bold red]ROLLBACK FAILED:[/bold red] {msg}", title="Rollback Error"))
        raise typer.Exit(code=1)


if __name__ == "__main__":
    agent_app()
