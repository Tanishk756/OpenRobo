"""Tests for ABSlotManager, crash consistency, rollback integrity, and trust store resolution."""

import json
from pathlib import Path

import pytest
from openrobo_agent.deployment.activation import activate_staged_slot
from openrobo_agent.deployment.models import SlotState
from openrobo_agent.deployment.rollback import rollback_to_previous
from openrobo_agent.deployment.slots import ABSlotManager
from openrobo_agent.deployment.staging import stage_release_artifact
from openrobo_release.archive import create_deterministic_archive
from openrobo_release.models import (
    KeyStatus,
    ReleaseTarget,
    TrustedReleaseKey,
)
from openrobo_release.signing import ReleaseSigner, generate_development_keypair
from openrobo_release.trust_store import TrustedReleaseKeyStore


@pytest.fixture
def test_pki(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROBO_DEV_RELEASE_SIGNING", "true")
    key_meta, priv_bytes = generate_development_keypair(key_id="test-key-01")

    trust_dir = tmp_path / "trusted_keys"
    store = TrustedReleaseKeyStore(trust_dir=trust_dir)
    store.add_key(
        TrustedReleaseKey(
            key_id="test-key-01",
            public_key=key_meta.public_key_pem,
            created_at="2026-09-18T00:00:00Z",
            status=KeyStatus.ACTIVE,
        )
    )
    return store, priv_bytes, "test-key-01"


def _build_release(ws_dir: Path, out_dir: Path, release_id: str, version: str, key_id: str, priv_bytes: bytes):
    target = ReleaseTarget(operating_system="any", architecture="any")
    art_path = out_dir / f"rel-{release_id}.tar.gz"
    man_path = out_dir / f"rel-{release_id}.manifest.json"
    sig_path = out_dir / f"rel-{release_id}.sig"

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


def test_slot_initial_state(tmp_path):
    manager = ABSlotManager(tmp_path / "deploy")
    assert manager.get_active_slot_id() is None
    assert manager.get_inactive_slot_id() == "slot-a"
    assert manager.get_slot_metadata("slot-a").state == SlotState.EMPTY
    assert manager.get_slot_metadata("slot-b").state == SlotState.EMPTY


def test_staging_and_verified_only_activation(tmp_path, test_pki):
    store, priv_bytes, key_id = test_pki
    ws = tmp_path / "ws1"
    ws.mkdir()
    (ws / "main.py").write_text("print('v1')", encoding="utf-8")

    out_dir = tmp_path / "dist"
    art_p, man_p, sig_p = _build_release(ws, out_dir, "rel-v1", "1.0.0", key_id, priv_bytes)

    manager = ABSlotManager(tmp_path / "deploy")

    # Staging
    ok, msg = stage_release_artifact(manager, art_p, man_p, sig_p, store)
    assert ok is True, msg
    assert manager.get_slot_metadata("slot-a").state == SlotState.VERIFIED

    # Activation requires VERIFIED (un-verified slot cannot be activated)
    ok_act, msg_act = activate_staged_slot(manager, slot_id="slot-b")
    assert ok_act is False
    assert "cannot be activated" in msg_act

    # Activate slot-a
    ok_act_a, msg_act_a = activate_staged_slot(manager, slot_id="slot-a")
    assert ok_act_a is True, msg_act_a
    assert manager.get_active_slot_id() == "slot-a"
    assert manager.get_slot_metadata("slot-a").state == SlotState.ACTIVE


def test_crash_intent_journal_startup_reconciliation(tmp_path):
    dep_root = tmp_path / "deploy_crash"
    dep_root.mkdir()

    # Create an interrupted activation journal where pointer was switched to slot-b
    (dep_root / "current.ptr").write_text("slot-b", encoding="utf-8")
    journal_file = dep_root / "activation.intent.json"
    journal_file.write_text(
        json.dumps({
            "transaction_id": "tx-123",
            "from_slot": "slot-a",
            "to_slot": "slot-b",
            "release_id": "rel-002",
            "state": "SWITCHED",
            "created_at": "2026-09-18T00:00:00Z",
        }),
        encoding="utf-8",
    )

    manager = ABSlotManager(dep_root)
    assert manager.get_active_slot_id() == "slot-b"
    assert manager.get_slot_metadata("slot-b").state == SlotState.ACTIVE
    assert manager.get_slot_metadata("slot-a").state == SlotState.PREVIOUS
    assert not journal_file.exists()


def test_rollback_rejects_tampered_candidate(tmp_path, test_pki):
    store, priv_bytes, key_id = test_pki
    manager = ABSlotManager(tmp_path / "deploy_tamper")

    # Stage & activate v1
    ws1 = tmp_path / "ws1"
    ws1.mkdir()
    (ws1 / "main.py").write_text("print('v1')", encoding="utf-8")
    art1, man1, sig1 = _build_release(ws1, tmp_path / "dist1", "rel-1", "1.0.0", key_id, priv_bytes)
    ok1, m1 = stage_release_artifact(manager, art1, man1, sig1, store)
    assert ok1 is True, m1
    ok_act1, ma1 = activate_staged_slot(manager, "slot-a")
    assert ok_act1 is True, ma1

    # Stage & activate v2
    ws2 = tmp_path / "ws2"
    ws2.mkdir()
    (ws2 / "main.py").write_text("print('v2')", encoding="utf-8")
    art2, man2, sig2 = _build_release(ws2, tmp_path / "dist2", "rel-2", "2.0.0", key_id, priv_bytes)
    ok2, m2 = stage_release_artifact(manager, art2, man2, sig2, store)
    assert ok2 is True, m2
    ok_act2, ma2 = activate_staged_slot(manager, "slot-b")
    assert ok_act2 is True, ma2

    # Tamper with slot-a content
    (manager.get_slot_dir("slot-a") / "main.py").write_text("print('tampered')", encoding="utf-8")

    # Rollback must be rejected
    ok_rb, msg_rb = rollback_to_previous(manager, store)
    assert ok_rb is False
    assert "tampered" in msg_rb.lower() or "mismatch" in msg_rb.lower()
    assert manager.get_active_slot_id() == "slot-b"
    assert manager.get_slot_metadata("slot-a").state == SlotState.QUARANTINED


def test_rollback_rejects_revoked_key(tmp_path, test_pki):
    store, priv_bytes, key_id = test_pki
    manager = ABSlotManager(tmp_path / "deploy_revoked")

    # Stage & activate v1
    ws1 = tmp_path / "ws1"
    ws1.mkdir()
    (ws1 / "main.py").write_text("print('v1')", encoding="utf-8")
    art1, man1, sig1 = _build_release(ws1, tmp_path / "dist1", "rel-1", "1.0.0", key_id, priv_bytes)
    ok1, m1 = stage_release_artifact(manager, art1, man1, sig1, store)
    assert ok1 is True, m1
    ok_act1, ma1 = activate_staged_slot(manager, "slot-a")
    assert ok_act1 is True, ma1

    # Stage & activate v2
    ws2 = tmp_path / "ws2"
    ws2.mkdir()
    (ws2 / "main.py").write_text("print('v2')", encoding="utf-8")
    art2, man2, sig2 = _build_release(ws2, tmp_path / "dist2", "rel-2", "2.0.0", key_id, priv_bytes)
    ok2, m2 = stage_release_artifact(manager, art2, man2, sig2, store)
    assert ok2 is True, m2
    ok_act2, ma2 = activate_staged_slot(manager, "slot-b")
    assert ok_act2 is True, ma2

    # Revoke signing key in store
    store.revoke_key(key_id)

    # Rollback must be blocked
    ok_rb, msg_rb = rollback_to_previous(manager, store)
    assert ok_rb is False
    assert "revoked" in msg_rb.lower()
    assert manager.get_active_slot_id() == "slot-b"
