"""SQLite persistence for normalized signals."""
import json
import sqlite3
from contextlib import contextmanager

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_reliability REAL NOT NULL,
    url TEXT,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    zone TEXT,
    country TEXT,
    lat REAL,
    lon REAL,
    entities TEXT NOT NULL,
    category TEXT NOT NULL,
    tags TEXT NOT NULL,
    severity REAL NOT NULL,
    confidence REAL NOT NULL,
    analyzer TEXT NOT NULL,
    rationale TEXT,
    synthetic INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(timestamp);
CREATE TABLE IF NOT EXISTS alert_feedback (
    alert_id TEXT PRIMARY KEY,
    verdict TEXT NOT NULL,          -- confirmed | false_positive
    note TEXT,
    sources TEXT NOT NULL,          -- JSON list of source names in the alert at review time
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    alert_id TEXT PRIMARY KEY,
    sent_at TEXT NOT NULL
);
"""

COLUMNS = [
    "id", "source_name", "source_type", "source_reliability", "url", "title", "text", "timestamp",
    "ingested_at", "zone", "country", "lat", "lon", "entities", "category", "tags", "severity",
    "confidence", "analyzer", "rationale", "synthetic",
]


@contextmanager
def get_conn():
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)


def _to_row(sig: dict) -> tuple:
    row = dict(sig)
    row["entities"] = json.dumps(sig.get("entities") or {}, ensure_ascii=False)
    row["tags"] = json.dumps(sig.get("tags") or [])
    row["synthetic"] = 1 if sig.get("synthetic") else 0
    return tuple(row.get(c) for c in COLUMNS)


def _from_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["entities"] = json.loads(d["entities"])
    d["tags"] = json.loads(d["tags"])
    d["synthetic"] = bool(d["synthetic"])
    return d


def insert_signals(signals: list[dict]) -> int:
    """Insert signals, skipping duplicates (same id). Returns number of new rows."""
    if not signals:
        return 0
    cols = ", ".join(COLUMNS)
    qs = ", ".join("?" for _ in COLUMNS)
    with get_conn() as conn:
        before = conn.total_changes
        conn.executemany(f"INSERT OR IGNORE INTO signals ({cols}) VALUES ({qs})", [_to_row(s) for s in signals])
        return conn.total_changes - before


def fetch_signals(since_iso: str | None = None, limit: int | None = None) -> list[dict]:
    query, params = "SELECT * FROM signals", []
    if since_iso:
        query += " WHERE timestamp >= ?"
        params.append(since_iso)
    query += " ORDER BY timestamp DESC"
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    with get_conn() as conn:
        return [_from_row(r) for r in conn.execute(query, params).fetchall()]


def count_signals() -> int:
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]


def delete_synthetic() -> int:
    with get_conn() as conn:
        return conn.execute("DELETE FROM signals WHERE synthetic = 1").rowcount


# --- Analyst feedback -------------------------------------------------------
def set_feedback(alert_id: str, verdict: str, note: str | None, sources: list[str], created_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO alert_feedback (alert_id, verdict, note, sources, created_at) VALUES (?, ?, ?, ?, ?)",
            (alert_id, verdict, note, json.dumps(sources), created_at),
        )


def delete_feedback(alert_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM alert_feedback WHERE alert_id = ?", (alert_id,))


def clear_feedback() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM alert_feedback")
        conn.execute("DELETE FROM notifications")


def get_feedback() -> dict[str, dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM alert_feedback").fetchall()
    return {r["alert_id"]: {**dict(r), "sources": json.loads(r["sources"])} for r in rows}


def source_feedback_stats() -> dict[str, dict]:
    stats: dict[str, dict] = {}
    for fb in get_feedback().values():
        key = "confirmed" if fb["verdict"] == "confirmed" else "rejected"
        for src in fb["sources"]:
            stats.setdefault(src, {"confirmed": 0, "rejected": 0})[key] += 1
    return stats


# --- Notifications ----------------------------------------------------------
def was_notified(alert_id: str) -> bool:
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM notifications WHERE alert_id = ?", (alert_id,)).fetchone() is not None


def mark_notified(alert_id: str, sent_at: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO notifications (alert_id, sent_at) VALUES (?, ?)", (alert_id, sent_at))
