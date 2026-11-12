"""Live ingestion from open sources: RSS feeds + GDELT DOC 2.0 API.

Failures of individual sources are reported, never fatal - the demo keeps working offline.
"""
import asyncio
import html
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import feedparser
import httpx

from .. import config, db
from ..analyzer import analyze
from ..normalize import build_signal, iso, make_id, utcnow

_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _clean(value: str) -> str:
    return _WS.sub(" ", html.unescape(_TAGS.sub(" ", value or ""))).strip()


def _struct_to_dt(t) -> datetime | None:
    return datetime(*t[:6], tzinfo=timezone.utc) if t else None


async def fetch_rss(client: httpx.AsyncClient, feed: dict) -> list[dict]:
    resp = await client.get(feed["url"], follow_redirects=True)
    resp.raise_for_status()
    parsed = feedparser.parse(resp.content)
    items = []
    for e in parsed.entries[:40]:
        title = _clean(e.get("title", ""))
        if not title:
            continue
        ts = _struct_to_dt(e.get("published_parsed") or e.get("updated_parsed")) or utcnow()
        items.append({
            "source_name": feed["name"], "source_type": feed["type"], "reliability": feed["reliability"],
            "title": title, "text": _clean(e.get("summary") or e.get("description") or "")[:1500] or title,
            "url": e.get("link"), "timestamp": ts,
        })
    return items


async def fetch_gdelt(client: httpx.AsyncClient) -> list[dict]:
    params = {"query": config.GDELT_QUERY, "mode": "artlist", "format": "json",
              "maxrecords": config.GDELT_MAX_RECORDS, "timespan": "24h", "sort": "datedesc"}
    resp = await client.get(config.GDELT_URL, params=params)
    if resp.status_code == 429:  # GDELT allows ~1 request / 5 s per IP; retry once
        await asyncio.sleep(6)
        resp = await client.get(config.GDELT_URL, params=params)
    resp.raise_for_status()
    try:
        data = resp.json()
    except ValueError as exc:  # GDELT returns plain text when rate limited
        raise RuntimeError(resp.text[:120]) from exc
    items = []
    for a in data.get("articles", []):
        domain = (a.get("domain") or urlparse(a.get("url", "")).netloc).removeprefix("www.")
        try:
            ts = datetime.strptime(a["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            ts = utcnow()
        items.append({
            "source_name": domain or "GDELT", "source_type": "news (GDELT)",
            "reliability": config.DOMAIN_RELIABILITY.get(domain, config.DEFAULT_RELIABILITY),
            "title": _clean(a.get("title", "")), "text": _clean(a.get("title", "")),
            "url": a.get("url"), "timestamp": ts,
        })
    return items


def _analyze_all(raw: list[dict]) -> list[dict]:
    """Fast local analysis only; the LLM upgrades new signals afterwards in the background (enrich.py)."""
    out = []
    for r in raw:
        analysis = analyze(r["title"], r["text"], use_llm=False)
        out.append(build_signal(
            source_name=r["source_name"], source_type=r["source_type"], reliability=r["reliability"],
            title=r["title"], text=r["text"], url=r["url"], timestamp=r["timestamp"], analysis=analysis,
        ))
    return out


async def run_live_ingest() -> dict:
    started = utcnow()
    names = [f["name"] for f in config.RSS_FEEDS] + ["GDELT"]
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT, headers={"User-Agent": config.USER_AGENT}) as client:
        tasks = [fetch_rss(client, f) for f in config.RSS_FEEDS] + [fetch_gdelt(client)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    raw, report = [], []
    for name, res in zip(names, results):
        if isinstance(res, Exception):
            report.append({"source": name, "ok": False, "items": 0, "error": f"{type(res).__name__}: {res}"[:200]})
        else:
            raw.extend(res)
            report.append({"source": name, "ok": True, "items": len(res)})

    raw = [r for r in raw if r["title"]]
    known = await asyncio.to_thread(db.existing_ids, [make_id(r["url"], r["source_name"], r["title"]) for r in raw])
    fresh = [r for r in raw if make_id(r["url"], r["source_name"], r["title"]) not in known]
    signals = await asyncio.to_thread(_analyze_all, fresh)
    inserted = await asyncio.to_thread(db.insert_signals, signals)
    relevant = sum(1 for s in signals if s["category"] != "other")
    return {
        "started_at": iso(started), "finished_at": iso(utcnow()),
        "fetched": len(raw), "inserted": inserted, "threat_relevant": relevant, "sources": report,
        "new_ids": [s["id"] for s in signals],
    }
