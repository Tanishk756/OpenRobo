"""Unit tests for Safe Artifact Extraction and Malicious Archive Resistance."""

import io
import tarfile

import pytest
from openrobo_release import (
    ReleaseManifest,
    ReleaseTarget,
    SafeArtifactExtractor,
    create_deterministic_archive,
)


@pytest.fixture
def valid_workspace_and_manifest(tmp_path):
    ws_dir = tmp_path / "valid_ws"
    ws_dir.mkdir()
    (ws_dir / "src").mkdir()
    (ws_dir / "src" / "main.py").write_text("print('running')", encoding="utf-8")
    (ws_dir / "config.yaml").write_text("rate: 10", encoding="utf-8")

    archive_path = tmp_path / "valid.tar.gz"
    _, art_digest, ws_digest, files = create_deterministic_archive(ws_dir, archive_path)

    manifest = ReleaseManifest(
        release_id="rel_valid_001",
        release_version="1.0.0",
        created_at="2026-09-18T12:00:00Z",
        workspace_digest=ws_digest,
        artifact_digest=art_digest,
        target=ReleaseTarget(operating_system="linux", architecture="x86_64"),
        files=files,
        release_key_id="test-key",
    )

    return archive_path, manifest


def test_safe_extraction_success(tmp_path, valid_workspace_and_manifest):
    """Prove that a valid archive extracts cleanly and verifies all file hashes."""
    archive_path, manifest = valid_workspace_and_manifest
    extract_dest = tmp_path / "extracted_valid"

    extractor = SafeArtifactExtractor()
    ok, msg, details = extractor.extract_archive(archive_path, extract_dest, manifest=manifest)

    assert ok is True
    assert (extract_dest / "src" / "main.py").exists()
    assert (extract_dest / "config.yaml").exists()
    assert details["target_dir"] == str(extract_dest.resolve())


def test_reject_relative_path_traversal(tmp_path):
    """Prove that archives with '../' traversal sequences are rejected."""
    bad_tar = tmp_path / "traversal.tar.gz"
    with tarfile.open(bad_tar, "w:gz") as tar:
        data = b"malicious content"
        ti = tarfile.TarInfo(name="../../escaped.txt")
        ti.size = len(data)
        tar.addfile(ti, io.BytesIO(data))

    extractor = SafeArtifactExtractor()
    ok, msg, _ = extractor.extract_archive(bad_tar, tmp_path / "dest")
    assert ok is False
    assert "Path traversal sequence '..' forbidden" in msg


def test_reject_absolute_path_traversal(tmp_path):
    """Prove that archives with absolute paths are rejected."""
    bad_tar = tmp_path / "absolute.tar.gz"
    with tarfile.open(bad_tar, "w:gz") as tar:
        data = b"malicious content"
        ti = tarfile.TarInfo(name="/etc/passwd")
        ti.size = len(data)
        tar.addfile(ti, io.BytesIO(data))

    extractor = SafeArtifactExtractor()
    ok, msg, _ = extractor.extract_archive(bad_tar, tmp_path / "dest")
    assert ok is False
    assert "Absolute or UNC path forbidden" in msg


def test_reject_windows_drive_path(tmp_path):
    r"""Prove that archives with Windows drive paths (e.g. C:\) are rejected."""
    bad_tar = tmp_path / "drive.tar.gz"
    with tarfile.open(bad_tar, "w:gz") as tar:
        data = b"malicious content"
        ti = tarfile.TarInfo(name="C:/Windows/malicious.dll")
        ti.size = len(data)
        tar.addfile(ti, io.BytesIO(data))

    extractor = SafeArtifactExtractor()
    ok, msg, _ = extractor.extract_archive(bad_tar, tmp_path / "dest")
    assert ok is False
    assert "Windows drive path forbidden" in msg


def test_reject_symlink_escaping_extraction_root(tmp_path):
    """Prove that symlinks pointing outside the target extraction root are rejected."""
    bad_tar = tmp_path / "symlink_escape.tar.gz"
    with tarfile.open(bad_tar, "w:gz") as tar:
        ti = tarfile.TarInfo(name="link_to_etc")
        ti.type = tarfile.SYMTYPE
        ti.linkname = "../../etc/shadow"
        tar.addfile(ti)

    extractor = SafeArtifactExtractor()
    ok, msg, _ = extractor.extract_archive(bad_tar, tmp_path / "dest")
    assert ok is False
    assert "Symlink 'link_to_etc' targets outside extraction root" in msg


def test_reject_archive_bomb_file_count_limit(tmp_path):
    """Prove that archives exceeding maximum file count limits are rejected."""
    bad_tar = tmp_path / "many_files.tar.gz"
    with tarfile.open(bad_tar, "w:gz") as tar:
        for i in range(15):
            ti = tarfile.TarInfo(name=f"file_{i}.txt")
            ti.size = 0
            tar.addfile(ti, io.BytesIO(b""))

    extractor = SafeArtifactExtractor(max_file_count=10)
    ok, msg, _ = extractor.extract_archive(bad_tar, tmp_path / "dest")
    assert ok is False
    assert "exceeding maximum limit of 10" in msg


def test_post_extraction_digest_mismatch_detected(tmp_path, valid_workspace_and_manifest):
    """Prove that modified extracted content triggers post-extraction failure."""
    archive_path, manifest = valid_workspace_and_manifest
    extract_dest = tmp_path / "tampered_extract"

    # Modify manifest expectation so it doesn't match actual archive
    manifest.files[0].sha256 = "0000000000000000000000000000000000000000000000000000000000000000"

    extractor = SafeArtifactExtractor()
    ok, msg, _ = extractor.extract_archive(archive_path, extract_dest, manifest=manifest)
    assert ok is False
    assert "File digest mismatch" in msg
