"""Live ingestion from open sources: RSS feeds + GDELT DOC 2.0 API.

Failures of individual sources are reported, never fatal - the demo keeps working offline.
"""
import asyncio
import html
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import feedparser
import httpx

from .. import config, db
from ..analyzer import analyze
from ..ml.images import clean_url, image_from_entry
from ..normalize import build_signal, iso, make_id, utcnow
from .scrape import fetch_scraped

log = logging.getLogger(__name__)
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
        summary = _clean(e.get("summary") or e.get("description") or "")
        # social posts (e.g. Mastodon) have no title: use the start of the post
        title = _clean(e.get("title", "")) or (summary[:140].rsplit(" ", 1)[0] + "…" if len(summary) > 140 else summary)
        if not title:
            continue
        ts = _struct_to_dt(e.get("published_parsed") or e.get("updated_parsed")) or utcnow()
        image = image_from_entry(e)  # relative image paths are resolved against the article link
        items.append({
            "source_name": feed["name"], "source_type": feed["type"], "reliability": feed["reliability"],
            "title": title, "text": summary[:1500] or title,
            "url": e.get("link"), "timestamp": ts,
            "image_url": clean_url(urljoin(e.get("link") or feed["url"], image)) if image else None,
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
            "url": a.get("url"), "timestamp": ts, "image_url": clean_url(a.get("socialimage")),
        })
    return items


