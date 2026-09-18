"""Canonical serialization and digest utilities for OpenRobo Release Manifests."""

import hashlib
import json
import os
from pathlib import Path
from typing import List, Union

from openrobo_release.models import FileEntry, ReleaseManifest

IGNORE_NAMES = (".git", "node_modules", ".venv", "__pycache__", ".pytest_cache", "build", "install", "log")


def canonical_manifest_bytes(manifest: Union[ReleaseManifest, dict]) -> bytes:
    """
    Produce bit-for-bit deterministic canonical JSON representation of a ReleaseManifest.

    Guarantees:
    - Sorted dictionary keys at all nesting levels
    - Stable compact separators (',', ':') with zero extraneous whitespace
    - Strict UTF-8 encoding
    - No floating point indeterminism or newline variations
    """
    if isinstance(manifest, ReleaseManifest):
        data = manifest.model_dump(mode="json")
    elif isinstance(manifest, dict):
        data = manifest
    else:
        raise TypeError(f"Expected ReleaseManifest or dict, got {type(manifest).__name__}")

    # Standard JSON canonicalization with sorted keys and compact separators
    encoded_str = json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return encoded_str.encode("utf-8")


def compute_manifest_digest(manifest: Union[ReleaseManifest, dict, bytes]) -> str:
    """Compute SHA-256 hex digest over canonical manifest bytes."""
    if isinstance(manifest, bytes):
        raw_bytes = manifest
    else:
        raw_bytes = canonical_manifest_bytes(manifest)
    return hashlib.sha256(raw_bytes).hexdigest()


def compute_workspace_digest(files: List[FileEntry]) -> str:
    """Compute deterministic SHA-256 tree digest across an ordered list of workspace files."""
    sorted_files = sorted(files, key=lambda f: f.path)
    combined = "\n".join(f"{f.sha256}  {f.path}" for f in sorted_files)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def calculate_workspace_digest(workspace_dir_or_files: Union[Path, str, List[FileEntry]]) -> str:
    """Calculates workspace tree digest from directory path or list of FileEntries."""
    if isinstance(workspace_dir_or_files, list):
        return compute_workspace_digest(workspace_dir_or_files)

    ws_path = Path(workspace_dir_or_files).resolve()
    file_hashes: list[tuple[str, str]] = []
    for root, _, files in os.walk(ws_path):
        for f in sorted(files):
            full_path = Path(root) / f
            rel_path = os.path.relpath(full_path, ws_path).replace("\\", "/")
            if any(p in rel_path.split("/") for p in IGNORE_NAMES):
                continue
            with open(full_path, "rb") as fp:
                h = hashlib.sha256(fp.read()).hexdigest()
            file_hashes.append((rel_path, h))

    file_hashes.sort(key=lambda x: x[0])
    combined = "\n".join(f"{h}  {p}" for p, h in file_hashes)
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()
