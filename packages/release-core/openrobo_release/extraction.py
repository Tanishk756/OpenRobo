"""Safe release archive extraction with traversal resistance, link rejection, and quarantine staging."""

import hashlib
import os
import re
import shutil
import tarfile
import unicodedata
import uuid
from pathlib import Path

from openrobo_release.models import ReleaseManifest

# Windows reserved device names
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
}


def sanitize_and_validate_path(
    path_str: str,
    seen_canonical_paths: set[str] | None = None,
    max_path_length: int = 255,
) -> str:
    """Sanitizes an archive member path, enforcing traversal prevention and duplicate alias rejection.

    Returns the canonical normalized relative path.
    """
    if "\x00" in path_str:
        raise ValueError(f"Path contains illegal null byte: {repr(path_str)}")

    # Reject non-printable ASCII control characters
    for c in path_str:
        if ord(c) < 32 and c not in ("\t", "\n", "\r"):
            raise ValueError(f"Path contains illegal ASCII control character: {repr(path_str)}")

    # Normalize Unicode to NFC
    nfc_str = unicodedata.normalize("NFC", path_str)

    # Reject Windows drive letters and UNC paths
    if re.match(r"^[a-zA-Z]:", nfc_str) or nfc_str.startswith(("\\\\", "//")):
        raise ValueError(f"Absolute Windows drive/UNC path forbidden: {path_str}")

    # Normalize backslashes to forward slashes
    normalized = nfc_str.replace("\\", "/")

    if normalized.startswith("/"):
        raise ValueError(f"absolute path forbidden: {path_str}")

    parts = normalized.split("/")
    cleaned_parts: list[str] = []

    for part in parts:
        part = part.strip()
        if not part or part == ".":
            continue
        if part == "..":
            raise ValueError(f"path traversal / directory traversal ('..') detected in path: {path_str}")

        # Check for Windows reserved device names (e.g. CON, NUL, COM1, AUX.txt)
        base_name = part.split(".")[0].upper()
        if base_name in WINDOWS_RESERVED_NAMES:
            raise ValueError(f"Windows reserved device name forbidden in archive member: {part}")

        cleaned_parts.append(part)

    if not cleaned_parts:
        raise ValueError(f"Path resolves to empty/root target: {path_str}")

    canonical_rel_path = "/".join(cleaned_parts)

    if len(canonical_rel_path) > max_path_length:
        raise ValueError(f"Path length ({len(canonical_rel_path)}) exceeds maximum permitted ({max_path_length})")

    # Duplicate alias detection using case-folded path for universal portable safety
    if seen_canonical_paths is not None:
        lookup_key = canonical_rel_path.casefold()
        if lookup_key in seen_canonical_paths:
            raise ValueError(f"Canonical path collision / colliding path alias detected for archive member: {canonical_rel_path}")
        seen_canonical_paths.add(lookup_key)

    return canonical_rel_path


