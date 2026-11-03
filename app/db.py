import sqlite3
from pathlib import Path
from contextlib import contextmanager
from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS employees (
 id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, role TEXT NOT NULL,
 manager_id TEXT, cost_center TEXT NOT NULL, monthly_limit REAL NOT NULL, preferences TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS receipts (
 id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, filename TEXT NOT NULL, vendor TEXT,
 expense_date TEXT, amount REAL, category TEXT, extracted_text TEXT, confidence REAL DEFAULT 0,
 created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS claims (
 id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, manager_id TEXT, title TEXT NOT NULL,
 purpose TEXT, cost_center TEXT NOT NULL, status TEXT NOT NULL, total REAL NOT NULL DEFAULT 0,
 currency TEXT NOT NULL DEFAULT 'INR', items_json TEXT NOT NULL, policy_json TEXT NOT NULL DEFAULT '[]',
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, submitted_at TEXT, decision_reason TEXT
);
CREATE TABLE IF NOT EXISTS approvals (
 id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, manager_id TEXT NOT NULL, status TEXT NOT NULL,
 reason TEXT, created_at TEXT NOT NULL, decided_at TEXT
);
CREATE TABLE IF NOT EXISTS audit_events (
 id TEXT PRIMARY KEY, run_id TEXT, claim_id TEXT, actor_id TEXT, event_type TEXT NOT NULL,
 message TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS agent_runs (
 id TEXT PRIMARY KEY, employee_id TEXT NOT NULL, claim_id TEXT, status TEXT NOT NULL,
 trace_json TEXT NOT NULL, created_at TEXT NOT NULL
);
"""

def connect():
    Path(settings.database_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.executescript(SCHEMA)
