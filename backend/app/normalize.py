"""Normalization of heterogeneous source items into the unified signal schema."""
import hashlib
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def make_id(url: str | None, source_name: str, title: str) -> str:
    key = url or f"{source_name}|{title}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def build_signal(
    *,
    source_name: str,
    source_type: str,
    reliability: float,
    title: str,
    text: str,
    url: str | None,
    timestamp: datetime,
    analysis: dict,
    synthetic: bool = False,
    signal_id: str | None = None,
) -> dict:
    """Unified schema: source, timestamp, text, entities, geolocation + AI analysis."""
    loc = analysis.get("location") or {}
    now = utcnow()
    return {
        "id": signal_id or make_id(url, source_name, title),
        "source_name": source_name,
        "source_type": source_type,
        "source_reliability": round(float(reliability), 2),
        "url": url,
        "title": (title or "").strip()[:300],
        "text": (text or title or "").strip()[:2000],
        "timestamp": iso(min(timestamp, now)),
        "ingested_at": iso(now),
        "zone": loc.get("zone"),
        "country": loc.get("country"),
        "lat": loc.get("lat"),
        "lon": loc.get("lon"),
        "entities": analysis.get("entities") or {},
        "category": analysis.get("category", "other"),
        "tags": analysis.get("tags") or [],
        "severity": round(float(analysis.get("severity", 0.1)), 2),
        "confidence": round(float(analysis.get("confidence", 0.3)), 2),
        "analyzer": analysis.get("analyzer", "local-nlp"),
        "rationale": analysis.get("rationale"),
        "synthetic": synthetic,
    }
