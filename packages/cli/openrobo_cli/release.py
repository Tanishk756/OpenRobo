"""Release packaging, signing, and verification CLI commands for OpenRobo."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from openrobo_release import (
    ReleaseManifest,
    ReleaseSigner,
    ReleaseTarget,
    ReleaseVerifier,
    TrustedReleaseKey,
    canonical_manifest_bytes,
    create_deterministic_archive,
)
from rich.console import Console
from rich.panel import Panel

console = Console()
release_app = typer.Typer(name="release", help="Cryptographic release artifact packaging, signing, and verification.")


@release_app.command("build")
def build_release(
    workspace_dir: Path = typer.Argument(..., help="Path to workspace directory to package"),
    output_dir: Path = typer.Option(Path("dist"), "--output-dir", "-o", help="Output directory for release artifacts"),
    release_id: str = typer.Option(..., "--release-id", "-r", help="Unique release identifier"),
    version: str = typer.Option("1.0.0", "--version", "-v", help="Semver release version"),
    key_id: str = typer.Option("rel-dev-key-01", "--key-id", "-k", help="Release key ID"),
    private_key_file: Optional[Path] = typer.Option(None, "--private-key", help="Path to Ed25519 private key PEM file"),
    target_os: str = typer.Option("linux", "--target-os", help="Target operating system"),
    target_arch: str = typer.Option("x86_64", "--target-arch", help="Target CPU architecture"),
    ros_distro: str = typer.Option("humble", "--ros-distro", help="Target ROS 2 distro"),
):
    """Package a workspace directory into an immutable signed release artifact."""
    if not workspace_dir.exists() or not workspace_dir.is_dir():
        console.print(f"[bold red]Error:[/bold red] Workspace directory not found: {workspace_dir}")
        raise typer.Exit(code=1)

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / f"{release_id}.tar.gz"
    manifest_path = output_dir / f"{release_id}.manifest.json"
    sig_path = output_dir / f"{release_id}.sig"

    console.print(f"[cyan]Creating deterministic archive for release '{release_id}'...[/cyan]")
    archive_out, art_digest, ws_digest, files = create_deterministic_archive(workspace_dir, archive_path)

    now_iso = datetime.now(timezone.utc).isoformat()
    manifest = ReleaseManifest(
        release_id=release_id,
        release_version=version,
        created_at=now_iso,
        workspace_digest=ws_digest,
        artifact_digest=art_digest,
        target=ReleaseTarget(operating_system=target_os, architecture=target_arch, ros_distro=ros_distro),
        files=files,
        release_key_id=key_id,
    )

    # Sign manifest
    if private_key_file and private_key_file.exists():
        priv_pem = private_key_file.read_text(encoding="utf-8")
        signer = ReleaseSigner(private_key_pem=priv_pem, key_id=key_id)
        sig_b64 = signer.sign_manifest(manifest)
    else:
        # Generate development signing key
        console.print("[yellow]Notice: No private key provided. Generating development signing keypair...[/yellow]")
        sign_key, trust_key = ReleaseSigner.generate_keypair(key_id=key_id)
        signer = ReleaseSigner(private_key_pem=sign_key.private_key_pem, key_id=key_id, allow_dev=True)
        sig_b64 = signer.sign_manifest(manifest)

        # Save public key for verification
        pub_path = output_dir / f"{key_id}.pub.pem"
        pub_path.write_text(trust_key.public_key_pem, encoding="utf-8")
        console.print(f"Saved public key to [cyan]{pub_path}[/cyan]")

    # Save manifest and signature
    manifest_bytes = canonical_manifest_bytes(manifest)
    manifest_path.write_bytes(manifest_bytes)
    sig_path.write_text(sig_b64, encoding="utf-8")

    console.print(Panel(
        f"[bold green]Release Package Built Successfully[/bold green]\n\n"
        f"Release ID:       {release_id} (v{version})\n"
        f"Artifact Digest:  {art_digest[:16]}...\n"
        f"Workspace Digest: {ws_digest[:16]}...\n"
        f"Files Packaged:   {len(files)}\n"
        f"Archive:          {archive_path}\n"
        f"Manifest:         {manifest_path}\n"
        f"Signature:        {sig_path}",
        title="Release Build Summary",
    ))


@release_app.command("verify")
def verify_release(
    manifest_path: Path = typer.Argument(..., help="Path to release manifest JSON"),
    signature_path: Path = typer.Argument(..., help="Path to detached base64 .sig file"),
    public_key_path: Path = typer.Option(..., "--public-key", "-p", help="Path to trusted Ed25519 public key PEM"),
    artifact_path: Optional[Path] = typer.Option(None, "--artifact", "-a", help="Optional path to artifact archive for digest check"),
):
    """Cryptographically verify a release manifest, detached signature, and artifact digest."""
    if not manifest_path.exists():
        console.print(f"[bold red]Error:[/bold red] Manifest not found: {manifest_path}")
        raise typer.Exit(code=1)
    if not signature_path.exists():
        console.print(f"[bold red]Error:[/bold red] Signature not found: {signature_path}")
        raise typer.Exit(code=1)
    if not public_key_path.exists():
        console.print(f"[bold red]Error:[/bold red] Public key not found: {public_key_path}")
        raise typer.Exit(code=1)

    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = ReleaseManifest(**manifest_data)
    except Exception as e:
        console.print(f"[bold red]Malformed Manifest:[/bold red] {e}")
        raise typer.Exit(code=1)

    sig_b64 = signature_path.read_text(encoding="utf-8").strip()
    pub_pem = public_key_path.read_text(encoding="utf-8")

    trusted_key = TrustedReleaseKey(
        key_id=manifest.release_key_id,
        algorithm="Ed25519",
        public_key_pem=pub_pem,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    verifier = ReleaseVerifier(trusted_keys=[trusted_key])
    result = verifier.verify_release(manifest=manifest, signature_b64=sig_b64, artifact_path=artifact_path)

    if result.is_valid:
        console.print(Panel(
            f"[bold green]VERIFICATION SUCCESSFUL[/bold green]\n\n"
            f"Release ID:       {manifest.release_id}\n"
            f"Key ID:           {manifest.release_key_id}\n"
            f"Manifest Digest:  {result.manifest_digest}\n"
            f"Artifact Digest:  {result.artifact_digest or 'N/A'}\n"
            f"Status:           {result.status.value}",
            title="Verification Result",
        ))
    else:
        console.print(Panel(
            f"[bold red]VERIFICATION FAILED[/bold red]\n\n"
            f"Status:  {result.status.value}\n"
            f"Message: {result.message}",
            title="Verification Error",
        ))
        raise typer.Exit(code=1)
