"""HybridScope API."""
import asyncio
import logging
import re
import secrets
import time
from collections import Counter, defaultdict, deque
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, db, enrich, notify
from .analyzer import LLM_STATUS, active_analyzer, analyze
from .analyzer.llm import known_model, resolve_model, summarize_alert
from .assess import SUBCATEGORIES, mark_duplicates, signal_view
from .brief import build_brief
from .correlation import build_alerts, replay
from .feedback import apply_feedback
from .graph import build_graph
from .ingest.live import run_live_ingest
from .ingest.seed import reset_seed
from .normalize import iso, parse_iso, utcnow
from .i18n import norm_lang, source_label, zone_name
from .localize import localize_alert, localize_signal
from .ml import classifier, dataset, image_embeddings, jobs, local_llm, ollama
from .ml.images import ImageError, decode_upload, fetch as fetch_image, prepare as prepare_image
from .snapshot import cache_key, export_snapshot, load_samples, load_snapshot, snapshot_info

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("hybridscope")

STATE: dict = {"last_ingest": None, "ingest_running": False, "tasks": set()}
_ANALYZE_HITS: dict[str, deque] = defaultdict(deque)


# --- Public-mode guards ------------------------------------------------------------
def is_admin(request: Request) -> bool:
    token = request.headers.get("x-admin-token", "")
    return bool(config.ADMIN_TOKEN) and secrets.compare_digest(token, config.ADMIN_TOKEN)


def require_admin(request: Request) -> None:
    """In the public deployment, only the presenter (X-Admin-Token) may change the demo's state."""
    if config.PUBLIC_MODE and not is_admin(request):
        raise HTTPException(403, "Disabled in the public demo")


def limit_analyze(request: Request) -> None:
    """Per-client limit on Analyze Text in the public deployment, to protect the LLM quota."""
    if not config.PUBLIC_MODE or is_admin(request):
        return
    if len(_ANALYZE_HITS) > 5000:
        _ANALYZE_HITS.clear()
    hits = _ANALYZE_HITS[request.client.host if request.client else "?"]
    now = time.monotonic()
    while hits and now - hits[0] > 60:
        hits.popleft()
    if len(hits) >= config.ANALYZE_PER_MINUTE:
        raise HTTPException(429, f"Public demo limit: {config.ANALYZE_PER_MINUTE} analyses per minute, please wait a moment")
    hits.append(now)


def start_enrichment(ids: list[str]) -> bool:
    """Upgrade signals with an LLM in the background: the cloud LLM when configured, otherwise the
    local one when LOCAL_LLM_FOR_LIVE=1 (keeps a reference so the task is not GC'd)."""
    if not ids:
        return False
    if not (config.llm_enabled() and config.LLM_FOR_LIVE):
        if config.LOCAL_LLM_FOR_LIVE and ollama.chat_model():
            return jobs.start_label(ids[: config.LLM_MAX_PER_INGEST])
        return False
    task = asyncio.create_task(enrich.enrich_signals(ids))
    STATE["tasks"].add(task)
    task.add_done_callback(STATE["tasks"].discard)
    return True


SERBIAN_SOURCES = {s["name"] for s in [*config.RSS_FEEDS, *config.TELEGRAM_CHANNELS] if s.get("lang") == "sr"}


# Only used to ORDER the local-AI queue (the local AI does the reading): place names in Latin and Cyrillic.
_KOSOVO_MENTION = re.compile(r"kosov|косов|prišt|pristin|приштин|mitrovic|митровиц|kfor", re.I)
_STATE_TYPES = ("state-media", "state-aligned")


def serbian_ids(ids: list[str]) -> list[str]:
    """New reports from Serbian-language sources, most relevant first: those about Kosovo, then
    state-controlled or state-aligned media, then the rest; newest first within each group."""
    sigs = [s for s in db.fetch_by_ids(ids) if s["source_name"] in SERBIAN_SOURCES]

    def rank(s):
        about_kosovo = bool(_KOSOVO_MENTION.search(f"{s['title']} {s['text']}"))
        state = str(s.get("source_type", "")).startswith(_STATE_TYPES)
        return (not about_kosovo, not state)

    return [s["id"] for s in sorted(sorted(sigs, key=lambda s: s["timestamp"], reverse=True), key=rank)]


