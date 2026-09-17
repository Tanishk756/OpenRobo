"""Unit tests for offline durable telemetry spool."""

import tempfile
from pathlib import Path

from openrobo_agent.models import MessageEnvelope
from openrobo_agent.spool import OfflineTelemetrySpool


def test_spool_enqueue_peek_and_acknowledge():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_spool.db"
        spool = OfflineTelemetrySpool(db_path, max_events=100)

        msg1 = MessageEnvelope(device_id="dev-1", message_type="HEARTBEAT", payload={"val": 1})
        msg2 = MessageEnvelope(device_id="dev-1", message_type="HEARTBEAT", payload={"val": 2})

        assert spool.enqueue(msg1) is True
        assert spool.enqueue(msg2) is True
        assert spool.count() == 2

        peeked = spool.peek(limit=10)
        assert len(peeked) == 2
        assert peeked[0].message_id == msg1.message_id
        assert peeked[1].message_id == msg2.message_id

        # Acknowledge first
        acked = spool.acknowledge([msg1.message_id])
        assert acked == 1
        assert spool.count() == 1

        remaining = spool.peek()
        assert len(remaining) == 1
        assert remaining[0].message_id == msg2.message_id


def test_spool_fifo_max_events_bounding():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_spool_bounded.db"
        spool = OfflineTelemetrySpool(db_path, max_events=5)

        for i in range(10):
            msg = MessageEnvelope(device_id="dev-1", message_type="TEST", payload={"idx": i})
            spool.enqueue(msg)

        assert spool.count() == 5
        peeked = spool.peek(limit=10)
        # Should contain indices 5, 6, 7, 8, 9
        indices = [p.payload["idx"] for p in peeked]
        assert indices == [5, 6, 7, 8, 9]
