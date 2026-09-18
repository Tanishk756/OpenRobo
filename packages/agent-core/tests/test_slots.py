"""Unit tests for A/B Workspace Partitioning, Atomic Activation, and Mechanical Rollback."""

from datetime import datetime, timezone

import pytest
from openrobo_agent.deployment import (
    ABSlotManager,
    SlotState,
    activate_staged_slot,
    rollback_to_previous,
    stage_release_artifact,
)
from openrobo_release import (
    ReleaseManifest,
    ReleaseSigner,
    ReleaseTarget,
    ReleaseVerifier,
    create_deterministic_archive,
)


@pytest.fixture
def test_release(tmp_path):
    ws_dir = tmp_path / "sample_src_ws"
    ws_dir.mkdir()
    (ws_dir / "app.py").write_text("print('v1.0')", encoding="utf-8")

    archive_path = tmp_path / "rel_v1.tar.gz"
    _, art_digest, ws_digest, files = create_deterministic_archive(ws_dir, archive_path)

    manifest = ReleaseManifest(
        release_id="rel-v1",
        release_version="1.0.0",
        created_at=datetime.now(timezone.utc).isoformat(),
        workspace_digest=ws_digest,
        artifact_digest=art_digest,
        target=ReleaseTarget(operating_system="linux", architecture="x86_64"),
        files=files,
        release_key_id="test-key-id",
    )

    sign_key, trust_key = ReleaseSigner.generate_keypair(key_id=manifest.release_key_id)
    signer = ReleaseSigner(private_key_pem=sign_key.private_key_pem, key_id=sign_key.key_id, allow_dev=True)
    sig_b64 = signer.sign_manifest(manifest)

    verifier = ReleaseVerifier(trusted_keys=[trust_key])

    return archive_path, manifest, sig_b64, verifier, trust_key, signer


def test_ab_slot_manager_initial_state(tmp_path):
    """Prove that ABSlotManager initializes dual empty partitions."""
    slot_mgr = ABSlotManager(tmp_path / "workspaces")
    assert slot_mgr.get_active_slot() is None
    assert slot_mgr.get_inactive_slot() == "slot-a"

    meta_a = slot_mgr.get_slot_metadata("slot-a")
    meta_b = slot_mgr.get_slot_metadata("slot-b")
    assert meta_a.status == SlotState.EMPTY
    assert meta_b.status == SlotState.EMPTY


def test_staging_and_activation_lifecycle(tmp_path, test_release):
    """Prove full staging -> activation -> second staging -> activation -> rollback lifecycle."""
    archive_path, manifest_v1, sig_v1, verifier, trust_key, signer = test_release
    slot_mgr = ABSlotManager(tmp_path / "workspaces")

    # 1. Stage v1 into inactive slot (slot-a)
    ok, msg, meta_v1 = stage_release_artifact(
        slot_manager=slot_mgr,
        archive_path=archive_path,
        manifest=manifest_v1,
        signature_b64=sig_v1,
        verifier=verifier,
        agent_capabilities={"operating_system": "linux", "architecture": "x86_64", "ros_distro": "humble"},
    )
    assert ok is True
    assert meta_v1.status == SlotState.STAGED
    assert meta_v1.slot_id == "slot-a"
    assert (slot_mgr.slot_paths["slot-a"] / "app.py").exists()

    # 2. Activate slot-a
    ok, msg, act_v1 = activate_staged_slot(slot_mgr, target_slot_id="slot-a")
    assert ok is True
    assert act_v1.status == SlotState.ACTIVE
    assert slot_mgr.get_active_slot() == "slot-a"
    assert slot_mgr.get_inactive_slot() == "slot-b"

    # 3. Create release v2
    ws_v2 = tmp_path / "ws_v2"
    ws_v2.mkdir()
    (ws_v2 / "app.py").write_text("print('v2.0')", encoding="utf-8")
    archive_v2 = tmp_path / "rel_v2.tar.gz"
    _, art_digest_v2, ws_digest_v2, files_v2 = create_deterministic_archive(ws_v2, archive_v2)

    manifest_v2 = ReleaseManifest(
        release_id="rel-v2",
        release_version="2.0.0",
        created_at=datetime.now(timezone.utc).isoformat(),
        workspace_digest=ws_digest_v2,
        artifact_digest=art_digest_v2,
        target=ReleaseTarget(operating_system="linux", architecture="x86_64"),
        files=files_v2,
        release_key_id="test-key-id",
    )
    sig_v2 = signer.sign_manifest(manifest_v2)

    # 4. Stage v2 into inactive slot (slot-b)
    ok, msg, meta_v2 = stage_release_artifact(
        slot_manager=slot_mgr,
        archive_path=archive_v2,
        manifest=manifest_v2,
        signature_b64=sig_v2,
        verifier=verifier,
        agent_capabilities={"operating_system": "linux", "architecture": "x86_64", "ros_distro": "humble"},
    )
    assert ok is True
    assert meta_v2.slot_id == "slot-b"
    assert meta_v2.status == SlotState.STAGED

    # Confirm slot-a is still ACTIVE and undisturbed
    assert slot_mgr.get_slot_metadata("slot-a").status == SlotState.ACTIVE
    assert (slot_mgr.slot_paths["slot-a"] / "app.py").read_text(encoding="utf-8") == "print('v1.0')"

    # 5. Activate v2 (slot-b)
    ok, msg, act_v2 = activate_staged_slot(slot_mgr, target_slot_id="slot-b")
    assert ok is True
    assert act_v2.status == SlotState.ACTIVE
    assert slot_mgr.get_active_slot() == "slot-b"

    # Confirm slot-a transitioned to PREVIOUS without deletion
    meta_a_prev = slot_mgr.get_slot_metadata("slot-a")
    assert meta_a_prev.status == SlotState.PREVIOUS
    assert (slot_mgr.slot_paths["slot-a"] / "app.py").exists()

    # 6. Execute Rollback to previous slot (slot-a)
    ok, msg, restored_meta = rollback_to_previous(slot_mgr)
    assert ok is True
    assert restored_meta.slot_id == "slot-a"
    assert restored_meta.status == SlotState.ACTIVE
    assert slot_mgr.get_active_slot() == "slot-a"

    # Confirm slot-b marked FAILED
    assert slot_mgr.get_slot_metadata("slot-b").status == SlotState.FAILED


def test_active_slot_protected_from_overwrite(tmp_path, test_release):
    """Prove that attempting to stage directly into the active slot raises an error."""
    archive_path, manifest, sig, verifier, _, _ = test_release
    slot_mgr = ABSlotManager(tmp_path / "workspaces")

    # Manually activate slot-a
    meta_a = slot_mgr.get_slot_metadata("slot-a")
    meta_a.status = SlotState.ACTIVE
    slot_mgr.update_slot_metadata(meta_a)

    with pytest.raises(RuntimeError, match="Active slot is protected"):
        slot_mgr.prepare_staging_slot("slot-a")