def start_serbian_local_ai(ids: list[str]) -> int:
    """Serbian is read by the local AI only (the keyword rules cover Albanian, English and German).
    Returns how many reports were queued (0 when Ollama is not running or another job is busy)."""
    queue = ids[: config.SERBIAN_LOCAL_AI_PER_INGEST]
    if not queue or not ollama.chat_model():
        return 0
    return len(queue) if jobs.start_label(queue) else 0


def start_model_check(ids: list[str]) -> bool:
    """A trained model on embeddings checks the new reports in the background (vectors are slow on a CPU)."""
    if not ids or not classifier.uses_embeddings():
        return False

    async def run():
        changed = await asyncio.to_thread(classifier.refine_stored, ids)
        if changed:
            invalidate_cache()
        log.info("trained model corrected %s of %s new reports", changed, len(ids))

    task = asyncio.create_task(run())
    STATE["tasks"].add(task)
    task.add_done_callback(STATE["tasks"].discard)
    return True


async def ingest_once() -> dict | None:
    if STATE["ingest_running"]:
        return None
    STATE["ingest_running"] = True
    try:
        if config.DEMO_OFFLINE:
            return await _offline_ingest()
        report = await run_live_ingest()
        invalidate_cache()
        new_ids = report.pop("new_ids", [])
        serbian = set(serbian_ids(new_ids))
        report["serbian_local_ai"] = start_serbian_local_ai(list(serbian))
        report["model_check"] = start_model_check(new_ids)
        report["llm_enrichment"] = start_enrichment([i for i in new_ids if i not in serbian])
        alerts, _ = _alerts("all", config.NOTIFY_LANG)
        report["notified"] = await notify.notify_new(alerts)
        STATE["last_ingest"] = report
        log.info("live ingest: %s fetched, %s new, %s notified", report["fetched"], report["inserted"], report["notified"])
        return report
    finally:
        STATE["ingest_running"] = False


async def _offline_ingest() -> dict:
    """Offline demo: replay the saved snapshot of real, AI-analysed signals as if just fetched."""
    started = utcnow()
    loaded = await asyncio.to_thread(load_snapshot)
    live = [s for s in await asyncio.to_thread(db.fetch_signals) if not s["synthetic"]]
    report = {
        "started_at": iso(started), "finished_at": iso(utcnow()), "offline": True,
        "fetched": loaded, "inserted": loaded, "threat_relevant": sum(1 for s in live if s["category"] != "other"),
        "sources": [{"source": "offline snapshot", "ok": loaded > 0, "items": loaded,
                     **({} if loaded else {"error": "no snapshot found: create one online first"})}],
        "notified": 0, "llm_enrichment": False,
    }
    STATE["last_ingest"] = report
    return report


async def live_loop():
    while True:
        try:
            await ingest_once()
        except Exception:  # noqa: BLE001
            log.exception("live ingest failed")
        await asyncio.sleep(config.LIVE_INGEST_INTERVAL_MIN * 60)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    invalidate_cache()
    db.init_db()
    if config.SEED_ON_START or db.count_signals() == 0:
        db.clear_feedback()
        log.info("scenario loaded: %s signals", reset_seed())
    if config.DEMO_OFFLINE:
        log.info("OFFLINE DEMO: snapshot loaded, %s signals; no network calls will be made", load_snapshot())
    elif config.LOAD_SNAPSHOT_ON_START:
        log.info("snapshot loaded on start: %s signals", load_snapshot())
    if not config.DEMO_OFFLINE and config.llm_enabled():
        # pick the models in the background so no request ever waits on the provider's model list
        warmup = asyncio.create_task(asyncio.to_thread(lambda: (resolve_model("analyze"), resolve_model("live"))))
        STATE["tasks"].add(warmup)
        warmup.add_done_callback(STATE["tasks"].discard)
    task = asyncio.create_task(live_loop()) if config.LIVE_INGEST_INTERVAL_MIN > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="HybridScope API", version="0.2.0", lifespan=lifespan)


@app.middleware("http")
async def clear_cache_on_change(request, call_next):
    """Feedback, corrections, ingest and resets change the data: the next read recomputes it."""
    response = await call_next(request)
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        invalidate_cache()
    return response


@app.middleware("http")
async def no_cache_html(request, call_next):
    """Always revalidate the dashboard's HTML so a rebuilt frontend is picked up immediately
    (the hashed JS/CSS assets can still be cached)."""
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _window(hours: float | None) -> float:
    """Time filter in hours, capped at the look-back window (None or 0 = the whole window)."""
    return min(float(hours), config.LOOKBACK_HOURS) if hours and hours > 0 else config.LOOKBACK_HOURS


