"""HybridScope API."""
import asyncio
import logging
import secrets
import time
from collections import Counter, defaultdict, deque
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, db, enrich, notify
from .analyzer import LLM_STATUS, active_analyzer, analyze
from .analyzer.llm import known_model, resolve_model
from .brief import build_brief
from .correlation import build_alerts, replay
from .feedback import apply_feedback
from .graph import build_graph
from .ingest.live import run_live_ingest
from .ingest.seed import reset_seed
from .normalize import iso, parse_iso, utcnow
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
    """Upgrade signals with the LLM in the background (keeps a reference so the task is not GC'd)."""
    if not (config.llm_enabled() and config.LLM_FOR_LIVE and ids):
        return False
    task = asyncio.create_task(enrich.enrich_signals(ids))
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
        report["llm_enrichment"] = start_enrichment(report.pop("new_ids", []))
        alerts, _ = _alerts("all")
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


def _signals(source: str = "all"):
    now = utcnow()
    sigs = db.fetch_signals(since_iso=iso(now - timedelta(hours=config.LOOKBACK_HOURS)))
    if source == "synthetic":
        sigs = [s for s in sigs if s["synthetic"]]
    elif source == "live":
        sigs = [s for s in sigs if not s["synthetic"]]
    return apply_feedback(sigs), now


def _alerts(source: str = "all"):
    sigs, now = _signals(source)
    alerts = build_alerts(sigs, now)
    feedback = db.get_feedback()
    for a in alerts:
        fb = feedback.get(a["id"])
        a["feedback"] = fb and {"verdict": fb["verdict"], "note": fb["note"], "at": fb["created_at"]}
    return alerts, now


def _find(alert_id: str, source: str) -> dict:
    alerts, _ = _alerts(source)
    for a in alerts:
        if a["id"] == alert_id:
            return a
    raise HTTPException(404, "Alert not found (it may have aged out or been re-clustered)")


def _alert_text(a: dict) -> str:
    parts = [a["title"], a["headline"], a["zone"], a["summary"]]
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
        "live_interval_min": config.LIVE_INGEST_INTERVAL_MIN,
        "signals": db.count_signals(),
        "ingest_running": STATE["ingest_running"],
        "last_ingest": STATE["last_ingest"],
    }


@app.get("/api/stats")
def stats(source: str = "all"):
    alerts, now = _alerts(source)
    sigs, _ = _signals(source)
    day_ago = now - timedelta(hours=24)
    recent = [s for s in sigs if parse_iso(s["timestamp"]) >= day_ago]
    return {
        "generated_at": iso(now),
        "signals_total": len(sigs),
        "signals_24h": len(recent),
        "threat_relevant": sum(1 for s in sigs if s["category"] != "other"),
        "live_signals": sum(1 for s in sigs if not s["synthetic"]),
        "synthetic_signals": sum(1 for s in sigs if s["synthetic"]),
        "sources": len({s["source_name"] for s in sigs}),
        "alerts": len(alerts),
        "hybrid_alerts": sum(1 for a in alerts if a["is_hybrid"]),
        "critical_alerts": sum(1 for a in alerts if a["level"] == "CRITICAL"),
        "reviewed_alerts": sum(1 for a in alerts if a["feedback"]),
        "by_category_24h": dict(Counter(s["category"] for s in recent)),
        "by_level": dict(Counter(a["level"] for a in alerts)),
        "last_ingest": STATE["last_ingest"],
    }


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
):
    alerts, now = _alerts(source)
    zones = sorted({a["zone"] for a in alerts})
    needle = (q or "").strip().lower()
    filtered = [
        a for a in alerts
        if (not category or category in a["categories"])
        and (not zone or a["zone"] == zone)
        and a["confidence"] >= min_confidence
        and a["score"] >= min_score
        and (not hybrid_only or a["is_hybrid"])
        and (not hide_dismissed or not a["feedback"] or a["feedback"]["verdict"] != "false_positive")
        and (not needle or needle in _alert_text(a))
    ]
    return {"generated_at": iso(now), "total": len(alerts), "zones": zones, "alerts": [_light(a) for a in filtered]}


@app.get("/api/alerts/{alert_id}")
def get_alert(alert_id: str, source: str = "all"):
    return _find(alert_id, source)


@app.get("/api/alerts/{alert_id}/brief")
def get_brief(alert_id: str, source: str = "all"):
    return build_brief(_find(alert_id, source))


@app.get("/api/alerts/{alert_id}/replay")
def get_replay(alert_id: str, source: str = "all"):
    return replay(_find(alert_id, source))


class FeedbackRequest(BaseModel):
    verdict: Literal["confirmed", "false_positive"]
    note: str = Field(default="", max_length=1000)


@app.post("/api/alerts/{alert_id}/feedback", dependencies=[Depends(require_admin)])
def post_feedback(alert_id: str, req: FeedbackRequest, source: str = "all"):
    alert = _find(alert_id, source)
    db.set_feedback(alert_id, req.verdict, req.note or None, alert["sources"], iso(utcnow()))
    return {"ok": True, "sources_updated": alert["sources"], "source_stats": db.source_feedback_stats()}


@app.delete("/api/alerts/{alert_id}/feedback", dependencies=[Depends(require_admin)])
def delete_feedback(alert_id: str):
    db.delete_feedback(alert_id)
    return {"ok": True}


@app.post("/api/alerts/{alert_id}/notify", dependencies=[Depends(require_admin)])
async def notify_alert(alert_id: str, source: str = "all"):
    if not notify.channels():
        raise HTTPException(400, "No notification channel configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID or ALERT_WEBHOOK_URL)")
    return {"results": await notify.send(_find(alert_id, source))}


@app.get("/api/graph")
def get_graph(source: str = "all"):
    alerts, _ = _alerts(source)
    return build_graph(alerts)


@app.get("/api/signals")
def list_signals(
    limit: int = 300,
    category: Optional[str] = None,
    zone: Optional[str] = None,
    source: str = "all",
    q: Optional[str] = None,
):
    sigs, _ = _signals(source)
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
    ids = db.fetch_unenriched_live(max(1, min(limit, 500)))
    return {"queued": len(ids), "started": start_enrichment(ids)}


@app.post("/api/demo/reset", dependencies=[Depends(require_admin)])
def demo_reset():
    db.clear_feedback()
    return {"loaded": reset_seed()}


class AnalyzeRequest(BaseModel):
    title: str = ""
    text: str = Field(min_length=3, max_length=8000)
    use_llm: bool = True


@app.post("/api/analyze", dependencies=[Depends(limit_analyze)])
def analyze_text(req: AnalyzeRequest):
    key = cache_key(req.title, req.text)
    cached = db.cache_get(key)  # identical text analysed before: instant, and spares the LLM quota
    if cached:
        return {**cached, "cached": True}
    if config.DEMO_OFFLINE:
        return {**analyze(req.title, req.text, use_llm=False), "offline": True}
    result = analyze(req.title, req.text, use_llm=req.use_llm)
    if result["analyzer"].startswith("llm:"):
        db.cache_put(key, req.title, req.text, result, iso(utcnow()))  # replayable in the offline demo
    return result


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
