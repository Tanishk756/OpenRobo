"""Deterministic release archive creation with secret filtering and exclusion reporting."""

import fnmatch
import gzip
import hashlib
import io
import os
import tarfile
from datetime import datetime, timezone
from pathlib import Path

from openrobo_release.manifest import calculate_workspace_digest
from openrobo_release.models import (
    ExclusionReport,
    FileEntry,
    ReleaseManifest,
    ReleaseTarget,
)

# High-confidence exact and glob patterns for secret and key files
FORBIDDEN_PATTERNS = [
    "*.key",
    "*.pem",
    "*.crt",
    "*.pfx",
    "*.p12",
    "*.pkcs12",
    ".env",
    ".env.*",
    "*id_rsa",
    "*id_rsa.pub",
    "*id_ed25519",
    "*id_ed25519.pub",
    "*credentials.json",
    "*credentials.yaml",
    "*secret.json",
    "*secret.yaml",
    "*token.json",
    "*.keystore",
    "*.jks",
]

# Common ignore patterns (build artifacts, git, virtual environments)
DEFAULT_IGNORE_PATTERNS = [
    ".git",
    ".git/*",
    "node_modules",
    "node_modules/*",
    ".venv",
    ".venv/*",
    "__pycache__",
    "__pycache__/*",
    "*.pyc",
    ".pytest_cache",
    ".pytest_cache/*",
    "build",
    "build/*",
    "install",
    "install/*",
    "log",
    "log/*",
]


def is_forbidden_secret(rel_path: str) -> tuple[bool, str]:
    """Evaluates whether a relative file path matches a high-confidence secret/key pattern."""
    path_obj = Path(rel_path)
    filename = path_obj.name

    for pattern in FORBIDDEN_PATTERNS:
        if fnmatch.fnmatch(filename, pattern) or fnmatch.fnmatch(rel_path, pattern):
            return True, f"Matched forbidden secret pattern '{pattern}'"

    return False, ""


def should_ignore(rel_path: str) -> bool:
    """Checks if a file or directory should be ignored from the workspace build."""
    path_parts = Path(rel_path).parts
    for part in path_parts:
        if part in (".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", "build", "install", "log"):
            return True
    for pattern in DEFAULT_IGNORE_PATTERNS:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False


def create_deterministic_archive(
    workspace_dir: Path | str,
    output_path: Path | str,
    target: ReleaseTarget,
    release_id: str,
    release_version: str,
    release_key_id: str,
    stack_id: str | None = None,
    runtime_contract_digest: str | None = None,
    required_capabilities: list[str] | None = None,
    deployment_policy_id: str | None = None,
) -> tuple[ReleaseManifest, ExclusionReport]:
    """Packages a workspace into a deterministic .tar.gz release archive and returns manifest and exclusion report."""
    ws_path = Path(workspace_dir).resolve()
    out_path = Path(output_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report = ExclusionReport()
    file_entries: list[FileEntry] = []
    collected_files: list[tuple[str, Path]] = []

    for root, dirs, files in os.walk(ws_path):
        dirs.sort()
        files.sort()

        rel_root = os.path.relpath(root, ws_path)
        if rel_root != "." and should_ignore(rel_root.replace("\\", "/")):
            dirs[:] = []
            continue

        for f in files:
            full_file = Path(root) / f
            rel_file = os.path.relpath(full_file, ws_path).replace("\\", "/")

            if should_ignore(rel_file):
                report.excluded_files.append(rel_file)
                report.exclusion_reasons[rel_file] = "Default build/vcs ignore"
                continue

            forbidden, reason = is_forbidden_secret(rel_file)
            if forbidden:
                report.excluded_files.append(rel_file)
                report.exclusion_reasons[rel_file] = reason
                raise ValueError(f"High-confidence secret file detected and blocked from release: {rel_file} ({reason})")

            with open(full_file, "rb") as fp:
                content = fp.read()

            sha = hashlib.sha256(content).hexdigest()
            size = len(content)

            file_entries.append(FileEntry(path=rel_file, sha256=sha, size_bytes=size))
            collected_files.append((rel_file, full_file))
            report.included_files.append(rel_file)

    collected_files.sort(key=lambda x: x[0])
    file_entries.sort(key=lambda x: x.path)

    raw_tar_buf = io.BytesIO()
    with tarfile.open(fileobj=raw_tar_buf, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for rel_file, full_file in collected_files:
            stat_res = full_file.stat()
            tar_info = tarfile.TarInfo(name=rel_file)
            tar_info.size = stat_res.st_size
            tar_info.mtime = 0
            tar_info.uid = 0
            tar_info.gid = 0
            tar_info.uname = ""
            tar_info.gname = ""
            tar_info.mode = 0o755 if (stat_res.st_mode & 0o111) else 0o644
            tar_info.type = tarfile.REGTYPE

            with open(full_file, "rb") as fp:
                tar.addfile(tar_info, fp)

    raw_tar_bytes = raw_tar_buf.getvalue()

    gz_buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=gz_buf, mtime=0.0) as gz_out:
        gz_out.write(raw_tar_bytes)

    archive_bytes = gz_buf.getvalue()
    with open(out_path, "wb") as f:
        f.write(archive_bytes)

    artifact_digest = hashlib.sha256(archive_bytes).hexdigest()
    workspace_digest = calculate_workspace_digest(ws_path)

    manifest = ReleaseManifest(
        schema_version="1.0.0",
        release_id=release_id,
        release_version=release_version,
        created_at=datetime.now(timezone.utc).isoformat(),
        stack_id=stack_id,
        workspace_digest=workspace_digest,
        artifact_digest=artifact_digest,
        target=target,
        files=file_entries,
        runtime_contract_digest=runtime_contract_digest,
        required_capabilities=required_capabilities or [],
        deployment_policy_id=deployment_policy_id,
        release_key_id=release_key_id,
    )

    return manifest, report