# The dashboard asks for alerts, stats and the open alert at the same moment (and polls while the AI
# upgrades signals): computing the window once per few seconds keeps every request fast. Any change
# made through the API clears it at once.
CACHE_TTL_S = 5.0
_CACHE: dict[tuple, tuple[float, object]] = {}


def invalidate_cache() -> None:
    _CACHE.clear()


jobs.on_change(invalidate_cache)  # labelling and training jobs change what the pages show


def _cached(key: tuple, compute):
    hit = _CACHE.get(key)
    if hit and time.monotonic() - hit[0] < CACHE_TTL_S:
        return hit[1]
    value = compute()
    _CACHE[key] = (time.monotonic(), value)
    return value


def _window_signals(source: str):
    now = utcnow()
    sigs = db.fetch_signals(since_iso=iso(now - timedelta(hours=config.LOOKBACK_HOURS)))
    if source == "synthetic":
        sigs = [s for s in sigs if s["synthetic"]]
    elif source == "live":
        sigs = [s for s in sigs if not s["synthetic"]]
    sigs = [signal_view(s, now) for s in apply_feedback(sigs)]
    mark_duplicates(sigs)
    return sigs, now


def _signals(source: str = "all", hours: float | None = None):
    """Signals of the look-back window with the computed fields (bands, precision, duplicates, ...).
    `hours` keeps only signals published in the last N hours."""
    sigs, now = _cached(("signals", source), lambda: _window_signals(source))
    if hours and _window(hours) < config.LOOKBACK_HOURS:
        since = now - timedelta(hours=_window(hours))
        sigs = [s for s in sigs if parse_iso(s["timestamp"]) >= since]
    return sigs, now


def _alerts(source: str = "all", lang: str = "en", hours: float | None = None):
    """Alerts are always built from the whole window, so their IDs (and analyst verdicts) stay stable;
    the time filter then keeps the alerts with activity in the last N hours."""
    def compute():
        sigs, now = _signals(source)
        return [localize_alert(a, lang) for a in build_alerts(sigs, now)], now

    alerts, now = _cached(("alerts", source, norm_lang(lang)), compute)
    alerts = [dict(a) for a in alerts]  # verification is attached per request below
    if hours and _window(hours) < config.LOOKBACK_HOURS:
        since = now - timedelta(hours=_window(hours))
        alerts = [a for a in alerts if parse_iso(a["last_seen"]) >= since]
    feedback = db.get_feedback()
    for a in alerts:
        fb = feedback.get(a["id"])
        auto = (a.get("assessment") or {}).get("auto_verification") or {"status": "unverified"}
        # the evidence decides; an analyst's status, when set, overrides it
        a["verification"] = fb["verdict"] if fb else auto["status"]
        a["verification_source"] = "analyst" if fb else "auto"
        a["feedback"] = fb and {"verdict": fb["verdict"], "note": fb["note"], "at": fb["created_at"]}
    return alerts, now


def _localized_analysis(result: dict, lang: str) -> dict:
    """Swap in the rationale and zone name for the requested language."""
    out = dict(result)
    translated = (result.get("i18n") or {}).get(norm_lang(lang)) or {}
    if translated.get("rationale"):
        out["rationale"] = translated["rationale"]
    if out.get("location"):
        out["location"] = {**out["location"], "zone_label": zone_name(out["location"].get("zone"), lang)}
    return out


def _find(alert_id: str, source: str, lang: str = "en") -> dict:
    alerts, _ = _alerts(source, lang)
    for a in alerts:
        if a["id"] == alert_id:
            return a
    raise HTTPException(404, "Alert not found (it may have aged out or been re-clustered)")


def _alert_text(a: dict) -> str:
    parts = [a["title"], a["headline"], a["zone"], a.get("zone_label") or "", a["summary"]]
    parts += [e["name"] for e in a["shared_entities"]]
    parts += [t["id"] + " " + t["name"] for t in a["ttps"]]
    parts += [s["title"] for s in a["signals"]]
    return " ".join(parts).lower()


