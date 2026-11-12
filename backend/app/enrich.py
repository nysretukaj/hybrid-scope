"""Background LLM enrichment of live signals.

Live items are stored immediately with the local analyzer, so ingestion stays fast. This task
then re-analyses them with the LLM one by one, threat-relevant ones first, paced to stay under
the provider's free-tier rate limit. The dashboard picks up each upgraded signal on its next poll.
"""
import asyncio
import logging
import time

from . import config, db
from .analyzer.llm import STATUS as LLM_STATUS
from .analyzer.llm import analyze_llm, rate_limited
from .analyzer.local import merge_entities

log = logging.getLogger(__name__)
STATE: dict = {"running": False, "queued": 0, "done": 0, "failed": 0, "changed_category": 0, "started_at": None}
_lock = asyncio.Lock()


def _priority(s: dict) -> tuple:
    return (s["category"] == "other", -s["severity"])


async def enrich_signals(ids: list[str]) -> dict:
    if not config.llm_enabled() or not ids:
        return STATE
    async with _lock:
        sigs = sorted(await asyncio.to_thread(db.fetch_by_ids, ids), key=_priority)[: config.LLM_MAX_PER_INGEST]
        STATE.update(running=True, queued=len(sigs), done=0, failed=0, changed_category=0, started_at=time.time())
        interval = 60.0 / max(1.0, config.LLM_RPM)
        consecutive_failures = 0
        try:
            for s in sigs:
                result = None
                for attempt in range(4):  # retry after rate limits and short network drops
                    while rate_limited():
                        await asyncio.sleep(1)
                    started = time.monotonic()
                    result = await asyncio.to_thread(analyze_llm, s["title"], s["text"], "live")
                    await asyncio.sleep(max(0.0, interval - (time.monotonic() - started)))
                    if result:
                        break
                    if LLM_STATUS.get("transient"):
                        await asyncio.sleep(5 * (attempt + 1))  # back off: 5 s, 10 s, 15 s
                        continue
                    if not rate_limited():
                        break
                if result:
                    consecutive_failures = 0
                    result["entities"] = merge_entities(s["entities"], result["entities"])
                    await asyncio.to_thread(db.update_analysis, s["id"], result)
                    STATE["done"] += 1
                    if result["category"] != s["category"]:
                        STATE["changed_category"] += 1
                else:
                    STATE["failed"] += 1
                    consecutive_failures += 1
                    if consecutive_failures >= 3:
                        log.warning("stopping LLM enrichment after repeated failures: %s", LLM_STATUS["last_error"])
                        break
        finally:
            STATE["running"] = False
    log.info("LLM enrichment: %s upgraded, %s failed", STATE["done"], STATE["failed"])
    return STATE