async def fetch_cisa_kev(client: httpx.AsyncClient) -> list[dict]:
    """CISA Known Exploited Vulnerabilities: confirmed exploitation in the wild (an incident database)."""
    resp = await client.get(config.CISA_KEV_URL)
    resp.raise_for_status()
    cutoff = utcnow().date().toordinal() - config.CISA_KEV_DAYS
    items = []
    for v in resp.json().get("vulnerabilities", []):
        try:
            added = datetime.strptime(v["dateAdded"], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        if added.date().toordinal() < cutoff:
            continue
        cve = v.get("cveID", "")
        ransomware = str(v.get("knownRansomwareCampaignUse", "")).lower() == "known"
        title = f"{cve} in {v.get('vendorProject', '')} {v.get('product', '')} is being actively exploited".strip()
        text = (f"CISA confirmed active exploitation of {cve} ({v.get('vulnerabilityName', '')}). "
                f"{v.get('shortDescription', '')} Required action: {v.get('requiredAction', '')}"
                + (" The vulnerability is known to be used in ransomware campaigns." if ransomware else ""))
        items.append({
            "source_name": "CISA KEV", "source_type": "advisory", "reliability": 0.95,
            "title": title, "text": _clean(text),
            "url": f"https://nvd.nist.gov/vuln/detail/{cve}" if cve else None, "timestamp": added,
        })
    return items


# ISO country codes used by ransomware.live -> country names the gazetteer knows
ISO_COUNTRY = {
    "XK": "Kosovo", "RS": "Serbia", "MK": "North Macedonia", "AL": "Albania", "BA": "Bosnia", "ME": "Montenegro",
    "HR": "Croatia", "EE": "Estonia", "FI": "Finland", "LV": "Latvia", "LT": "Lithuania", "MD": "Moldova",
    "UA": "Ukraine", "RU": "Russia", "PL": "Poland", "RO": "Romania", "BG": "Bulgaria", "DE": "Germany",
    "FR": "France", "GB": "United Kingdom", "UK": "United Kingdom", "NL": "Netherlands", "BE": "Belgium",
    "IT": "Italy", "ES": "Spain", "GR": "Greece", "TR": "Turkey", "AT": "Austria", "CH": "Switzerland",
    "IL": "Israel", "IR": "Iran", "CN": "China", "TW": "Taiwan", "JP": "Japan", "KR": "South Korea",
    "KP": "North Korea", "IN": "India", "BR": "Brazil", "US": "United States", "CA": "Canada", "AU": "Australia",
}


def ransomware_items(victims: list[dict], now: datetime, days: int) -> list[dict]:
    """Leak-site claims as reports. The victim name stays as ransomware.live shows it (partly masked)."""
    items = []
    for v in victims:
        try:
            ts = datetime.fromisoformat(str(v.get("discovered") or v.get("attackdate")).replace("Z", "+00:00"))
        except ValueError:
            continue
        ts = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
        if (now - ts).days >= days:
            continue
        group = _clean(str(v.get("group") or "")) or "unknown"
        victim = _clean(str(v.get("victim") or "")) or "an organisation"
        country = ISO_COUNTRY.get(str(v.get("country") or "").upper())
        sector = _clean(str(v.get("activity") or ""))
        sector = "" if sector.lower() in ("", "not found", "unknown") else sector
        where = f" in {country}" if country else ""
        title = f"{group} ransomware group claims attack on {victim}{where}"
        text = (f"The {group} ransomware gang claims on its leak site to have attacked {victim}"
                + (f", a {sector} organisation" if sector else "") + f"{where}. "
                + _clean(str(v.get("description") or ""))[:400]
                + " This is the criminals' own claim and has not been confirmed by the victim.")
        url = v.get("url") if str(v.get("url") or "").startswith("https://www.ransomware.live/") else None
        items.append({"source_name": "ransomware.live", "source_type": "leak", "reliability": 0.6,
                      "title": title, "text": text.strip(), "url": url, "timestamp": ts, "image_url": None})
    return items


async def fetch_ransomware(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(config.RANSOMWARE_URL)
    resp.raise_for_status()
    data = resp.json()
    return ransomware_items(data if isinstance(data, list) else [], utcnow(), config.RANSOMWARE_DAYS)


def apply_fact_check_hint(item: dict, a: dict) -> bool:
    """A fact-checker's article with at least a weak disinformation indicator is about a false claim:
    classify it as (low-severity) disinformation. Explainers without any indicator stay as they are."""
    from ..assess import classify_extra
    from ..i18n import tr

    if not str(item.get("source_type", "")).startswith("fact-check") or a["category"] != "other":
        return False
    if (a.get("keyword_scores") or {}).get("disinformation", 0) < 1:
        return False
    a.update(classify_extra("disinformation", item["title"], item["text"]))
    a.update(category="disinformation", severity=max(a["severity"], 0.3), confidence=max(a["confidence"], 0.5))
    a["rationale"] = tr("nlp.factcheck", "en")
    for lang in ("sq", "de"):
        a.setdefault("i18n", {}).setdefault(lang, {})["rationale"] = tr("nlp.factcheck", lang)
    return True


def reanalyze_rule_only() -> int:
    """Run improved keyword rules again over stored reports that only the rules have seen.
    LLM and analyst labels are never touched. Returns how many reports changed category."""
    changed = 0
    for s in db.fetch_signals():
        if s["analyzer"] != "local-nlp":
            continue
        a = analyze(s["title"], s["text"], use_llm=False)
        apply_fact_check_hint(s, a)
        if a["category"] != s["category"] and db.update_analysis(s["id"], a, only_if_analyzer="local-nlp"):
            changed += 1
    return changed


def _analyze_all(raw: list[dict]) -> list[dict]:
    """Fast local analysis only: keyword rules, corrected in one batch by the model trained on our data
    when that model is fast (word features). A model on embeddings runs after storing, in the background
    (main.ingest_once), and LLMs upgrade new signals afterwards (enrich.py, ml/jobs.py)."""
    from ..ml import classifier

    analyses = [analyze(r["title"], r["text"], use_llm=False) for r in raw]
    for r, a in zip(raw, analyses):
        apply_fact_check_hint(r, a)
    try:
        classifier.refine([(r["title"], r["text"]) for r in raw], analyses, allow_embeddings=False)
    except Exception:  # noqa: BLE001 - the rules' result is always kept if the model fails
        log.exception("trained model could not check the new reports")
    return [build_signal(
        source_name=r["source_name"], source_type=r["source_type"], reliability=r["reliability"],
        title=r["title"], text=r["text"], url=r["url"], timestamp=r["timestamp"], analysis=a,
        image_url=r.get("image_url"),
    ) for r, a in zip(raw, analyses)]


async def run_live_ingest() -> dict:
    started = utcnow()
    names = ([f["name"] for f in config.RSS_FEEDS] + ["GDELT", "CISA KEV", "ransomware.live"]
             + [s["name"] for s in config.SCRAPE_SOURCES])
    async with httpx.AsyncClient(timeout=config.HTTP_TIMEOUT, headers={"User-Agent": config.USER_AGENT}) as client:
        tasks = ([fetch_rss(client, f) for f in config.RSS_FEEDS]
                 + [fetch_gdelt(client), fetch_cisa_kev(client), fetch_ransomware(client)]
                 + [fetch_scraped(client, s) for s in config.SCRAPE_SOURCES])
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