def _light(a: dict) -> dict:
    return {k: v for k, v in a.items() if k not in ("signals", "links")}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "offline": config.DEMO_OFFLINE,
        "public_mode": config.PUBLIC_MODE,
        "snapshot": snapshot_info(),
        "analyzer": active_analyzer(),
        "llm_enabled": config.llm_enabled(),
        "llm": {
            "provider": config.LLM_BASE_URL.split("/")[2] if config.llm_enabled() else None,
            "model_analyze": known_model("analyze") if config.llm_enabled() else None,
            "model_live": known_model("live") if config.llm_enabled() else None,
            "live_enrichment": config.LLM_FOR_LIVE,
            "enrich": {k: v for k, v in enrich.STATE.items() if k != "started_at"},
            "last_error": LLM_STATUS["last_error"],
        },
        "notify_channels": notify.channels(),
        "local_ai": {
            "available": ollama.available(),
            "chat_model": ollama.chat_model(),
            "trained_model": bool(classifier.info()),
            "job": jobs.STATE["job"] if jobs.STATE["running"] else None,
        },
        "live_interval_min": config.LIVE_INGEST_INTERVAL_MIN,
        "signals": db.count_signals(),
        "ingest_running": STATE["ingest_running"],
        "last_ingest": STATE["last_ingest"],
    }


@app.get("/api/stats")
def stats(source: str = "all", hours: Optional[float] = None, lang: str = "en"):
    """Dashboard numbers, all computed from the stored signals and the alerts built from them."""
    alerts, now = _alerts(source, lang, hours)
    sigs, _ = _signals(source, hours)
    relevant = [s for s in sigs if s["category"] != "other"]
    day_ago = now - timedelta(hours=24)
    recent = [s for s in sigs if parse_iso(s["timestamp"]) >= day_ago]

    # one bar per day (oldest first), split by category
    days = max(1, min(10, round(_window(hours) / 24)))
    trend = []
    for d in range(days - 1, -1, -1):
        start, end = now - timedelta(days=d + 1), now - timedelta(days=d)
        day = [s for s in relevant if start <= parse_iso(s["timestamp"]) < end]
        trend.append({"day": iso(end), "total": len(day), "by_category": dict(Counter(s["category"] for s in day))})

    feedback_stats = db.source_feedback_stats()
    per_source: dict[str, dict] = {}
    for s in sigs:
        row = per_source.setdefault(s["source_name"], {
            "name": source_label(s["source_name"], lang) if s["synthetic"] else s["source_name"],
            "key": s["source_name"], "type": s["source_type"],
            "reliability": s["source_reliability"], "prior": s.get("source_reliability_prior", s["source_reliability"]),
            "signals": 0, "relevant": 0, **feedback_stats.get(s["source_name"], {"confirmed": 0, "rejected": 0}),
        })
        row["signals"] += 1
        row["relevant"] += s["category"] != "other"
    by_country = Counter(zone_name(s.get("country"), lang) or s.get("country") for s in relevant if s.get("country"))

    return {
        "generated_at": iso(now),
        "window_hours": _window(hours),
        "signals_total": len(sigs),
        "signals_24h": len(recent),
        "threat_relevant": len(relevant),
        "live_signals": sum(1 for s in sigs if not s["synthetic"]),
        "synthetic_signals": sum(1 for s in sigs if s["synthetic"]),
        "sources": len({s["source_name"] for s in sigs}),
        "alerts": len(alerts),
        "hybrid_alerts": sum(1 for a in alerts if a["is_hybrid"]),
        "critical_alerts": sum(1 for a in alerts if a["level"] == "CRITICAL"),
        "infrastructure_alerts": sum(1 for a in alerts if "infrastructure" in a["categories"]),
        "reviewed_alerts": sum(1 for a in alerts if a["verification_source"] == "analyst"),
        "auto_verified": sum(1 for a in alerts if a["verification_source"] == "auto"),
        "duplicates": sum(1 for s in sigs if s.get("duplicate_of")),
        "unlocated": sum(1 for s in relevant if s.get("lat") is None),
        "by_category": dict(Counter(s["category"] for s in relevant)),
        "by_category_24h": dict(Counter(s["category"] for s in recent)),
        "by_level": dict(Counter(a["level"] for a in alerts)),
        "by_verification": dict(Counter(a["verification"] for a in alerts)),
        "by_country": [{"name": n, "count": c} for n, c in by_country.most_common(10)],
        "trend": trend,
        "source_stats": sorted(per_source.values(), key=lambda r: (-r["relevant"], -r["signals"]))[:15],
        "recent": [{"id": s["id"], "title": localize_signal(s, lang)["title"], "category": s["category"],
                    "subcategory": s.get("subcategory"),
                    "zone_label": zone_name(s.get("zone"), lang), "timestamp": s["timestamp"],
                    "severity_level": s["severity_level"], "synthetic": s["synthetic"]}
                   for s in sorted(relevant, key=lambda s: s["timestamp"], reverse=True)[:6]],
        "last_ingest": STATE["last_ingest"],
    }


