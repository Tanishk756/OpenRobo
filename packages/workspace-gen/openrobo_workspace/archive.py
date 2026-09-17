"""Deterministic in-memory ZIP archive builder."""

import io
import zipfile
from typing import List

from openrobo_workspace.filesystem import sanitize_relative_path
from openrobo_workspace.models import GeneratedFile

DETERMINISTIC_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def build_workspace_zip(files: List[GeneratedFile], root_dir_name: str = "workspace") -> bytes:
    """Pack generated files into deterministic ZIP archive bytes."""
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(files, key=lambda f: f.path):
            safe_rel = sanitize_relative_path(file.path)
            arcname = f"{root_dir_name}/{safe_rel}" if root_dir_name else safe_rel

            zinfo = zipfile.ZipInfo(filename=arcname, date_time=DETERMINISTIC_TIMESTAMP)
            # POSIX file permissions: 0o755 for executable scripts, 0o644 for standard files
            if file.is_executable or safe_rel.endswith((".sh", ".py")):
                zinfo.external_attr = 0o100755 << 16
            else:
                zinfo.external_attr = 0o100644 << 16

            content_bytes = file.content.encode("utf-8")
            zf.writestr(zinfo, content_bytes)

    buffer.seek(0)
    return buffer.getvalue()


create_workspace_zip = build_workspace_zip
