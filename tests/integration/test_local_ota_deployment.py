"""Real filesystem integration test for local signed release artifact deployment lifecycle:
v1 build -> sign -> verify -> stage -> activate -> v2 stage -> activate -> rollback to v1.
"""

from pathlib import Path

from openrobo_agent.deployment.activation import activate_staged_slot
from openrobo_agent.deployment.models import SlotState
from openrobo_agent.deployment.rollback import rollback_to_previous
from openrobo_agent.deployment.slots import ABSlotManager
from openrobo_agent.deployment.staging import stage_release_artifact
from openrobo_release.archive import create_deterministic_archive
from openrobo_release.models import KeyStatus, ReleaseTarget, TrustedReleaseKey
from openrobo_release.signing import ReleaseSigner, generate_development_keypair
from openrobo_release.trust_store import TrustedReleaseKeyStore


def _create_and_sign_release(
    ws_dir: Path,
    out_dir: Path,
    release_id: str,
    version: str,
    key_id: str,
    priv_bytes: bytes,
) -> tuple[Path, Path, Path]:
    target = ReleaseTarget(operating_system="any", architecture="any", ros_distro="humble")
    art_path = out_dir / f"openrobo-{release_id}.tar.gz"
    man_path = out_dir / f"openrobo-{release_id}.manifest.json"
    sig_path = out_dir / f"openrobo-{release_id}.sig"

    manifest, _ = create_deterministic_archive(
        workspace_dir=ws_dir,
        output_path=art_path,
        target=target,
        release_id=release_id,
        release_version=version,
        release_key_id=key_id,
    )

    signer = ReleaseSigner(priv_bytes, key_id=key_id)
    sig = signer.sign_manifest(manifest)

    man_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    sig_path.write_text(sig, encoding="utf-8")

    return art_path, man_path, sig_path


def test_full_local_ota_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    monkeypatch.setenv("ROS_DISTRO", "humble")

    # 1. Setup Trust Store with Dev Release Key
    signing_key, priv_bytes = generate_development_keypair(key_id="rel-authority-1")
    trust_dir = tmp_path / "trusted_release_keys"
    trust_store = TrustedReleaseKeyStore(trust_dir=trust_dir)
    trust_store.add_key(
        TrustedReleaseKey(
            key_id="rel-authority-1",
            public_key=signing_key.public_key_pem,
            created_at=signing_key.created_at,
            status=KeyStatus.ACTIVE,
        )
    )

    dep_root = tmp_path / "var_lib_openrobo_agent"
    manager = ABSlotManager(dep_root)

    # 2. Build Release v1.0.0
    ws1 = tmp_path / "workspace_v1"
    ws1.mkdir()
    (ws1 / "package.xml").write_text("<package><name>nav_stack</name><version>1.0.0</version></package>", encoding="utf-8")
    src1 = ws1 / "src"
    src1.mkdir()
    (src1 / "node.py").write_text("print('Navigation Stack v1.0.0 Online')", encoding="utf-8")

    dist1 = tmp_path / "dist_v1"
    art1, man1, sig1 = _create_and_sign_release(ws1, dist1, "rel-v1", "1.0.0", "rel-authority-1", priv_bytes)

    # 3. Stage & Activate Release v1.0.0 (Into Slot A)
    ok_stage1, msg1 = stage_release_artifact(manager, art1, man1, sig1, trust_store)
    assert ok_stage1 is True, msg1
    assert manager.get_slot_metadata("slot-a").state == SlotState.VERIFIED

    ok_act1, msg_act1 = activate_staged_slot(manager, slot_id="slot-a")
    assert ok_act1 is True, msg_act1
    assert manager.get_active_slot_id() == "slot-a"
    assert (manager.get_slot_dir("slot-a") / "src" / "node.py").exists()

    # 4. Build Release v2.0.0
    ws2 = tmp_path / "workspace_v2"
    ws2.mkdir()
    (ws2 / "package.xml").write_text("<package><name>nav_stack</name><version>2.0.0</version></package>", encoding="utf-8")
    src2 = ws2 / "src"
    src2.mkdir()
    (src2 / "node.py").write_text("print('Navigation Stack v2.0.0 Online')", encoding="utf-8")

    dist2 = tmp_path / "dist_v2"
    art2, man2, sig2 = _create_and_sign_release(ws2, dist2, "rel-v2", "2.0.0", "rel-authority-1", priv_bytes)

    # 5. Stage & Activate Release v2.0.0 (Into Slot B)
    ok_stage2, msg2 = stage_release_artifact(manager, art2, man2, sig2, trust_store)
    assert ok_stage2 is True, msg2
    assert manager.get_slot_metadata("slot-b").state == SlotState.VERIFIED

    ok_act2, msg_act2 = activate_staged_slot(manager, slot_id="slot-b")
    assert ok_act2 is True, msg_act2
    assert manager.get_active_slot_id() == "slot-b"
    assert manager.get_slot_metadata("slot-a").state == SlotState.PREVIOUS

    # Verify slot-a content is preserved
    assert (manager.get_slot_dir("slot-a") / "src" / "node.py").read_text(encoding="utf-8") == "print('Navigation Stack v1.0.0 Online')"

    # 6. Execute Rollback to v1.0.0
    ok_rb, msg_rb = rollback_to_previous(manager, trust_store)
    assert ok_rb is True, msg_rb
    assert manager.get_active_slot_id() == "slot-a"
    assert manager.get_slot_metadata("slot-b").state == SlotState.FAILED
    assert manager.get_slot_metadata("slot-a").state == SlotState.ACTIVE
