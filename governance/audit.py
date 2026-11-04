"""Append-only, hash-chained SQLite audit store."""
import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

GENESIS = "0" * 64

class AuditStore:
    def __init__(self, db_path: str = "governance_audit.db"):
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True) if Path(self.db_path).parent != Path(".") else None
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    run_id TEXT,
                    event_type TEXT NOT NULL,
                    actor_id TEXT,
                    payload TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_run ON audit_events(run_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_events(event_type)")

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=15, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _canonical(value: Any) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

    def append(self, event_type: str, payload: dict[str, Any], actor_id: str | None = None,
               run_id: str | None = None) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            last = conn.execute("SELECT event_hash FROM audit_events ORDER BY event_id DESC LIMIT 1").fetchone()
            previous_hash = last["event_hash"] if last else GENESIS
            timestamp = datetime.now(timezone.utc).isoformat()
            body = {
                "timestamp": timestamp, "run_id": run_id, "event_type": event_type,
                "actor_id": actor_id, "payload": payload, "previous_hash": previous_hash
            }
            event_hash = hashlib.sha256(self._canonical(body).encode("utf-8")).hexdigest()
            cur = conn.execute(
                """INSERT INTO audit_events
                (timestamp,run_id,event_type,actor_id,payload,previous_hash,event_hash)
                VALUES (?,?,?,?,?,?,?)""",
                (timestamp, run_id, event_type, actor_id, self._canonical(payload), previous_hash, event_hash)
            )
            event_id = cur.lastrowid
            return {"event_id": event_id, **body, "event_hash": event_hash}

    def list_events(self, limit: int = 100, run_id: str | None = None,
                    event_type: str | None = None) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 1000))
        query, params = "SELECT * FROM audit_events WHERE 1=1", []
        if run_id:
            query += " AND run_id=?"; params.append(run_id)
        if event_type:
            query += " AND event_type=?"; params.append(event_type)
        query += " ORDER BY event_id DESC LIMIT ?"; params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [self._row(row) for row in reversed(rows)]

    @staticmethod
    def _row(row):
        return {
            "event_id": row["event_id"], "timestamp": row["timestamp"], "run_id": row["run_id"],
            "event_type": row["event_type"], "actor_id": row["actor_id"],
            "payload": json.loads(row["payload"]), "previous_hash": row["previous_hash"],
            "event_hash": row["event_hash"]
        }

    def verify(self) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM audit_events ORDER BY event_id ASC").fetchall()
        expected_prev = GENESIS
        for row in rows:
            body = {
                "timestamp": row["timestamp"], "run_id": row["run_id"],
                "event_type": row["event_type"], "actor_id": row["actor_id"],
                "payload": json.loads(row["payload"]), "previous_hash": row["previous_hash"]
            }
            calculated = hashlib.sha256(self._canonical(body).encode("utf-8")).hexdigest()
            if row["previous_hash"] != expected_prev or row["event_hash"] != calculated:
                return {"valid": False, "checked": row["event_id"], "broken_event_id": row["event_id"]}
            expected_prev = row["event_hash"]
        return {"valid": True, "checked": len(rows), "head_hash": expected_prev}
