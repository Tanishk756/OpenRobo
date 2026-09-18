"""Adversarial security tests for safe artifact extraction, quarantine isolation, and canonical path sanitization."""

import io
import tarfile

import pytest
from openrobo_release.archive import create_deterministic_archive
from openrobo_release.extraction import SafeArtifactExtractor
from openrobo_release.models import FileEntry, ReleaseManifest, ReleaseTarget


def _make_archive(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, data in entries.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


@pytest.fixture
def valid_manifest() -> ReleaseManifest:
    return ReleaseManifest(
        release_id="rel-extract-001",
        release_version="1.0.0",
        created_at="2026-09-18T00:00:00Z",
        workspace_digest="sha256:dummy",
        artifact_digest="sha256:dummy",
        target=ReleaseTarget(operating_system="linux", architecture="x86_64"),
        files=[FileEntry(path="src/main.py", sha256="b45cffe084dd3d20d928bee85e7b0f21", size_bytes=14)],
        release_key_id="key-1",
    )


def test_safe_extraction_success(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "main.py").write_text("print('test')", encoding="utf-8")

    out_tar = tmp_path / "release.tar.gz"
    target = ReleaseTarget(operating_system="linux", architecture="x86_64")
    man, _ = create_deterministic_archive(ws, out_tar, target, "rel-1", "1.0.0", "k1")

    extractor = SafeArtifactExtractor()
    dest = tmp_path / "extracted"
    extractor.extract_and_verify(out_tar, dest, man)

    assert (dest / "main.py").exists()
    assert (dest / "main.py").read_text(encoding="utf-8") == "print('test')"


def test_reject_traversal_archive(tmp_path, valid_manifest):
    arch_bytes = _make_archive({"../escape.py": b"evil"})
    tar_file = tmp_path / "evil.tar.gz"
    tar_file.write_bytes(arch_bytes)

    extractor = SafeArtifactExtractor()
    with pytest.raises(ValueError, match="path traversal"):
        extractor.extract_and_verify(tar_file, tmp_path / "dest", valid_manifest)


def test_reject_absolute_path_archive(tmp_path, valid_manifest):
    arch_bytes = _make_archive({"/etc/passwd": b"evil"})
    tar_file = tmp_path / "evil.tar.gz"
    tar_file.write_bytes(arch_bytes)

    extractor = SafeArtifactExtractor()
    with pytest.raises(ValueError, match="absolute path"):
        extractor.extract_and_verify(tar_file, tmp_path / "dest", valid_manifest)


def test_reject_windows_drive_archive(tmp_path, valid_manifest):
    arch_bytes = _make_archive({"C:/Windows/System32/evil.dll": b"evil"})
    tar_file = tmp_path / "evil.tar.gz"
    tar_file.write_bytes(arch_bytes)

    extractor = SafeArtifactExtractor()
    with pytest.raises(ValueError, match="Windows drive"):
        extractor.extract_and_verify(tar_file, tmp_path / "dest", valid_manifest)


def test_reject_symlink_archive_by_default(tmp_path, valid_manifest):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        info = tarfile.TarInfo(name="link.txt")
        info.type = tarfile.SYMTYPE
        info.linkname = "target.txt"
        tar.addfile(info)

    tar_file = tmp_path / "symlink.tar.gz"
    tar_file.write_bytes(buf.getvalue())

    extractor = SafeArtifactExtractor(allow_symlinks=False)
    with pytest.raises(ValueError, match="forbidden symbolic link"):
        extractor.extract_and_verify(tar_file, tmp_path / "dest", valid_manifest)


def test_reject_canonical_duplicate_alias(tmp_path, valid_manifest):
    # Archive with alias collisions: a/b and a/./b
    arch_bytes = _make_archive({"src/app.py": b"1", "src/./app.py": b"2"})
    tar_file = tmp_path / "alias.tar.gz"
    tar_file.write_bytes(arch_bytes)

    extractor = SafeArtifactExtractor()
    with pytest.raises(ValueError, match="colliding path alias"):
        extractor.extract_and_verify(tar_file, tmp_path / "dest", valid_manifest)


def test_reject_windows_reserved_device_names(tmp_path, valid_manifest):
    arch_bytes = _make_archive({"con.txt": b"reserved"})
    tar_file = tmp_path / "reserved.tar.gz"
    tar_file.write_bytes(arch_bytes)

    extractor = SafeArtifactExtractor()
    with pytest.raises(ValueError, match="Windows reserved device name"):
        extractor.extract_and_verify(tar_file, tmp_path / "dest", valid_manifest)


def test_reject_control_characters_in_path(tmp_path, valid_manifest):
    arch_bytes = _make_archive({"src/test\x07file.py": b"bell"})
    tar_file = tmp_path / "ctrl.tar.gz"
    tar_file.write_bytes(arch_bytes)

    extractor = SafeArtifactExtractor()
    with pytest.raises(ValueError, match="control character"):
        extractor.extract_and_verify(tar_file, tmp_path / "dest", valid_manifest)


def test_reject_expansion_ratio_bomb(tmp_path, valid_manifest):
    # Highly compressible zeroes exceeding 2x ratio limit
    large_zeroes = b"\x00" * (100 * 1024)
    arch_bytes = _make_archive({"src/large.bin": large_zeroes})
    tar_file = tmp_path / "bomb.tar.gz"
    tar_file.write_bytes(arch_bytes)

    extractor = SafeArtifactExtractor(max_expansion_ratio=2.0)
    with pytest.raises(ValueError, match="expansion ratio"):
        extractor.extract_and_verify(tar_file, tmp_path / "dest", valid_manifest)


def test_quarantine_cleanup_on_failure(tmp_path, valid_manifest):
    # Archive with traversal that fails mid-extraction
    arch_bytes = _make_archive({"../outside.txt": b"bad"})
    tar_file = tmp_path / "fail.tar.gz"
    tar_file.write_bytes(arch_bytes)

    dest = tmp_path / "staging_target"
    extractor = SafeArtifactExtractor()
    with pytest.raises(ValueError):
        extractor.extract_and_verify(tar_file, dest, valid_manifest)

    # Confirm no orphan incoming quarantine directories left in parent
    incoming_dirs = list(tmp_path.glob("staging_target.incoming.*"))
    assert len(incoming_dirs) == 0
    assert not dest.exists()
