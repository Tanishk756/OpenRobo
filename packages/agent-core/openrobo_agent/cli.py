"""Command line interface for the OpenRobo Agent runtime and local deployment manager."""

import asyncio
import os
from pathlib import Path
from typing import Optional

import typer
from openrobo_release.trust_store import TrustedReleaseKeyStore
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from openrobo_agent.config import AgentConfig
from openrobo_agent.deployment.activation import activate_staged_slot
from openrobo_agent.deployment.rollback import rollback_to_previous
from openrobo_agent.deployment.slots import ABSlotManager
from openrobo_agent.deployment.staging import stage_release_artifact
from openrobo_agent.identity import DeviceIdentityManager
from openrobo_agent.runtime import AgentRuntimeDispatcher
from openrobo_agent.security import check_file_permissions
from openrobo_agent.service import AgentDaemon, SystemdServiceGenerator

agent_app = typer.Typer(help="OpenRobo Edge Agent and Local Deployment CLI.")
deployment_app = typer.Typer(help="Manage local A/B workspace deployment slots.", no_args_is_help=True)
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
    deployment_root: Optional[str] = typer.Option(None, "--root", "-r", help="Deployment root directory."),
) -> None:
    """Lists current A/B partition slot statuses and active workspace pointer."""
    if deployment_root:
        workspaces_dir = Path(deployment_root)
    else:
        config = AgentConfig(state_dir=state_dir or AgentConfig.default_state_dir())
        workspaces_dir = Path(config.state_dir) / "workspaces"

    manager = ABSlotManager(workspaces_dir)
    active = manager.get_active_slot_id()

    table = Table(title="OpenRobo Local A/B Partition Slots")
    table.add_column("Slot", style="cyan")
    table.add_column("State", style="bold")
    table.add_column("Active", style="green")
    table.add_column("Release ID", style="magenta")
    table.add_column("Release Version", style="yellow")
    table.add_column("Installed At")

    for sid in ["slot-a", "slot-b"]:
        meta = manager.get_slot_metadata(sid)
        is_act = "[bold green]YES[/bold green]" if sid == active else "NO"
        st = meta.state.value if meta else "EMPTY"
        rid = meta.release_id or "-" if meta else "-"
        ver = meta.release_version or "-" if meta else "-"
        inst = meta.installed_at[:19] if (meta and meta.installed_at) else "-"

        table.add_row(sid, st, is_act, rid, ver, inst)

    console.print(table)
    if manager.is_windows:
        console.print("[yellow]Note: Running on Windows environment (fallback pointer mode).[/yellow]")


@deployment_app.command("stage")
def stage_release(
    artifact: str = typer.Argument(..., help="Path to release .tar.gz archive."),
    manifest: str = typer.Argument(..., help="Path to release manifest JSON."),
    signature: str = typer.Argument(..., help="Path to detached signature file."),
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Custom agent state directory"),
    deployment_root: Optional[str] = typer.Option(None, "--root", "-r", help="Deployment root directory."),
    trust_dir: Optional[str] = typer.Option(None, "--trust-dir", help="Path to trusted release keys directory."),
    public_key: Optional[str] = typer.Option(None, "--public-key", "-p", help="Development-only public key override."),
) -> None:
    """Stages and verifies a release artifact into the inactive partition slot."""
    if deployment_root:
        workspaces_dir = Path(deployment_root)
    else:
        config = AgentConfig(state_dir=state_dir or AgentConfig.default_state_dir())
        workspaces_dir = Path(config.state_dir) / "workspaces"

    manager = ABSlotManager(workspaces_dir)
    fallback_dir = str(Path(workspaces_dir).parent / "trusted-release-keys")
    default_trust_dir = trust_dir or os.environ.get("OPENROBO_TRUSTED_KEYS_DIR") or fallback_dir
    store = TrustedReleaseKeyStore(trust_dir=default_trust_dir)

    pub_key_content = None
    if public_key:
        pk_path = Path(public_key)
        if pk_path.exists() and pk_path.is_file():
            with open(pk_path, "r", encoding="utf-8") as f:
                pub_key_content = f.read()
        else:
            pub_key_content = public_key

    ok, msg = stage_release_artifact(
        manager=manager,
        artifact_path=artifact,
        manifest_path=manifest,
        signature_path=signature,
        trust_store=store,
        dev_public_key=pub_key_content,
        allow_dev_key=True if public_key else False,
    )

    if ok:
        console.print(f"[bold green]{msg}[/bold green]")
    else:
        console.print(f"[bold red]Staging Failed:[/bold red] {msg}")
        raise typer.Exit(code=1)


@deployment_app.command("activate")
def activate_release(
    slot_id: Optional[str] = typer.Option(None, "--slot", help="Explicit slot to activate ('slot-a' or 'slot-b')."),
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Custom agent state directory"),
    deployment_root: Optional[str] = typer.Option(None, "--root", "-r", help="Deployment root directory."),
) -> None:
    """Atomically activates a VERIFIED partition slot."""
    if deployment_root:
        workspaces_dir = Path(deployment_root)
    else:
        config = AgentConfig(state_dir=state_dir or AgentConfig.default_state_dir())
        workspaces_dir = Path(config.state_dir) / "workspaces"

    manager = ABSlotManager(workspaces_dir)
    ok, msg = activate_staged_slot(manager=manager, slot_id=slot_id)  # type: ignore

    if ok:
        console.print(f"[bold green]{msg}[/bold green]")
    else:
        console.print(f"[bold red]Activation Failed:[/bold red] {msg}")
        raise typer.Exit(code=1)


@deployment_app.command("rollback")
def rollback_release(
    state_dir: Optional[str] = typer.Option(None, "--state-dir", "-s", help="Custom agent state directory"),
    deployment_root: Optional[str] = typer.Option(None, "--root", "-r", help="Deployment root directory."),
    trust_dir: Optional[str] = typer.Option(None, "--trust-dir", help="Path to trusted release keys directory."),
) -> None:
    """Restores the previous partition slot after verifying release evidence and content hashes."""
    if deployment_root:
        workspaces_dir = Path(deployment_root)
    else:
        config = AgentConfig(state_dir=state_dir or AgentConfig.default_state_dir())
        workspaces_dir = Path(config.state_dir) / "workspaces"

    manager = ABSlotManager(workspaces_dir)
    fallback_dir = str(Path(workspaces_dir).parent / "trusted-release-keys")
    default_trust_dir = trust_dir or os.environ.get("OPENROBO_TRUSTED_KEYS_DIR") or fallback_dir
    store = TrustedReleaseKeyStore(trust_dir=default_trust_dir)

    ok, msg = rollback_to_previous(manager=manager, trust_store=store)

    if ok:
        console.print(f"[bold green]{msg}[/bold green]")
    else:
        console.print(f"[bold red]Rollback Failed:[/bold red] {msg}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    agent_app()
