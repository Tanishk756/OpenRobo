"""OpenRobo Agent Command Line Interface."""

import asyncio
import os
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from openrobo_agent.config import AgentConfig
from openrobo_agent.identity import DeviceIdentityManager
from openrobo_agent.runtime import AgentRuntimeDispatcher
from openrobo_agent.security import check_file_permissions
from openrobo_agent.service import AgentDaemon, SystemdServiceGenerator

agent_app = typer.Typer(help="OpenRobo Edge Agent CLI")
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


if __name__ == "__main__":
    agent_app()
