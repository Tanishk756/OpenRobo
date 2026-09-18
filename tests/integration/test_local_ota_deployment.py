"""End-to-End Real Filesystem Acceptance Test for Milestone 7.2.1 Signed Release & Local A/B OTA Lifecycle."""

from datetime import datetime, timezone

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


def test_real_filesystem_ota_v1_to_v2_and_rollback_acceptance(tmp_path):
    """
    Empirical Real Filesystem Acceptance:
    - Build release v1 from sample workspace
    - Sign release v1 with Ed25519 keypair
    - Stage release v1 into slot-a
    - Atomically activate slot-a
    - Build release v2 from updated workspace
    - Sign release v2
    - Stage release v2 into slot-b while slot-a remains active and undisturbed
    - Atomically activate slot-b (transitioning slot-a to PREVIOUS without file deletion)
    - Execute mechanical rollback to restore slot-a as ACTIVE
    """
    # 1. Setup Deployment Root and Keypair
    deploy_root = tmp_path / "agent_workspaces"
    slot_mgr = ABSlotManager(deploy_root)

    sign_key, trust_key = ReleaseSigner.generate_keypair(key_id="fleet-ota-release-key-01")
    signer = ReleaseSigner(private_key_pem=sign_key.private_key_pem, key_id=sign_key.key_id, allow_dev=True)
    verifier = ReleaseVerifier(trusted_keys=[trust_key])

    agent_caps = {
        "operating_system": "linux",
        "architecture": "x86_64",
        "ros_distro": "humble",
    }

    # 2. Construct Workspace v1
    ws_v1_dir = tmp_path / "workspace_v1"
    ws_v1_dir.mkdir()
    (ws_v1_dir / "package.xml").write_text("<package><name>nav_stack</name><version>1.0.0</version></package>", encoding="utf-8")
    (ws_v1_dir / "src").mkdir()
    (ws_v1_dir / "src" / "nav_node.py").write_text("def run():\n    print('Nav Node v1.0.0 Online')\n", encoding="utf-8")
    (ws_v1_dir / "launch").mkdir()
    (ws_v1_dir / "launch" / "nav.launch.py").write_text("# Launch v1.0.0\n", encoding="utf-8")

    archive_v1 = tmp_path / "release_v1.tar.gz"
    _, art_digest_v1, ws_digest_v1, files_v1 = create_deterministic_archive(ws_v1_dir, archive_v1)

    manifest_v1 = ReleaseManifest(
        release_id="rel-nav-1.0.0",
        release_version="1.0.0",
        created_at=datetime.now(timezone.utc).isoformat(),
        workspace_digest=ws_digest_v1,
        artifact_digest=art_digest_v1,
        target=ReleaseTarget(operating_system="linux", architecture="x86_64", ros_distro="humble"),
        files=files_v1,
        release_key_id=sign_key.key_id,
    )
    sig_v1 = signer.sign_manifest(manifest_v1)

    # 3. Stage and Activate v1 into slot-a
    ok_stage_1, msg_stage_1, meta_stage_1 = stage_release_artifact(
        slot_manager=slot_mgr,
        archive_path=archive_v1,
        manifest=manifest_v1,
        signature_b64=sig_v1,
        verifier=verifier,
        agent_capabilities=agent_caps,
    )
    assert ok_stage_1 is True
    assert meta_stage_1.slot_id == "slot-a"
    assert meta_stage_1.status == SlotState.STAGED

    ok_act_1, msg_act_1, meta_act_1 = activate_staged_slot(slot_mgr, target_slot_id="slot-a")
    assert ok_act_1 is True
    assert meta_act_1.status == SlotState.ACTIVE
    assert slot_mgr.get_active_slot() == "slot-a"
    node_v1 = (slot_mgr.slot_paths["slot-a"] / "src" / "nav_node.py").read_text(encoding="utf-8")
    assert node_v1 == "def run():\n    print('Nav Node v1.0.0 Online')\n"

    # 4. Construct Workspace v2
    ws_v2_dir = tmp_path / "workspace_v2"
    ws_v2_dir.mkdir()
    (ws_v2_dir / "package.xml").write_text("<package><name>nav_stack</name><version>2.0.0</version></package>", encoding="utf-8")
    (ws_v2_dir / "src").mkdir()
    (ws_v2_dir / "src" / "nav_node.py").write_text("def run():\n    print('Nav Node v2.0.0 Optimized Online')\n", encoding="utf-8")
    (ws_v2_dir / "launch").mkdir()
    (ws_v2_dir / "launch" / "nav.launch.py").write_text("# Launch v2.0.0\n", encoding="utf-8")

    archive_v2 = tmp_path / "release_v2.tar.gz"
    _, art_digest_v2, ws_digest_v2, files_v2 = create_deterministic_archive(ws_v2_dir, archive_v2)

    manifest_v2 = ReleaseManifest(
        release_id="rel-nav-2.0.0",
        release_version="2.0.0",
        created_at=datetime.now(timezone.utc).isoformat(),
        workspace_digest=ws_digest_v2,
        artifact_digest=art_digest_v2,
        target=ReleaseTarget(operating_system="linux", architecture="x86_64", ros_distro="humble"),
        files=files_v2,
        release_key_id=sign_key.key_id,
    )
    sig_v2 = signer.sign_manifest(manifest_v2)

    # 5. Stage v2 into inactive slot (slot-b) while slot-a remains ACTIVE
    ok_stage_2, msg_stage_2, meta_stage_2 = stage_release_artifact(
        slot_manager=slot_mgr,
        archive_path=archive_v2,
        manifest=manifest_v2,
        signature_b64=sig_v2,
        verifier=verifier,
        agent_capabilities=agent_caps,
    )
    assert ok_stage_2 is True
    assert meta_stage_2.slot_id == "slot-b"
    assert meta_stage_2.status == SlotState.STAGED
    # Verify active slot-a was not modified or overwritten
    assert slot_mgr.get_active_slot() == "slot-a"
    node_v1 = (slot_mgr.slot_paths["slot-a"] / "src" / "nav_node.py").read_text(encoding="utf-8")
    assert node_v1 == "def run():\n    print('Nav Node v1.0.0 Online')\n"

    # 6. Activate v2 (slot-b)
    ok_act_2, msg_act_2, meta_act_2 = activate_staged_slot(slot_mgr, target_slot_id="slot-b")
    assert ok_act_2 is True
    assert meta_act_2.status == SlotState.ACTIVE
    assert slot_mgr.get_active_slot() == "slot-b"
    node_v2 = (slot_mgr.slot_paths["slot-b"] / "src" / "nav_node.py").read_text(encoding="utf-8")
    assert node_v2 == "def run():\n    print('Nav Node v2.0.0 Optimized Online')\n"

    # Verify slot-a is preserved as PREVIOUS
    meta_a_prev = slot_mgr.get_slot_metadata("slot-a")
    assert meta_a_prev.status == SlotState.PREVIOUS
    assert (slot_mgr.slot_paths["slot-a"] / "src" / "nav_node.py").exists()

    # 7. Execute Rollback back to slot-a
    ok_rb, msg_rb, meta_restored = rollback_to_previous(slot_mgr)
    assert ok_rb is True
    assert meta_restored.slot_id == "slot-a"
    assert meta_restored.status == SlotState.ACTIVE
    assert slot_mgr.get_active_slot() == "slot-a"
    node_v1 = (slot_mgr.slot_paths["slot-a"] / "src" / "nav_node.py").read_text(encoding="utf-8")
    assert node_v1 == "def run():\n    print('Nav Node v1.0.0 Online')\n"

    # Verify slot-b is marked FAILED
    meta_b_failed = slot_mgr.get_slot_metadata("slot-b")
    assert meta_b_failed.status == SlotState.FAILED
