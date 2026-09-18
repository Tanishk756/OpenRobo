"""Release management CLI commands for building, inspecting, signing, and verifying immutable OpenRobo releases."""

import os
from pathlib import Path

import typer
from openrobo_release.archive import create_deterministic_archive
from openrobo_release.models import ReleaseTarget
from openrobo_release.signing import (
    ReleaseSigner,
    generate_development_keypair,
    validate_private_key_file,
)
from openrobo_release.trust_store import TrustedReleaseKeyStore
from openrobo_release.verification import ReleaseVerifier
from rich.console import Console

release_app = typer.Typer(help="Manage and build OpenRobo signed release artifacts.", no_args_is_help=True)
key_app = typer.Typer(help="Manage release signing keys.", no_args_is_help=True)
release_app.add_typer(key_app, name="key")
console = Console()


@key_app.command("generate")
def generate_key(
    dev: bool = typer.Option(False, "--dev", help="Explicitly declare that this is a development signing key."),
    output_dir: str = typer.Option("./keys", "--output-dir", "-o", help="Directory to save generated key files."),
    key_id: str = typer.Option(None, "--key-id", help="Optional explicit key ID."),
) -> None:
    """Generates a development Ed25519 signing keypair when OPENROBO_DEV_RELEASE_SIGNING=true."""
    if not dev:
        console.print("[bold red]Error: Automatic production key generation is disabled. Use --dev for development keys.[/bold red]")
        raise typer.Exit(code=1)

    try:
        signing_key, priv_bytes = generate_development_keypair(key_id=key_id)
    except PermissionError as pe:
        console.print(f"[bold red]Permission Error:[/bold red] {pe}")
        raise typer.Exit(code=1)

    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    priv_file = out_path / f"{signing_key.key_id}.key"
    pub_file = out_path / f"{signing_key.key_id}.pub.json"

    with open(priv_file, "wb") as f:
        f.write(priv_bytes)
    with open(pub_file, "w", encoding="utf-8") as f:
        f.write(signing_key.model_dump_json(indent=2))

    console.print(f"[bold green]Development signing keypair generated:[/bold green] {signing_key.key_id}")
    console.print(f"  Private Key: {priv_file}")
    console.print(f"  Public Key Metadata: {pub_file}")


@release_app.command("build")
def build_release(
    workspace_dir: str = typer.Argument(..., help="Path to the workspace root to package."),
    output_dir: str = typer.Option("./dist", "--output-dir", "-o", help="Output directory for release artifacts."),
    release_id: str = typer.Option(None, "--release-id", help="Explicit release UUID."),
    release_version: str = typer.Option("1.0.0", "--version", "-v", help="Semantic release version."),
    os_target: str = typer.Option("linux", "--os", help="Target operating system."),
    arch_target: str = typer.Option("x86_64", "--arch", help="Target CPU architecture."),
    ros_distro: str = typer.Option("humble", "--ros-distro", help="Target ROS distribution."),
    private_key: str = typer.Option(None, "--private-key", "-k", help="Path to Ed25519 private key file (PEM format)."),
    key_id: str = typer.Option(None, "--key-id", help="Signing Key ID."),
) -> None:
    """Packages a workspace into a deterministic .tar.gz archive, generates manifest, and cryptographically signs it."""
    ws_path = Path(workspace_dir).resolve()
    if not ws_path.exists():
        console.print(f"[bold red]Error: Workspace directory does not exist:[/bold red] {ws_path}")
        raise typer.Exit(code=1)

    # 1. Resolve & Validate Private Key
    priv_key_path = private_key or os.environ.get("OPENROBO_RELEASE_PRIVATE_KEY")
    if not priv_key_path:
        console.print(
            "[bold red]Error: Production release build requires an explicit signing key "
            "(--private-key or OPENROBO_RELEASE_PRIVATE_KEY).[/bold red]\n"
            "Automatic development signing is disabled in production."
        )
        raise typer.Exit(code=1)

    try:
        validate_private_key_file(priv_key_path)
    except Exception as e:
        console.print(f"[bold red]Private Key Validation Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    with open(priv_key_path, "rb") as f:
        priv_key_bytes = f.read()

    actual_key_id = key_id or Path(priv_key_path).stem
    actual_release_id = release_id or f"rel-{os.urandom(6).hex()}"

    target = ReleaseTarget(
        operating_system=os_target,
        architecture=arch_target,
        ros_distro=ros_distro,
    )

    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)

    artifact_filename = f"openrobo-{actual_release_id}.tar.gz"
    artifact_path = out_path / artifact_filename
    manifest_path = out_path / f"openrobo-{actual_release_id}.manifest.json"
    sig_path = out_path / f"openrobo-{actual_release_id}.sig"

    # 2. Package Archive
    try:
        manifest, report = create_deterministic_archive(
            workspace_dir=ws_path,
            output_path=artifact_path,
            target=target,
            release_id=actual_release_id,
            release_version=release_version,
            release_key_id=actual_key_id,
        )
    except Exception as e:
        console.print(f"[bold red]Packaging Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    # 3. Sign Manifest
    signer = ReleaseSigner(priv_key_bytes, key_id=actual_key_id)
    detached_sig = signer.sign_manifest(manifest)

    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(manifest.model_dump_json(indent=2))
    with open(sig_path, "w", encoding="utf-8") as f:
        f.write(detached_sig)

    console.print("[bold green]Release built and signed successfully![/bold green]")
    console.print(f"  Release ID: {actual_release_id}")
    console.print(f"  Artifact:   {artifact_path}")
    console.print(f"  Manifest:   {manifest_path}")
    console.print(f"  Signature:  {sig_path}")
    console.print(f"  Files:      {len(report.included_files)} included, {len(report.excluded_files)} excluded")


@release_app.command("verify")
def verify_release(
    manifest_file: str = typer.Argument(..., help="Path to release manifest JSON."),
    signature_file: str = typer.Argument(..., help="Path to detached signature file."),
    trust_dir: str = typer.Option(None, "--trust-dir", help="Path to trusted release keys directory."),
) -> None:
    """Verifies a release manifest against trusted release keys."""
    m_path = Path(manifest_file).resolve()
    s_path = Path(signature_file).resolve()

    if not m_path.exists() or not s_path.exists():
        console.print("[bold red]Manifest or signature file does not exist.[/bold red]")
        raise typer.Exit(code=1)

    import json

    from openrobo_release.models import ReleaseManifest

    with open(m_path, "r", encoding="utf-8") as f:
        manifest = ReleaseManifest.model_validate(json.load(f))
    with open(s_path, "r", encoding="utf-8") as f:
        sig = f.read().strip()

    store = TrustedReleaseKeyStore(trust_dir=trust_dir)
    verifier = ReleaseVerifier(trust_store=store)

    res = verifier.verify_manifest_signature(manifest, sig)
    if res.is_valid:
        console.print(f"[bold green]Signature VALID for release {manifest.release_id} (Key: {res.key_id})[/bold green]")
    else:
        console.print(f"[bold red]Signature INVALID: {res.details} ({res.status.value})[/bold red]")
        raise typer.Exit(code=1)
