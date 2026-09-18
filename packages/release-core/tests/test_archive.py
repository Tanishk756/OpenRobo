"""Unit tests for Deterministic Archive creation and Secret Exclusion."""

import tarfile

from openrobo_release import create_deterministic_archive


def test_deterministic_archive_hash_stability(tmp_path):
    """Prove that archiving the same workspace files twice produces identical artifact SHA-256."""
    ws_dir = tmp_path / "workspace"
    ws_dir.mkdir()
    (ws_dir / "src").mkdir()
    (ws_dir / "src" / "node.py").write_text("import rclpy\nprint('hello')", encoding="utf-8")
    (ws_dir / "package.xml").write_text("<package><name>my_pkg</name></package>", encoding="utf-8")

    out1 = tmp_path / "release1.tar.gz"
    out2 = tmp_path / "release2.tar.gz"

    _, digest1, ws_digest1, files1 = create_deterministic_archive(ws_dir, out1)
    _, digest2, ws_digest2, files2 = create_deterministic_archive(ws_dir, out2)

    assert digest1 == digest2
    assert ws_digest1 == ws_digest2
    assert len(files1) == len(files2) == 2


def test_secret_exclusion_filters_sensitive_files(tmp_path):
    """Prove that private keys, credentials, .env files, and cache directories are excluded."""
    ws_dir = tmp_path / "workspace_with_secrets"
    ws_dir.mkdir()

    # Legitimate files
    (ws_dir / "app.py").write_text("print('app')", encoding="utf-8")
    (ws_dir / "README.md").write_text("# Readme", encoding="utf-8")

    # Forbidden secrets & caches
    (ws_dir / "server.key").write_text("-----BEGIN PRIVATE KEY-----", encoding="utf-8")
    (ws_dir / "cert.pem").write_text("-----BEGIN CERTIFICATE-----", encoding="utf-8")
    (ws_dir / ".env").write_text("SECRET_KEY=12345", encoding="utf-8")
    (ws_dir / ".env.production").write_text("API_KEY=xyz", encoding="utf-8")
    (ws_dir / "id_rsa").write_text("ssh-rsa secret", encoding="utf-8")
    (ws_dir / "token.txt").write_text("orb_tok_secret", encoding="utf-8")

    pycache_dir = ws_dir / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "app.cpython-311.pyc").write_bytes(b"\x00\x00\x00")

    out_tar = tmp_path / "filtered_release.tar.gz"
    _, _, _, files = create_deterministic_archive(ws_dir, out_tar)

    packaged_paths = [f.path for f in files]
    assert "app.py" in packaged_paths
    assert "README.md" in packaged_paths

    # Confirm secrets are excluded
    assert "server.key" not in packaged_paths
    assert "cert.pem" not in packaged_paths
    assert ".env" not in packaged_paths
    assert ".env.production" not in packaged_paths
    assert "id_rsa" not in packaged_paths
    assert "token.txt" not in packaged_paths
    assert "__pycache__/app.cpython-311.pyc" not in packaged_paths

    # Verify tar content directly
    with tarfile.open(out_tar, "r:gz") as tar:
        names = tar.getnames()
        assert "server.key" not in names
        assert ".env" not in names
