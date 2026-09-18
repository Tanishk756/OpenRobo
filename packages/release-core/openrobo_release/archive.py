"""Deterministic archive builder with strict secret exclusion and metadata normalization."""

import fnmatch
import gzip
import hashlib
import os
import tarfile
from pathlib import Path
from typing import List, Set, Tuple

from openrobo_release.manifest import compute_workspace_digest
from openrobo_release.models import FileEntry

# Strict exclusion patterns for secrets, credentials, runtime caches, and private keys
FORBIDDEN_PATTERNS: Set[str] = {
    "*.key",
    "*.pem",
    "*.p12",
    "*.pfx",
    "*.pkcs8",
    ".env",
    ".env.*",
    "*_rsa",
    "*_ed25519",
    "id_rsa*",
    "id_ed25519*",
    "*token*",
    "*.token",
    "*secret*",
    "*credential*",
    "*.sqlite",
    "*.db",
    "__pycache__",
    "*.pyc",
    ".pytest_cache",
    ".ruff_cache",
    ".git",
    ".gitignore",
    ".venv",
    "node_modules",
    ".next",
}


def is_forbidden_file(relative_path: str) -> bool:
    """Check if a given path matches any secret or runtime cache exclusion pattern."""
    parts = Path(relative_path).parts
    for part in parts:
        for pattern in FORBIDDEN_PATTERNS:
            if fnmatch.fnmatch(part.lower(), pattern.lower()):
                return True
    return False


def collect_workspace_files(workspace_dir: Path) -> List[Path]:
    """Recursively collect and sort all non-secret workspace files."""
    files: List[Path] = []
    for root, dirs, filenames in os.walk(workspace_dir):
        # Filter directories in-place to prevent traversing forbidden folders
        dirs[:] = [d for d in dirs if not is_forbidden_file(d)]
        for f in filenames:
            rel_path = os.path.relpath(os.path.join(root, f), workspace_dir).replace("\\", "/")
            if not is_forbidden_file(rel_path):
                files.append(Path(os.path.join(root, f)))
    return sorted(files, key=lambda p: os.path.relpath(p, workspace_dir).replace("\\", "/"))


def compute_file_entry(file_path: Path, workspace_dir: Path) -> FileEntry:
    """Compute relative POSIX path, size, and SHA-256 hash for a workspace file."""
    rel_path = os.path.relpath(file_path, workspace_dir).replace("\\", "/")
    sha256 = hashlib.sha256()
    size = 0
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
            size += len(chunk)
    return FileEntry(
        path=rel_path,
        sha256=sha256.hexdigest(),
        size_bytes=size,
    )


def create_deterministic_archive(
    workspace_dir: Path,
    output_archive_path: Path,
) -> Tuple[Path, str, str, List[FileEntry]]:
    """
    Create bit-for-bit deterministic .tar.gz archive from a workspace directory.

    Guarantees:
    - Exclusion of all secret/credential/key patterns
    - Sorted alphabetical file entry order
    - Fixed gzip mtime (0) and fixed TarInfo mtime (0)
    - Normalized owner (uid=0, gid=0, uname="", gname="")
    - Normalized permissions (0o755 for dirs and executables, 0o644 for standard files)
    - Returns (archive_path, artifact_sha256, workspace_digest, file_entries)
    """
    workspace_dir = Path(workspace_dir).resolve()
    output_archive_path = Path(output_archive_path).resolve()
    output_archive_path.parent.mkdir(parents=True, exist_ok=True)

    file_paths = collect_workspace_files(workspace_dir)
    file_entries: List[FileEntry] = [compute_file_entry(fp, workspace_dir) for fp in file_paths]
    workspace_digest = compute_workspace_digest(file_entries)

    # Build deterministic tar.gz with fixed gzip mtime
    with open(output_archive_path, "wb") as raw_f:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_f, mtime=0.0) as gz_f:
            with tarfile.open(fileobj=gz_f, mode="w", format=tarfile.PAX_FORMAT) as tar:
                for fp, entry in zip(file_paths, file_entries):
                    # Check if file is executable
                    is_exec = bool(fp.stat().st_mode & 0o111)

                    ti = tarfile.TarInfo(name=entry.path)
                    ti.size = entry.size_bytes
                    ti.mtime = 0
                    ti.uid = 0
                    ti.gid = 0
                    ti.uname = ""
                    ti.gname = ""
                    ti.mode = 0o755 if is_exec else 0o644
                    ti.type = tarfile.REGTYPE

                    with open(fp, "rb") as f:
                        tar.addfile(ti, f)

    # Compute artifact SHA-256
    art_sha = hashlib.sha256()
    with open(output_archive_path, "rb") as f:
        while chunk := f.read(65536):
            art_sha.update(chunk)
    artifact_digest = art_sha.hexdigest()

    return output_archive_path, artifact_digest, workspace_digest, file_entries
