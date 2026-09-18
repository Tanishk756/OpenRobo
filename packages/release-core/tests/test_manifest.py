"""Unit tests for Release Manifest canonical serialization and digests."""

import json

from openrobo_release import (
    FileEntry,
    ReleaseManifest,
    ReleaseTarget,
    canonical_manifest_bytes,
    compute_manifest_digest,
    compute_workspace_digest,
)


def test_canonical_manifest_bytes_determinism():
    """Prove that regardless of dictionary key order, canonical representation is identical."""
    m1 = ReleaseManifest(
        release_id="rel_20260918_001",
        release_version="1.0.0",
        created_at="2026-09-18T12:00:00Z",
        workspace_digest="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        artifact_digest="bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        target=ReleaseTarget(operating_system="linux", architecture="x86_64", ros_distro="humble"),
        files=[
            FileEntry(path="src/node.py", sha256="1111111111111111111111111111111111111111111111111111111111111111", size_bytes=100),
            FileEntry(path="launch/main.py", sha256="2222222222222222222222222222222222222222222222222222222222222222", size_bytes=200),
        ],
        release_key_id="rel-key-01",
    )

    bytes1 = canonical_manifest_bytes(m1)
    digest1 = compute_manifest_digest(bytes1)

    # Convert to dict, shuffle keys, and canonicalize
    d = json.loads(bytes1.decode("utf-8"))
    shuffled_d = {k: d[k] for k in sorted(d.keys(), reverse=True)}

    bytes2 = canonical_manifest_bytes(shuffled_d)
    digest2 = compute_manifest_digest(bytes2)

    assert bytes1 == bytes2
    assert digest1 == digest2
    assert isinstance(digest1, str)
    assert len(digest1) == 64


def test_workspace_digest_computation():
    """Verify workspace tree digest computation over file entries."""
    files = [
        FileEntry(path="b.txt", sha256="bbbb", size_bytes=10),
        FileEntry(path="a.txt", sha256="aaaa", size_bytes=20),
    ]
    digest = compute_workspace_digest(files)
    assert isinstance(digest, str)
    assert len(digest) == 64

    # Order permutation yields identical digest because compute_workspace_digest sorts by path
    files_reversed = list(reversed(files))
    digest_rev = compute_workspace_digest(files_reversed)
    assert digest == digest_rev
