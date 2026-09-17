"""Offline Durable Telemetry Spool (SQLite FIFO Queue)."""

import contextlib
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterator, List, Tuple

from openrobo_agent.models import MessageEnvelope
from openrobo_agent.security import set_secure_file_permissions


class OfflineTelemetrySpool:
    """Bounded, thread-safe, SQLite-backed FIFO telemetry spool."""

    def __init__(
        self,
        db_path: Path,
        max_events: int = 5000,
        max_bytes: int = 50 * 1024 * 1024,
        max_age_days: int = 7,
    ):
        self.db_path = Path(db_path)
        self.max_events = max_events
        self.max_bytes = max_bytes
        self.max_age_seconds = max_age_days * 86400
        self._lock = threading.Lock()
        self._init_db()

    @contextlib.contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_spool (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT UNIQUE NOT NULL,
                    device_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    envelope_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    size_bytes INTEGER NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_spool_created ON telemetry_spool(created_at)")
            conn.commit()
        set_secure_file_permissions(self.db_path, 0o600)

    def enqueue(self, envelope: MessageEnvelope) -> bool:
        """Enqueue a message envelope into the local spool, applying bounds and FIFO eviction."""
        raw_json = envelope.model_dump_json()
        size_bytes = len(raw_json.encode("utf-8"))
        now = time.time()

        with self._lock, self._connection() as conn:
            try:
                conn.execute(
                    """
                    INSERT INTO telemetry_spool
                    (message_id, device_id, timestamp, message_type, envelope_json, created_at, size_bytes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        envelope.message_id,
                        envelope.device_id,
                        envelope.timestamp,
                        envelope.message_type,
                        raw_json,
                        now,
                        size_bytes,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return False

            self._prune_locked(conn)
            return True

    def peek(self, limit: int = 50) -> List[MessageEnvelope]:
        """Fetch the oldest unacknowledged message envelopes without removing them."""
        with self._lock, self._connection() as conn:
            rows = conn.execute(
                "SELECT envelope_json FROM telemetry_spool ORDER BY id ASC LIMIT ?",
                (limit,),
            ).fetchall()

            messages = []
            for r in rows:
                try:
                    msg = MessageEnvelope.model_validate_json(r["envelope_json"])
                    messages.append(msg)
                except Exception:
                    pass
            return messages

    def acknowledge(self, message_ids: Any) -> int:
        """Remove acknowledged messages from the spool."""
        if isinstance(message_ids, str):
            message_ids = [message_ids]
        if not message_ids:
            return 0
        with self._lock, self._connection() as conn:
            placeholders = ",".join("?" for _ in message_ids)
            cursor = conn.execute(
                f"DELETE FROM telemetry_spool WHERE message_id IN ({placeholders})",
                message_ids,
            )
            conn.commit()
            return cursor.rowcount

    def prune(self) -> Tuple[int, int]:
        """Prune expired and overflow messages."""
        with self._lock, self._connection() as conn:
            return self._prune_locked(conn)

    def _prune_locked(self, conn: sqlite3.Connection) -> Tuple[int, int]:
        now = time.time()
        expiry_cutoff = now - self.max_age_seconds

        cursor_exp = conn.execute("DELETE FROM telemetry_spool WHERE created_at < ?", (expiry_cutoff,))
        expired_count = cursor_exp.rowcount

        total_count = conn.execute("SELECT COUNT(*) FROM telemetry_spool").fetchone()[0]
        evicted_count = 0
        if total_count > self.max_events:
            excess = total_count - self.max_events
            conn.execute(
                """
                DELETE FROM telemetry_spool WHERE id IN (
                    SELECT id FROM telemetry_spool ORDER BY id ASC LIMIT ?
                )
                """,
                (excess,),
            )
            evicted_count += excess

        total_bytes = conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM telemetry_spool").fetchone()[0]
        if total_bytes > self.max_bytes:
            while total_bytes > self.max_bytes:
                chunk = conn.execute("SELECT id, size_bytes FROM telemetry_spool ORDER BY id ASC LIMIT 50").fetchall()
                if not chunk:
                    break
                ids_to_del = [r["id"] for r in chunk]
                placeholders = ",".join("?" for _ in ids_to_del)
                conn.execute(f"DELETE FROM telemetry_spool WHERE id IN ({placeholders})", ids_to_del)
                total_bytes = conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM telemetry_spool").fetchone()[0]
                evicted_count += len(ids_to_del)

        conn.commit()
        return expired_count, evicted_count

    def count(self) -> int:
        """Return total queued messages."""
        with self._lock, self._connection() as conn:
            return conn.execute("SELECT COUNT(*) FROM telemetry_spool").fetchone()[0]

    def size_bytes(self) -> int:
        """Return total disk size consumed by queued messages."""
        with self._lock, self._connection() as conn:
            return conn.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM telemetry_spool").fetchone()[0]
