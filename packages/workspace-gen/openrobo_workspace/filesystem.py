"""Filesystem utilities for safe workspace generation."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List

from openrobo_workspace.models import GeneratedFile

RESERVED_DEVICE_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}


class SecurityPathError(ValueError):
    """Raised when an unsafe path is encountered."""
    pass


def sanitize_relative_path(path_str: str) -> str:
    """Sanitize relative path and prevent traversal, drive letters, and reserved device names."""
    if not path_str or not path_str.strip():
        raise SecurityPathError("Empty relative path is not permitted.")

    normalized = path_str.replace("\\", "/").strip().lstrip("/")

    # Check Windows drive letter e.g. C:
    if re.match(r"^[a-zA-Z]:", normalized):
        raise SecurityPathError(f"Drive letter detected in relative path: {path_str}")

    parts = normalized.split("/")
    sanitized_parts = []
    for part in parts:
        part_clean = part.strip()
        if not part_clean or part_clean == ".":
            continue
        if part_clean == "..":
            raise SecurityPathError(f"Path traversal sequence '..' detected in path: {path_str}")

        # Check Windows reserved device names
        stem = part_clean.split(".")[0].upper()
        if stem in RESERVED_DEVICE_NAMES:
            raise SecurityPathError(f"Reserved device name '{part_clean}' detected in path: {path_str}")

        # Disallow null bytes or control chars
        if "\x00" in part_clean or any(ord(c) < 32 for c in part_clean):
            raise SecurityPathError(f"Control characters or null byte detected in path: {path_str}")

        sanitized_parts.append(part_clean)

    if not sanitized_parts:
        raise SecurityPathError("Path resolved to an empty destination.")

    return "/".join(sanitized_parts)


def build_file_tree(files: List[GeneratedFile]) -> Dict[str, Any]:
    """Construct hierarchical directory tree from flat list of generated files."""
    root: Dict[str, Any] = {"name": "root", "type": "directory", "children": {}}

    for file in sorted(files, key=lambda f: f.path):
        parts = file.path.split("/")
        current = root
        for i, part in enumerate(parts):
            is_file = (i == len(parts) - 1)
            if is_file:
                current["children"][part] = {
                    "name": part,
                    "path": file.path,
                    "type": "file",
                    "size": len(file.content.encode("utf-8")),
                    "is_executable": file.is_executable,
                    "description": file.description,
                }
            else:
                if part not in current["children"]:
                    current["children"][part] = {
                        "name": part,
                        "type": "directory",
                        "children": {},
                    }
                current = current["children"][part]

    return root


def write_workspace_to_disk(output_dir: str | Path, files: List[GeneratedFile]) -> List[str]:
    """Safely write generated files to disk beneath output_dir."""
    out_path = Path(output_dir).resolve()
    out_path.mkdir(parents=True, exist_ok=True)
    written_files = []

    for file in files:
        safe_rel = sanitize_relative_path(file.path)
        dest_path = (out_path / safe_rel).resolve()

        # Ensure destination is strictly inside output directory
        if not str(dest_path).startswith(str(out_path)):
            raise SecurityPathError(f"Path traversal attempt: {file.path} escapes output root {out_path}")

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(file.content)

        if file.is_executable and os.name != "nt":
            try:
                dest_path.chmod(0o755)
            except Exception:
                pass

        written_files.append(str(dest_path))

    return written_files