@app.get("/api/geo")
def geo(source: str = "all", hours: Optional[float] = None, lang: str = "en"):
    """Where the threat-relevant reports are, grouped by place, for the density layer of the map."""
    sigs, _ = _signals(source, hours)
    places: dict[tuple, dict] = {}
    for s in sigs:
        if s["category"] == "other" or s.get("lat") is None:
            continue
        p = places.setdefault((s["lat"], s["lon"]), {
            "lat": s["lat"], "lon": s["lon"], "count": 0, "max_severity": 0.0, "categories": Counter(),
            "precision": s.get("geo_precision"), "label": zone_name(s.get("zone"), lang),
        })
        p["count"] += 1
        p["max_severity"] = max(p["max_severity"], s["severity"])
        p["categories"][s["category"]] += 1
    return {"points": [{**p, "categories": dict(p["categories"])} for p in places.values()]}


@app.get("/api/alerts")
def list_alerts(
    category: Optional[str] = None,
    zone: Optional[str] = None,
    min_confidence: float = 0.0,
    min_score: float = 0.0,
    hybrid_only: bool = False,
    hide_dismissed: bool = False,
    source: str = "all",
    q: Optional[str] = None,
    lang: str = "en",
    hours: Optional[float] = None,
):
    alerts, now = _alerts(source, lang, hours)
    zones = sorted(({"value": z, "label": zone_name(z, lang)} for z in {a["zone"] for a in alerts}),
                   key=lambda z: z["label"])
    needle = (q or "").strip().lower()
    filtered = [
        a for a in alerts
        if (not category or category in a["categories"])
        and (not zone or a["zone"] == zone)
        and a["confidence"] >= min_confidence
        and a["score"] >= min_score
        and (not hybrid_only or a["is_hybrid"])
        and (not hide_dismissed or a["verification"] != "disproved")
        and (not needle or needle in _alert_text(a))
    ]
    return {"generated_at": iso(now), "total": len(alerts), "zones": zones, "alerts": [_light(a) for a in filtered]}


@app.get("/api/alerts/{alert_id}")
def get_alert(alert_id: str, source: str = "all", lang: str = "en"):
    return _find(alert_id, source, lang)


@app.get("/api/alerts/{alert_id}/brief")
def get_brief(alert_id: str, source: str = "all", lang: str = "en"):
    return build_brief(_find(alert_id, source, lang), lang)


@app.get("/api/alerts/{alert_id}/replay")
def get_replay(alert_id: str, source: str = "all", lang: str = "en"):
    return replay(_find(alert_id, source, lang))


class FeedbackRequest(BaseModel):
    # verification status set by the analyst ("false_positive" is the old name of "disproved")
    verdict: Literal["unverified", "investigating", "partial", "confirmed", "disproved", "false_positive"]
    note: str = Field(default="", max_length=1000)


@app.post("/api/alerts/{alert_id}/feedback", dependencies=[Depends(require_admin)])
def post_feedback(alert_id: str, req: FeedbackRequest, source: str = "all"):
    alert = _find(alert_id, source)
    verdict = db.norm_verdict(req.verdict)
    if verdict == "unverified":
        db.delete_feedback(alert_id)
    else:
        db.set_feedback(alert_id, verdict, req.note or None, alert["sources"], iso(utcnow()))
    return {"ok": True, "verification": verdict, "sources_updated": alert["sources"],
            "source_stats": db.source_feedback_stats()}


class ClassificationRequest(BaseModel):
    category: Literal["cyber", "disinformation", "political", "infrastructure", "physical", "other"]
    subcategory: Optional[str] = None


