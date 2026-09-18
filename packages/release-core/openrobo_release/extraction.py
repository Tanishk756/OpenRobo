"""Safe archive extraction engine with strict path traversal, symlink, and resource safeguards."""

import hashlib
import os
import tarfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from openrobo_release.models import ReleaseManifest


class ExtractionSecurityError(Exception):
    """Raised when an archive violates extraction security constraints."""
    pass


class SafeArtifactExtractor:
    """
    Guards archive extraction against path traversal, symlink escapes, zip bombs,
    device files, and corrupted or tampered payloads.
    """

    def __init__(
        self,
        max_archive_bytes: int = 100 * 1024 * 1024,          # 100 MB
        max_file_count: int = 5000,
        max_individual_file_bytes: int = 50 * 1024 * 1024,   # 50 MB
        max_total_extracted_bytes: int = 200 * 1024 * 1024,  # 200 MB
        max_path_length: int = 250,
        allow_symlinks: bool = True,
    ):
        self.max_archive_bytes = max_archive_bytes
        self.max_file_count = max_file_count
        self.max_individual_file_bytes = max_individual_file_bytes
        self.max_total_extracted_bytes = max_total_extracted_bytes
        self.max_path_length = max_path_length
        self.allow_symlinks = allow_symlinks

    def sanitize_path(self, member_name: str, target_dir: Path) -> Path:
        """
        Validate and resolve a member path, strictly rejecting path traversal,
        absolute paths, Windows drive letters, UNC paths, and NUL bytes.
        """
        if "\0" in member_name:
            raise ExtractionSecurityError(f"Malicious NUL byte detected in path: '{member_name}'")

        # Normalize slashes
        clean_name = member_name.replace("\\", "/").strip()

        # Reject absolute paths (POSIX / or Windows \ or UNC //)
        if clean_name.startswith("/") or clean_name.startswith("//"):
            raise ExtractionSecurityError(f"Absolute or UNC path forbidden: '{member_name}'")

        # Reject Windows drive letters (e.g. C:, D:)
        if len(clean_name) >= 2 and clean_name[1] == ":":
            raise ExtractionSecurityError(f"Windows drive path forbidden: '{member_name}'")

        # Check path length
        if len(clean_name) > self.max_path_length:
            raise ExtractionSecurityError(f"Path length {len(clean_name)} exceeds limit {self.max_path_length}")

        # Split parts and check for traversal
        parts = [p for p in clean_name.split("/") if p and p != "."]
        if not parts:
            raise ExtractionSecurityError(f"Empty or root-only path in archive member: '{member_name}'")

        for part in parts:
            if part == "..":
                raise ExtractionSecurityError(f"Path traversal sequence '..' forbidden: '{member_name}'")

        resolved_target = (target_dir / Path(*parts)).resolve()
        target_root_resolved = target_dir.resolve()

        try:
            resolved_target.relative_to(target_root_resolved)
        except ValueError:
            raise ExtractionSecurityError(f"Path escapes extraction directory: '{member_name}'")

        return resolved_target

    def validate_archive_members(self, tar: tarfile.TarFile, target_dir: Path) -> List[tarfile.TarInfo]:
        """Inspect all tar members before extraction, verifying resource bounds and security constraints."""
        members = tar.getmembers()

        if len(members) > self.max_file_count:
            raise ExtractionSecurityError(
                f"Archive contains {len(members)} entries, exceeding maximum limit of {self.max_file_count}."
            )

        total_extracted_bytes = 0
        seen_paths: Set[str] = set()

        for ti in members:
            # Check for duplicate normalized entries
            norm_name = ti.name.replace("\\", "/").rstrip("/")
            if norm_name in seen_paths:
                raise ExtractionSecurityError(f"Duplicate path entry in archive: '{ti.name}'")
            seen_paths.add(norm_name)

            # Validate path safety
            dest_path = self.sanitize_path(ti.name, target_dir)

            # Check file size limits
            if ti.size > self.max_individual_file_bytes:
                raise ExtractionSecurityError(
                    f"Member '{ti.name}' size {ti.size} bytes exceeds maximum individual limit of {self.max_individual_file_bytes}."
                )

            total_extracted_bytes += ti.size
            if total_extracted_bytes > self.max_total_extracted_bytes:
                raise ExtractionSecurityError(
                    f"Total extracted size {total_extracted_bytes} bytes exceeds limit of {self.max_total_extracted_bytes}."
                )

            # Check file types
            if ti.isreg() or ti.isdir():
                pass
            elif ti.issym():
                if not self.allow_symlinks:
                    raise ExtractionSecurityError(f"Symlinks are disabled by security policy: '{ti.name}'")
                # Validate symlink target does not escape target_dir
                link_target = ti.linkname.replace("\\", "/")
                if link_target.startswith("/") or (len(link_target) >= 2 and link_target[1] == ":"):
                    raise ExtractionSecurityError(f"Absolute symlink target forbidden: '{ti.linkname}'")
                dest_dir = dest_path.parent
                resolved_link = (dest_dir / link_target).resolve()
                try:
                    resolved_link.relative_to(target_dir.resolve())
                except ValueError:
                    raise ExtractionSecurityError(f"Symlink '{ti.name}' targets outside extraction root: '{ti.linkname}'")
            elif ti.islnk():
                # Hardlink target validation
                hard_target = self.sanitize_path(ti.linkname, target_dir)
                try:
                    hard_target.relative_to(target_dir.resolve())
                except ValueError:
                    raise ExtractionSecurityError(f"Hardlink '{ti.name}' targets outside extraction root: '{ti.linkname}'")
            else:
                raise ExtractionSecurityError(f"Unsupported/unsafe special file type in archive member: '{ti.name}'")

        return members

    def extract_archive(
        self,
        archive_path: Path,
        target_dir: Path,
        manifest: Optional[ReleaseManifest] = None,
        strict_file_list: bool = True,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Safely extract archive into target_dir and verify post-extraction file hashes against manifest.
        """
        archive_path = Path(archive_path).resolve()
        target_dir = Path(target_dir).resolve()

        if not archive_path.exists():
            return False, f"Archive file does not exist: {archive_path}", {}

        archive_size = archive_path.stat().st_size
        if archive_size > self.max_archive_bytes:
            return False, f"Archive size {archive_size} bytes exceeds maximum limit of {self.max_archive_bytes}.", {}

        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            with tarfile.open(archive_path, "r:gz") as tar:
                members = self.validate_archive_members(tar, target_dir)
                tar.extractall(path=str(target_dir), members=members, filter="tar" if hasattr(tarfile, "tar_filter") else None)
        except Exception as e:
            return False, f"Archive extraction aborted due to security violation or corruption: {e}", {}

        # Post-extraction file integrity check against manifest
        if manifest is not None:
            post_ok, post_msg, details = self.verify_extracted_files(target_dir, manifest, strict=strict_file_list)
            if not post_ok:
                return False, f"Post-extraction verification failed: {post_msg}", details

        return True, "Artifact extracted and verified safely.", {"target_dir": str(target_dir)}

    def verify_extracted_files(
        self,
        extracted_dir: Path,
        manifest: ReleaseManifest,
        strict: bool = True,
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Recalculate SHA-256 for all extracted files and confirm exact match against manifest.
        """
        extracted_dir = Path(extracted_dir).resolve()
        manifest_files = {f.path: f for f in manifest.files}
        found_files: Set[str] = set()

        for expected_path, expected_entry in manifest_files.items():
            full_path = extracted_dir / expected_path
            if not full_path.exists() or not full_path.is_file():
                return False, f"Required manifest file missing after extraction: '{expected_path}'", {"missing_file": expected_path}

            sha256 = hashlib.sha256()
            size = 0
            with open(full_path, "rb") as f:
                while chunk := f.read(65536):
                    sha256.update(chunk)
                    size += len(chunk)
            actual_hash = sha256.hexdigest()

            if actual_hash != expected_entry.sha256:
                return False, f"File digest mismatch on '{expected_path}': expected {expected_entry.sha256}, actual {actual_hash}", {
                    "path": expected_path,
                    "expected_sha256": expected_entry.sha256,
                    "actual_sha256": actual_hash,
                }

            if size != expected_entry.size_bytes:
                return False, f"File size mismatch on '{expected_path}': expected {expected_entry.size_bytes}, actual {size}", {
                    "path": expected_path,
                    "expected_size": expected_entry.size_bytes,
                    "actual_size": size,
                }

            found_files.add(expected_path)

        if strict:
            # Check if any extra untracked files exist
            for root, _, filenames in os.walk(extracted_dir):
                for f in filenames:
                    rel_p = os.path.relpath(os.path.join(root, f), extracted_dir).replace("\\", "/")
                    if rel_p not in manifest_files:
                        return False, f"Unexpected extra file found in extracted directory: '{rel_p}'", {"unexpected_file": rel_p}

        return True, "All manifest files verified successfully post-extraction.", {"verified_count": len(manifest_files)}
