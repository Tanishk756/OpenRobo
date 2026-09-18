"""Tests for deterministic archive packaging, secret exclusion, and preservation of legitimate files."""

from pathlib import Path

import pytest
from openrobo_release.archive import create_deterministic_archive
from openrobo_release.models import ReleaseTarget


@pytest.fixture
def clean_workspace(tmp_path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir()
    (ws / "package.xml").write_text("<package><name>test_pkg</name></package>", encoding="utf-8")
    src = ws / "src"
    src.mkdir()
    (src / "main.py").write_text("def main(): pass", encoding="utf-8")
    (src / "tokenizer.py").write_text("class Tokenizer: pass", encoding="utf-8")  # Legitimate file containing token
    return ws


def test_deterministic_archive_hash_stability(clean_workspace, tmp_path):
    target = ReleaseTarget(operating_system="linux", architecture="x86_64")
    out1 = tmp_path / "out1.tar.gz"
    out2 = tmp_path / "out2.tar.gz"

    man1, rep1 = create_deterministic_archive(
        clean_workspace, out1, target, release_id="rel-1", release_version="1.0.0", release_key_id="k1"
    )
    man2, rep2 = create_deterministic_archive(
        clean_workspace, out2, target, release_id="rel-1", release_version="1.0.0", release_key_id="k1"
    )

    assert man1.artifact_digest == man2.artifact_digest
    assert out1.read_bytes() == out2.read_bytes()
    # Ensure tokenizer.py is included
    assert any("tokenizer.py" in f for f in rep1.included_files)


def test_secret_exclusion_blocks_release(clean_workspace, tmp_path):
    target = ReleaseTarget(operating_system="linux", architecture="x86_64")
    out = tmp_path / "out.tar.gz"

    # Add forbidden key file
    (clean_workspace / "id_rsa").write_text("SECRET RSA KEY", encoding="utf-8")

    with pytest.raises(ValueError, match="High-confidence secret file detected"):
        create_deterministic_archive(
            clean_workspace, out, target, release_id="rel-1", release_version="1.0.0", release_key_id="k1"
        )