@app.post("/api/signals/{signal_id}/classification", dependencies=[Depends(require_admin)])
def correct_classification(signal_id: str, req: ClassificationRequest):
    """Analyst correction of a report's category; the automatic category is kept as original_category."""
    sub = req.subcategory if req.subcategory in SUBCATEGORIES.get(req.category, {}) else None
    result = db.set_classification(signal_id, req.category, sub)
    if not result:
        raise HTTPException(404, "Signal not found")
    return {"ok": True, **result}


_SUMMARIES: dict[tuple, str] = {}


@app.get("/api/alerts/{alert_id}/ai-summary", dependencies=[Depends(limit_analyze)])
def ai_summary(alert_id: str, source: str = "all", lang: str = "en"):
    """A short plain-language summary written by the LLM from the alert's reports (when an LLM is set up)."""
    if not config.llm_enabled():
        raise HTTPException(400, "No LLM configured")
    alert = _find(alert_id, source, lang)
    key = (alert_id, alert["signal_count"], norm_lang(lang))
    if key not in _SUMMARIES:
        text = summarize_alert(alert, norm_lang(lang))
        if not text:
            raise HTTPException(503, "The AI summary is not available right now, please try again later")
        _SUMMARIES[key] = text
    return {"summary": _SUMMARIES[key], "model": known_model("analyze")}


@app.delete("/api/alerts/{alert_id}/feedback", dependencies=[Depends(require_admin)])
def delete_feedback(alert_id: str):
    db.delete_feedback(alert_id)
    return {"ok": True}


@app.post("/api/alerts/{alert_id}/notify", dependencies=[Depends(require_admin)])
async def notify_alert(alert_id: str, source: str = "all"):
    if not notify.channels():
        raise HTTPException(400, "No notification channel configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID or ALERT_WEBHOOK_URL)")
    return {"results": await notify.send(_find(alert_id, source, config.NOTIFY_LANG))}


@app.post("/api/notify/test", dependencies=[Depends(require_admin)])
async def notify_test():
    """Send a short test message to every configured channel."""
    if not notify.channels():
        raise HTTPException(400, "No notification channel configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID or ALERT_WEBHOOK_URL)")
    return {"results": await notify.send_test()}


@app.get("/api/graph")
def get_graph(source: str = "all", lang: str = "en", hours: Optional[float] = None):
    alerts, _ = _alerts(source, lang, hours)
    return build_graph(alerts)


@app.get("/api/signals")
def list_signals(
    limit: int = 300,
    category: Optional[str] = None,
    zone: Optional[str] = None,
    source: str = "all",
    q: Optional[str] = None,
    lang: str = "en",
    hours: Optional[float] = None,
):
    sigs, _ = _signals(source, hours)
    sigs = [localize_signal(s, lang) for s in sigs]
    needle = (q or "").strip().lower()
    out = [
        s for s in sigs
        if (not category or s["category"] == category)
        and (not zone or s["zone"] == zone)
        and (not needle or needle in f"{s['title']} {s['text']} {s['source_name']}".lower())
    ]
    return {"total": len(out), "signals": out[: max(1, min(limit, 2000))]}


@app.post("/api/ingest/live")
async def ingest_live(request: Request):
    last = STATE["last_ingest"]
    if config.PUBLIC_MODE and last and not is_admin(request):
        age = (utcnow() - parse_iso(last["finished_at"])).total_seconds()
        if age < config.INGEST_COOLDOWN_S:
            return {**last, "cooldown": True}  # fetched moments ago: show that run instead of refetching
    report = await ingest_once()
    if report is None:
        raise HTTPException(409, "Live ingestion already running")
    return report


@app.post("/api/llm/enrich", dependencies=[Depends(require_admin)])
async def llm_backfill(limit: int = 60):
    """Upgrade the most recent live signals that were analysed only by the local NLP."""
    if not config.llm_enabled():
        raise HTTPException(400, "No LLM configured: set LLM_API_KEY in backend/.env")
    if enrich.STATE["running"]:
        raise HTTPException(409, "LLM enrichment already running")
    limit = max(1, min(limit, 500))
    serbian = set(serbian_ids(db.fetch_unenriched_live(limit * 3)))  # Serbian is left to the local AI
    ids = [i for i in db.fetch_unenriched_live(limit * 3) if i not in serbian][:limit]
    return {"queued": len(ids), "started": start_enrichment(ids)}


@app.post("/api/demo/reset", dependencies=[Depends(require_admin)])
def demo_reset():
    db.clear_feedback()
    return {"loaded": reset_seed()}