class SafeArtifactExtractor:
    """Extracts and verifies release archives with strict traversal prevention, link rejection, and quarantine staging."""

    def __init__(
        self,
        allow_symlinks: bool = False,
        allow_hardlinks: bool = False,
        max_archive_bytes: int = 100 * 1024 * 1024,  # 100 MB compressed
        max_expansion_ratio: float = 50.0,
        max_files: int = 10000,
        max_total_bytes: int = 200 * 1024 * 1024,  # 200 MB extracted
        max_file_size: int = 50 * 1024 * 1024,  # 50 MB single file
        max_path_length: int = 255,
    ) -> None:
        self.allow_symlinks = allow_symlinks
        self.allow_hardlinks = allow_hardlinks
        self.max_archive_bytes = max_archive_bytes
        self.max_expansion_ratio = max_expansion_ratio
        self.max_files = max_files
        self.max_total_bytes = max_total_bytes
        self.max_file_size = max_file_size
        self.max_path_length = max_path_length

    def extract_and_verify(
        self,
        archive_path: Path | str,
        target_dir: Path | str,
        manifest: ReleaseManifest,
        strict_mode: bool = True,
    ) -> None:
        """Safely unpacks archive into a quarantine folder, verifies all file digests, and atomically moves to target_dir."""
        arch_p = Path(archive_path).resolve()
        dest_p = Path(target_dir).resolve()
        dest_p.parent.mkdir(parents=True, exist_ok=True)

        archive_size = arch_p.stat().st_size
        if archive_size == 0:
            raise ValueError("Release archive is empty (0 bytes).")

        if archive_size > self.max_archive_bytes:
            raise ValueError(f"Archive compressed size ({archive_size} bytes) exceeds limit ({self.max_archive_bytes} bytes).")

        # Create isolated quarantine directory
        quarantine_p = dest_p.parent / f"{dest_p.name}.incoming.{uuid.uuid4().hex[:8]}"
        quarantine_p.mkdir(parents=True, exist_ok=False)

        try:
            total_bytes = 0
            file_count = 0
            seen_canonical: set[str] = set()
            member_canonical_map: dict[tarfile.TarInfo, str] = {}

            with tarfile.open(arch_p, mode="r:*") as tar:
                members = tar.getmembers()

                if len(members) > self.max_files:
                    raise ValueError(f"Archive entry count ({len(members)}) exceeds limit ({self.max_files}).")

                # Pre-scan and validate all members
                for member in members:
                    canonical_path = sanitize_and_validate_path(
                        member.name,
                        seen_canonical_paths=seen_canonical,
                        max_path_length=self.max_path_length,
                    )
                    member_canonical_map[member] = canonical_path

                    if member.issym():
                        if not self.allow_symlinks:
                            raise ValueError(f"Archive contains forbidden symbolic link: {member.name}")
                        link_target = member.linkname
                        if ".." in link_target or link_target.startswith("/") or re.match(r"^[a-zA-Z]:", link_target):
                            raise ValueError(f"Symbolic link escapes extraction target: {member.name} -> {link_target}")

                    elif member.islnk():
                        if not self.allow_hardlinks:
                            raise ValueError(f"Archive contains forbidden hard link: {member.name}")
                        link_target = member.linkname
                        if ".." in link_target or link_target.startswith("/") or re.match(r"^[a-zA-Z]:", link_target):
                            raise ValueError(f"Hard link escapes extraction target: {member.name} -> {link_target}")

                    elif member.isdev() or member.ischr() or member.isblk() or member.isfifo():
                        raise ValueError(f"Archive contains forbidden special device entry: {member.name}")

                    elif member.isreg():
                        file_count += 1
                        if file_count > self.max_files:
                            raise ValueError(f"Archive file count exceeded maximum limit ({self.max_files}).")

                        if member.size > self.max_file_size:
                            raise ValueError(f"Archive member {member.name} size ({member.size}) exceeds limit ({self.max_file_size}).")

                        total_bytes += member.size
                        if total_bytes > self.max_total_bytes:
                            raise ValueError(f"Total extracted bytes ({total_bytes}) exceeds limit ({self.max_total_bytes}).")

                # Check compression expansion ratio
                expansion_ratio = total_bytes / max(archive_size, 1)
                if expansion_ratio > self.max_expansion_ratio:
                    raise ValueError(
                        f"Decompression expansion ratio ({expansion_ratio:.1f}x) exceeds limit ({self.max_expansion_ratio:.1f}x)."
                    )

                # Extract validated members member-by-member using canonical destinations
                for member in members:
                    canonical_rel = member_canonical_map[member]
                    dest_file_path = (quarantine_p / canonical_rel).resolve()

                    # Confirm destination remains inside quarantine root using path-aware containment
                    if not dest_file_path.is_relative_to(quarantine_p):
                        raise ValueError(f"Extraction path escapes quarantine root: {dest_file_path}")

                    if member.isdir():
                        dest_file_path.mkdir(parents=True, exist_ok=True)
                    elif member.isreg():
                        dest_file_path.parent.mkdir(parents=True, exist_ok=True)
                        extracted_f = tar.extractfile(member)
                        if extracted_f is None:
                            raise ValueError(f"Failed to extract regular file: {member.name}")
                        with open(dest_file_path, "wb") as out_fp:
                            shutil.copyfileobj(extracted_f, out_fp)

            # Post-extraction file verification
            self._verify_extracted_files(quarantine_p, manifest, strict_mode=strict_mode)

            # If destination already exists, remove it cleanly
            if dest_p.exists():
                if dest_p.is_dir():
                    shutil.rmtree(dest_p)
                else:
                    dest_p.unlink()

            # Atomically move quarantine directory to target_dir
            shutil.move(str(quarantine_p), str(dest_p))

        except Exception as e:
            # Clean up quarantine folder on failure
            if quarantine_p.exists():
                shutil.rmtree(quarantine_p, ignore_errors=True)
            raise ValueError(f"Safe extraction failed: {e}") from e

    def _verify_extracted_files(self, extracted_root: Path, manifest: ReleaseManifest, strict_mode: bool = True) -> None:
        """Recalculates SHA-256 for all extracted files and verifies match with manifest."""
        manifest_map = {f.path.replace("\\", "/"): f.sha256 for f in manifest.files}
        found_files: set[str] = set()

        for root, _, files in os.walk(extracted_root):
            for f in files:
                full_path = Path(root) / f
                rel_path = os.path.relpath(full_path, extracted_root).replace("\\", "/")
                found_files.add(rel_path)

                if rel_path not in manifest_map:
                    if strict_mode:
                        raise ValueError(f"Extracted file '{rel_path}' is not declared in release manifest.")
                    continue

                with open(full_path, "rb") as fp:
                    content = fp.read()
                actual_sha = hashlib.sha256(content).hexdigest()
                expected_sha = manifest_map[rel_path]

                if actual_sha != expected_sha:
                    raise ValueError(f"Extracted file digest mismatch for '{rel_path}': expected {expected_sha}, got {actual_sha}")

        # Check for missing manifest files
        missing_files = set(manifest_map.keys()) - found_files
        if missing_files:
            raise ValueError(f"Required release files missing after extraction: {sorted(missing_files)}")
