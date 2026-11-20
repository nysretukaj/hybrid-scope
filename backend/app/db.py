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
    synthetic INTEGER NOT NULL DEFAULT 0,
    i18n TEXT NOT NULL DEFAULT '{}',    -- {"sq": {"title", "text", "rationale"}, "de": {...}}
    subcategory TEXT,
    cause TEXT,                         -- deliberate | accidental | natural | unknown
    claim TEXT,                         -- confirmed | alleged | opinion | reported
    target TEXT,
    content_hash TEXT,                  -- sha256 of title + text as collected
    original_category TEXT              -- set when an analyst corrects the category
);
CREATE INDEX IF NOT EXISTS idx_signals_ts ON signals(timestamp);
CREATE TABLE IF NOT EXISTS alert_feedback (
    alert_id TEXT PRIMARY KEY,
    verdict TEXT NOT NULL,          -- verification status: unverified | investigating | partial | confirmed | disproved
    note TEXT,
    sources TEXT NOT NULL,          -- JSON list of source names in the alert at review time
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    alert_id TEXT PRIMARY KEY,
    sent_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analyze_cache (
    key TEXT PRIMARY KEY,           -- hash of the normalized title + text
    title TEXT,
    text TEXT NOT NULL,
    result TEXT NOT NULL,           -- JSON of the LLM-backed analysis
    created_at TEXT NOT NULL
);
"""

COLUMNS = [
    "id", "source_name", "source_type", "source_reliability", "url", "title", "text", "timestamp",
    "ingested_at", "zone", "country", "lat", "lon", "entities", "category", "tags", "severity",
    "confidence", "analyzer", "rationale", "synthetic", "i18n",
    "subcategory", "cause", "claim", "target", "content_hash", "original_category",
]
# columns added after the first release, created on start for older databases
ADDED_COLUMNS = {"i18n": "TEXT NOT NULL DEFAULT '{}'", "subcategory": "TEXT", "cause": "TEXT", "claim": "TEXT",
                 "target": "TEXT", "content_hash": "TEXT", "original_category": "TEXT"}

VERIFICATION = ("unverified", "investigating", "partial", "confirmed", "disproved")
_LEGACY_VERDICT = {"false_positive": "disproved"}


def norm_verdict(v: str | None) -> str:
    v = _LEGACY_VERDICT.get(v or "", v or "")
    return v if v in VERIFICATION else "unverified"


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
        # migrate databases created by earlier versions
        cols = {r[1] for r in conn.execute("PRAGMA table_info(signals)")}
        for name, decl in ADDED_COLUMNS.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE signals ADD COLUMN {name} {decl}")


def _to_row(sig: dict) -> tuple:
    row = dict(sig)
    row["entities"] = json.dumps(sig.get("entities") or {}, ensure_ascii=False)
    row["tags"] = json.dumps(sig.get("tags") or [])
    row["synthetic"] = 1 if sig.get("synthetic") else 0
    row["i18n"] = json.dumps(sig.get("i18n") or {}, ensure_ascii=False)
    return tuple(row.get(c) for c in COLUMNS)


def _from_row(row: sqlite3.Row) -> dict:
    d = dict(row)
    d["entities"] = json.loads(d["entities"])
    d["tags"] = json.loads(d["tags"])
    d["synthetic"] = bool(d["synthetic"])
    d["i18n"] = json.loads(d.get("i18n") or "{}")
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


def existing_ids(ids: list[str]) -> set[str]:
    if not ids:
        return set()
    found: set[str] = set()
    with get_conn() as conn:
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            qs = ",".join("?" for _ in chunk)
            found |= {r[0] for r in conn.execute(f"SELECT id FROM signals WHERE id IN ({qs})", chunk)}
    return found


def fetch_by_ids(ids: list[str]) -> list[dict]:
    if not ids:
        return []
    out: list[dict] = []
    with get_conn() as conn:
        for i in range(0, len(ids), 500):
            chunk = ids[i:i + 500]
            qs = ",".join("?" for _ in chunk)
            out += [_from_row(r) for r in conn.execute(f"SELECT * FROM signals WHERE id IN ({qs})", chunk)]
    return out


def fetch_unenriched_live(limit: int) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id FROM signals WHERE synthetic = 0 AND analyzer = 'local-nlp' ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [r[0] for r in rows]


def update_analysis(signal_id: str, analysis: dict) -> None:
    """Store an LLM re-analysis. Signals an analyst has corrected by hand are never overwritten."""
    with get_conn() as conn:
        row = conn.execute("SELECT i18n, analyzer FROM signals WHERE id = ?", (signal_id,)).fetchone()
        if row and row[1] == "analyst":
            return
        i18n = json.loads(row[0]) if row and row[0] else {}
        # the new rationale replaces the old one in every language; other translated fields are kept
        for lang in ("sq", "de"):
            i18n.setdefault(lang, {}).pop("rationale", None)
        for lang, fields in (analysis.get("i18n") or {}).items():
            i18n.setdefault(lang, {}).update(fields)
        conn.execute(
            "UPDATE signals SET category = ?, tags = ?, severity = ?, confidence = ?, analyzer = ?, rationale = ?, "
            "entities = ?, i18n = ? WHERE id = ?",
            (analysis["category"], json.dumps(analysis.get("tags") or []), round(float(analysis["severity"]), 2),
             round(float(analysis["confidence"]), 2), analysis["analyzer"], analysis.get("rationale"),
             json.dumps(analysis.get("entities") or {}, ensure_ascii=False),
             json.dumps({k: v for k, v in i18n.items() if v}, ensure_ascii=False), signal_id),
        )
        conn.execute(
            "UPDATE signals SET subcategory = ?, cause = ?, claim = ?, target = ? WHERE id = ?",
            (analysis.get("subcategory"), analysis.get("cause"), analysis.get("claim"), analysis.get("target"), signal_id),
        )
        loc = analysis.get("location")
        if loc:  # the LLM named a country the text-based gazetteer had missed
            conn.execute(
                "UPDATE signals SET zone = ?, country = ?, lat = ?, lon = ? WHERE id = ? AND zone IS NULL",
                (loc.get("zone"), loc.get("country"), loc.get("lat"), loc.get("lon"), signal_id),
            )


def set_classification(signal_id: str, category: str, subcategory: str | None) -> dict | None:
    """Analyst correction of a signal's category. The first automatic category is kept for audit."""
    with get_conn() as conn:
        row = conn.execute("SELECT category, original_category, tags FROM signals WHERE id = ?", (signal_id,)).fetchone()
        if not row:
            return None
        original = row["original_category"] or row["category"]
        tags = [t for t in json.loads(row["tags"] or "[]") if t != category]
        conn.execute(
            "UPDATE signals SET category = ?, subcategory = ?, tags = ?, analyzer = 'analyst', original_category = ? WHERE id = ?",
            (category, subcategory, json.dumps(tags), original, signal_id),
        )
    return {"id": signal_id, "category": category, "subcategory": subcategory, "original_category": original}


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
    return {r["alert_id"]: {**dict(r), "verdict": norm_verdict(r["verdict"]), "sources": json.loads(r["sources"])}
            for r in rows}


def source_feedback_stats() -> dict[str, dict]:
    """Confirmed alerts count for their sources, disproved ones against; the states in between are neutral."""
    stats: dict[str, dict] = {}
    for fb in get_feedback().values():
        key = {"confirmed": "confirmed", "disproved": "rejected"}.get(fb["verdict"])
        if not key:
            continue
        for src in fb["sources"]:
            stats.setdefault(src, {"confirmed": 0, "rejected": 0})[key] += 1
    return stats


# --- Analyze cache (offline demo) -------------------------------------------
def cache_put(key: str, title: str, text: str, result: dict, created_at: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO analyze_cache (key, title, text, result, created_at) VALUES (?, ?, ?, ?, ?)",
            (key, title, text, json.dumps(result, ensure_ascii=False), created_at),
        )


def cache_get(key: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT result FROM analyze_cache WHERE key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def cache_all() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, title, text, result, created_at FROM analyze_cache").fetchall()
    return [{**dict(r), "result": json.loads(r["result"])} for r in rows]


def upsert_signals(signals: list[dict]) -> int:
    """Insert or replace (used to re-anchor snapshot signals to the current time)."""
    if not signals:
        return 0
    cols = ", ".join(COLUMNS)
    qs = ", ".join("?" for _ in COLUMNS)
    with get_conn() as conn:
        conn.executemany(f"INSERT OR REPLACE INTO signals ({cols}) VALUES ({qs})", [_to_row(s) for s in signals])
    return len(signals)


# --- Notifications ----------------------------------------------------------
def was_notified(alert_id: str) -> bool:
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM notifications WHERE alert_id = ?", (alert_id,)).fetchone() is not None


def mark_notified(alert_id: str, sent_at: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO notifications (alert_id, sent_at) VALUES (?, ?)", (alert_id, sent_at))