class AnalyzeRequest(BaseModel):
    title: str = ""
    text: str = Field(min_length=3, max_length=8000)
    use_llm: bool = True
    use_local: bool = True            # the local LLM (Ollama), when it is running
    image_base64: Optional[str] = Field(default=None, max_length=8_000_000)  # a picture to analyse with the text
    lang: str = "en"


@app.post("/api/analyze", dependencies=[Depends(limit_analyze)])
def analyze_text(req: AnalyzeRequest):
    image_b64 = preview = image_vector = None
    if req.image_base64:
        try:
            raw = decode_upload(req.image_base64)
            image_b64, preview = prepare_image(raw)
        except ImageError as exc:
            raise HTTPException(400, f"Image: {exc}") from exc
        if classifier.uses_images():  # the trained model also looks at the picture (CLIP vector)
            image_vector = image_embeddings.embed_bytes(raw)
    local_ready = bool(req.use_local and ollama.chat_model())
    key = cache_key(req.title, req.text)
    cached = None if (image_b64 or local_ready) else db.cache_get(key)
    if cached:  # identical text analysed before: instant, and spares the LLM quota
        return {**_localized_analysis(cached, req.lang), "cached": True}
    use_cloud = req.use_llm and not config.DEMO_OFFLINE
    result = analyze(req.title, req.text, use_llm=use_cloud, use_local_llm=local_ready, use_model=True,
                     image_b64=image_b64 if local_ready else None, image_vector=image_vector)
    if result["analyzer"].startswith("llm:") and not image_b64:
        db.cache_put(key, req.title, req.text, result, iso(utcnow()))  # replayable in the offline demo
    out = _localized_analysis(result, req.lang)
    if req.use_local:  # fake-news check by our fine-tuned model (English reason; it reads any of our languages)
        out["fact_check"] = local_llm.fact_check(req.title, req.text)
    if config.DEMO_OFFLINE:
        out["offline"] = True
    if image_b64:
        out["image_preview"] = preview
        out["image_skipped"] = not local_ready  # only the local vision model can read pictures
    return out


# --- Local AI (Ollama + model trained on our data) --------------------------------------
@app.get("/api/ml/status")
def ml_status():
    return {
        "ollama": ollama.status(),
        "classifier": classifier.info(),
        "dataset": _cached(("ml-dataset",), dataset.stats),
        "embeddings": db.count_embeddings(),
        "image_model": {"available": image_embeddings.available(), "name": image_embeddings.MODEL_NAME},
        "job": jobs.status(),
        "local_llm_for_live": config.LOCAL_LLM_FOR_LIVE,
        "classifier_min_prob": config.CLASSIFIER_MIN_PROB,
        "decision_threshold": classifier.decision_threshold(),
        "target_precision": config.CLASSIFIER_TARGET_PRECISION,
    }


@app.post("/api/ml/train", dependencies=[Depends(require_admin)])
def ml_train():
    if not jobs.start_train():
        raise HTTPException(409, "Another local-AI job is running")
    return {"started": True}


@app.post("/api/ml/label", dependencies=[Depends(require_admin)])
def ml_label(limit: int = 20, images: bool = False):
    """Let the local LLM label reports that only the keyword rules have seen (new training data).
    images=true: reports with a picture, read as text + picture together (for text+image training)."""
    if not ollama.chat_model():
        raise HTTPException(400, f"The local LLM is not available: start Ollama and run `ollama pull {config.OLLAMA_MODEL}`")
    limit = max(1, min(limit, 200))
    ids = db.fetch_unenriched_with_images(limit) if images else db.fetch_unenriched_live(limit)
    if not ids:
        return {"started": False, "queued": 0}
    if not jobs.start_label(ids, with_images=images):
        raise HTTPException(409, "Another local-AI job is running")
    return {"started": True, "queued": len(ids)}


EXPORT_FILES = ("classification.jsonl", "sft_chat.jsonl", "verification.jsonl", "dataset_card.md")


@app.post("/api/ml/export", dependencies=[Depends(require_admin)])
async def ml_export():
    return await asyncio.to_thread(dataset.export)


