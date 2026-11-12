"""Push notifications for high-risk alerts: Telegram bot and/or a generic webhook (Slack, Discord, Teams...).

Configure with TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID and/or ALERT_WEBHOOK_URL. Without them
notifications are simply disabled.
"""
import logging

import httpx

from . import config, db
from .normalize import iso, utcnow

log = logging.getLogger(__name__)
LEVEL_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def channels() -> list[str]:
    out = []
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        out.append("telegram")
    if config.ALERT_WEBHOOK_URL:
        out.append("webhook")
    return out


def format_message(alert: dict) -> str:
    lines = [
        f"🚨 HybridScope {alert['level']} ({alert['score']:.0f}/100){' · HYBRID' if alert['is_hybrid'] else ''}",
        f"{alert['title']}",
        f"Latest: {alert['headline']}",
        f"Domains: {', '.join(alert['categories'])} · {alert['signal_count']} signals / {alert['source_count']} sources · "
        f"confidence {alert['confidence'] * 100:.0f}%",
    ]
    if alert.get("synthetic"):
        lines.append("[EXERCISE - synthetic scenario data]")
    if config.PUBLIC_URL:
        lines.append(f"{config.PUBLIC_URL}/#alert={alert['id']}")
    return "\n".join(lines)


async def send(alert: dict) -> list[dict]:
    text = format_message(alert)
    results = []
    async with httpx.AsyncClient(timeout=10) as client:
        for ch in channels():
            try:
                if ch == "telegram":
                    r = await client.post(f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                                          json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text, "disable_web_page_preview": True})
                else:
                    r = await client.post(config.ALERT_WEBHOOK_URL, json={"text": text, "content": text})
                r.raise_for_status()
                results.append({"channel": ch, "ok": True})
            except Exception as exc:  # noqa: BLE001
                log.warning("notification via %s failed: %s", ch, exc)
                results.append({"channel": ch, "ok": False, "error": str(exc)[:160]})
    if any(r["ok"] for r in results):
        db.mark_notified(alert["id"], iso(utcnow()))
    return results


async def notify_new(alerts: list[dict]) -> int:
    """Auto-notify live (non-synthetic) alerts at or above NOTIFY_MIN_LEVEL, once per alert."""
    if not channels():
        return 0
    threshold = LEVEL_RANK.get(config.NOTIFY_MIN_LEVEL, 3)
    sent = 0
    for a in alerts:
        if a["synthetic"] or LEVEL_RANK[a["level"]] < threshold or db.was_notified(a["id"]):
            continue
        if any(r["ok"] for r in await send(a)):
            sent += 1
    return sent
