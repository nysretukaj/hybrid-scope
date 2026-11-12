"""Offline demo snapshot.

While online, export the real, AI-analysed live signals plus every cached LLM analysis to
seed/live_snapshot.json. With DEMO_OFFLINE=1 the API makes no network calls: it loads the
snapshot re-anchored to the current time (so it looks fresh), "Ingest live sources" replays it,
and Analyze Text answers from the cache.

Only short excerpts of third-party articles are kept (title, first ~280 characters, link).

CLI:  python -m app.snapshot        (exports from the current database)
"""
import hashlib
import json
import re
from datetime import timedelta
from pathlib import Path

from . import config, db
from .normalize import iso, parse_iso, utcnow

TEXT_LIMIT = 280
MAX_SIGNALS = 260
_INFO_CACHE: dict = {}


def cache_key(title: str, text: str) -> str:
    norm = re.sub(r"\s+", " ", f"{title or ''}|{text or ''}".strip().lower())
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:20]


def load_samples() -> list[dict]:
    try:
        return json.loads(config.SAMPLES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _excerpt(text: str) -> str:
    if len(text) <= TEXT_LIMIT:
        return text
    return text[:TEXT_LIMIT].rsplit(" ", 1)[0] + "…"


def precompute_samples() -> int:
    """Make sure every Analyze Text sample has a cached LLM answer (needs the LLM, online)."""
    from .analyzer import analyze  # local import: avoids a cycle at module load

    if not config.llm_enabled():
        return 0
    done = 0
    for s in load_samples():
        key = cache_key(s.get("title", ""), s["text"])
        if db.cache_get(key):
            continue
        result = analyze(s.get("title", ""), s["text"])
        if result["analyzer"].startswith("llm:"):
            db.cache_put(key, s.get("title", ""), s["text"], result, iso(utcnow()))
            done += 1
    return done


def export_snapshot(path: Path | None = None) -> dict:
    path = path or config.SNAPSHOT_PATH
    precompute_samples()
    now = utcnow()
    live = [s for s in db.fetch_signals(since_iso=iso(now - timedelta(hours=config.LOOKBACK_HOURS)))
            if not s["synthetic"]]
    relevant = [s for s in live if s["category"] != "other"]
    # keep some non-threat items so the Signal Stream still shows what the AI filters out
    noise = [s for s in live if s["category"] == "other"][: max(20, (MAX_SIGNALS - len(relevant)) // 3)]
    keep = sorted(relevant + noise, key=lambda s: s["timestamp"], reverse=True)[:MAX_SIGNALS]
    signals = [{**s, "text": _excerpt(s["text"])} for s in keep]
    cache = [{k: c[k] for k in ("key", "title", "text", "result")} for c in db.cache_all()]
    data = {"exported_at": iso(now), "signals": signals, "analyze_cache": cache}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    _INFO_CACHE.clear()
    return {
        "exported_at": data["exported_at"],
        "signals": len(signals),
        "threat_relevant": sum(1 for s in signals if s["category"] != "other"),
        "llm_analysed": sum(1 for s in signals if s["analyzer"].startswith("llm:")),
        "cached_analyses": len(cache),
        "path": str(path),
    }


def snapshot_info() -> dict | None:
    path = config.SNAPSHOT_PATH
    if not path.exists():
        return None
    mtime = path.stat().st_mtime
    if _INFO_CACHE.get("mtime") != mtime:
        data = json.loads(path.read_text(encoding="utf-8"))
        _INFO_CACHE.update(mtime=mtime, info={
            "exported_at": data.get("exported_at"),
            "signals": len(data.get("signals", [])),
            "llm_analysed": sum(1 for s in data.get("signals", []) if s.get("analyzer", "").startswith("llm:")),
            "cached_analyses": len(data.get("analyze_cache", [])),
        })
    return _INFO_CACHE["info"]


def load_snapshot(now=None) -> int:
    """Load the snapshot with timestamps shifted so its newest signal is ~10 minutes old."""
    path = config.SNAPSHOT_PATH
    if not path.exists():
        return 0
    now = now or utcnow()
    data = json.loads(path.read_text(encoding="utf-8"))
    signals = data.get("signals", [])
    for c in data.get("analyze_cache", []):
        db.cache_put(c["key"], c.get("title", ""), c["text"], c["result"], data.get("exported_at") or iso(now))
    if not signals:
        return 0
    newest = max(parse_iso(s["timestamp"]) for s in signals)
    shift = (now - timedelta(minutes=10)) - newest
    anchored = [{**s, "timestamp": iso(parse_iso(s["timestamp"]) + shift), "ingested_at": iso(now)} for s in signals]
    return db.upsert_signals(anchored)


if __name__ == "__main__":
    db.init_db()
    print(json.dumps(export_snapshot(), indent=1))