@app.get("/api/ml/export/{name}", dependencies=[Depends(require_admin)])
def ml_export_file(name: str):
    if name not in EXPORT_FILES:
        raise HTTPException(404, "Unknown file")
    path = config.DATASET_DIR / name
    if not path.exists():
        raise HTTPException(404, "Export the dataset first")
    return FileResponse(path, filename=f"hybridscope-{name}",
                        media_type="text/markdown" if name.endswith(".md") else "application/jsonl")


@app.post("/api/ml/create-model", dependencies=[Depends(require_admin)])
async def ml_create_model():
    """Build the 'hybridscope' model in Ollama: the base model + our instructions + labelled examples."""
    if not ollama.available() or not ollama.has_model(config.OLLAMA_MODEL):
        raise HTTPException(400, f"Base model missing: run `ollama pull {config.OLLAMA_MODEL}`")
    from .analyzer.llm import SYSTEM_PROMPT

    records = sorted((r for r in dataset.build() if r["weight"] > 0),
                     key=lambda r: (-r["weight"], len(r["text"])))
    examples, per_cat = [], Counter()
    for r in records:  # two short examples per category, gold first
        if per_cat[r["category"]] < 2 and len(r["text"]) <= 700:
            per_cat[r["category"]] += 1
            examples += [{"role": "user", "content": f"TITLE: {r['title']}\n\nTEXT: {r['text']}"},
                         {"role": "assistant", "content": local_llm._example_answer(r)}]
    try:
        res = await asyncio.to_thread(ollama.create_model, config.OLLAMA_CUSTOM_MODEL, config.OLLAMA_MODEL,
                                      SYSTEM_PROMPT, examples, {"temperature": 0, "num_ctx": 8192})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Ollama could not create the model: {exc}") from exc
    return {"model": config.OLLAMA_CUSTOM_MODEL, "base": config.OLLAMA_MODEL, "examples": len(examples) // 2,
            "status": res.get("status", "success")}


_VERIFICATIONS: dict[tuple, dict] = {}


@app.post("/api/alerts/{alert_id}/verify-ai", dependencies=[Depends(limit_analyze)])
def verify_ai(alert_id: str, source: str = "all", lang: str = "en"):
    """Second opinion from the local LLM: is this alert one coordinated hybrid campaign?"""
    if not ollama.chat_model():
        raise HTTPException(400, "The local LLM is not available")
    alert = _find(alert_id, source, "en")  # the model reads the original texts; it answers in `lang`
    key = (alert_id, alert["signal_count"], norm_lang(lang))
    if key not in _VERIFICATIONS:
        result = local_llm.verify_alert(alert, norm_lang(lang))
        if not result:
            raise HTTPException(503, "The local LLM did not answer, please try again")
        _VERIFICATIONS[key] = {**result, "at": iso(utcnow())}
    return _VERIFICATIONS[key]


@app.post("/api/signals/{signal_id}/image", dependencies=[Depends(limit_analyze)])
def analyze_signal_image(signal_id: str):
    """Describe the picture of a report with the local vision model (only pictures collected from the feeds)."""
    sig = db.fetch_signal(signal_id)
    if not sig or not sig.get("image_url"):
        raise HTTPException(404, "This report has no picture")
    stored = db.image_analysis_get(sig["image_url"])
    if stored:
        return {**stored["result"], "preview": stored["preview"], "cached": True}
    if not ollama.chat_model():
        raise HTTPException(400, "The local LLM is not available")
    try:
        b64, preview = prepare_image(fetch_image(sig["image_url"]))
    except (ImageError, Exception) as exc:  # noqa: BLE001 - network and format problems are reported, not raised
        raise HTTPException(422, f"The picture could not be loaded: {exc}") from exc
    result = local_llm.analyze_image(b64, sig["title"])
    if not result:
        raise HTTPException(503, "The local LLM did not answer, please try again")
    db.image_analysis_put(sig["image_url"], result["model"], result, preview, iso(utcnow()))
    return {**result, "preview": preview}


@app.get("/api/analyze/samples")
def analyze_samples():
    return [{**s, "cached": db.cache_get(cache_key(s.get("title", ""), s["text"])) is not None} for s in load_samples()]


@app.post("/api/demo/snapshot", dependencies=[Depends(require_admin)])
async def demo_snapshot():
    if config.DEMO_OFFLINE:
        raise HTTPException(400, "Create the snapshot while online (DEMO_OFFLINE=0)")
    return await asyncio.to_thread(export_snapshot)


# Serve the built dashboard (frontend/dist) from the same port when it exists.
if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="dashboard")
