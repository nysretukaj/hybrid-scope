"""HybridScope API."""
import asyncio
import logging
from collections import Counter
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, db
from .analyzer import active_analyzer, analyze
from .correlation import build_alerts
from .ingest.live import run_live_ingest
from .ingest.seed import load_seed, reset_seed
from .normalize import iso, parse_iso, utcnow

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("hybridscope")

STATE: dict = {"last_ingest": None, "ingest_running": False}


async def ingest_once() -> dict | None:
    if STATE["ingest_running"]:
        return None
    STATE["ingest_running"] = True
    try:
        report = await run_live_ingest()
        STATE["last_ingest"] = report
        log.info("live ingest: %s fetched, %s new", report["fetched"], report["inserted"])
        return report
    finally:
        STATE["ingest_running"] = False


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
        log.info("scenario loaded: %s signals", reset_seed())
    task = asyncio.create_task(live_loop()) if config.LIVE_INGEST_INTERVAL_MIN > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="HybridScope API", version="0.1.0", lifespan=lifespan)
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
    return sigs, now


def _alert_text(a: dict) -> str:
    parts = [a["title"], a["headline"], a["zone"], a["summary"]]
    parts += [e["name"] for e in a["shared_entities"]]
    parts += [s["title"] for s in a["signals"]]
    return " ".join(parts).lower()


def _light(a: dict) -> dict:
    return {k: v for k, v in a.items() if k not in ("signals", "links")}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "analyzer": active_analyzer(),
        "llm_enabled": config.llm_enabled(),
        "live_interval_min": config.LIVE_INGEST_INTERVAL_MIN,
        "signals": db.count_signals(),
        "ingest_running": STATE["ingest_running"],
        "last_ingest": STATE["last_ingest"],
    }


@app.get("/api/stats")
def stats(source: str = "all"):
    sigs, now = _signals(source)
    alerts = build_alerts(sigs, now)
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
    source: str = "all",
    q: Optional[str] = None,
):
    sigs, now = _signals(source)
    alerts = build_alerts(sigs, now)
    zones = sorted({a["zone"] for a in alerts})
    needle = (q or "").strip().lower()
    filtered = [
        a for a in alerts
        if (not category or category in a["categories"])
        and (not zone or a["zone"] == zone)
        and a["confidence"] >= min_confidence
        and a["score"] >= min_score
        and (not hybrid_only or a["is_hybrid"])
        and (not needle or needle in _alert_text(a))
    ]
    return {"generated_at": iso(now), "total": len(alerts), "zones": zones, "alerts": [_light(a) for a in filtered]}


@app.get("/api/alerts/{alert_id}")
def get_alert(alert_id: str, source: str = "all"):
    sigs, now = _signals(source)
    for a in build_alerts(sigs, now):
        if a["id"] == alert_id:
            return a
    raise HTTPException(404, "Alert not found (it may have aged out or been re-clustered)")


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
async def ingest_live():
    report = await ingest_once()
    if report is None:
        raise HTTPException(409, "Live ingestion already running")
    return report


@app.post("/api/demo/reset")
def demo_reset():
    return {"loaded": reset_seed()}


class AnalyzeRequest(BaseModel):
    title: str = ""
    text: str = Field(min_length=3, max_length=8000)
    use_llm: bool = True


@app.post("/api/analyze")
def analyze_text(req: AnalyzeRequest):
    return analyze(req.title, req.text, use_llm=req.use_llm)


# Serve the built dashboard (frontend/dist) from the same port when it exists.
if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="dashboard")
