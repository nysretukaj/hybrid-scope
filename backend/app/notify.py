"""Push notifications for high-risk alerts: Telegram bot and/or a generic webhook (Slack, Discord, Teams...).

Setup (Telegram):
  1. Create a bot with @BotFather and put TELEGRAM_BOT_TOKEN=... in backend/.env
  2. Open the bot in Telegram and press Start (or send any message)
  3. python -m app.notify --setup   -> finds your chat id, saves TELEGRAM_CHAT_ID and sends a test message
Messages are written in NOTIFY_LANG (en, sq or de). Without a token/chat id notifications are disabled.
"""
import logging

import httpx

from . import config, db
from .i18n import cat_label, tr
from .normalize import iso, utcnow

log = logging.getLogger(__name__)
LEVEL_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
LEVEL_ICON = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "🟡", "LOW": "ℹ️"}
TELEGRAM_API = "https://api.telegram.org"


def channels() -> list[str]:
    out = []
    if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
        out.append("telegram")
    if config.ALERT_WEBHOOK_URL:
        out.append("webhook")
    return out


def format_message(alert: dict, lang: str | None = None) -> str:
    """alert should already be localized to `lang` (title, headline, zone_label)."""
    lang = lang or config.NOTIFY_LANG
    lines = [
        f"{LEVEL_ICON.get(alert['level'], '•')} HybridScope · {tr('level.' + alert['level'], lang)} "
        f"({alert['score']:.0f}/100){tr('n.hybrid', lang) if alert['is_hybrid'] else ''}",
        alert["title"],
        tr("n.latest", lang, h=alert["headline"]),
        tr("n.domains", lang, cats=", ".join(cat_label(c, lang) for c in alert["categories"]),
           n=alert["signal_count"], k=alert["source_count"], c=f"{alert['confidence'] * 100:.0f}"),
    ]
    if alert.get("synthetic"):
        lines.append(tr("n.exercise", lang))
    if config.PUBLIC_URL:
        lines.append(f"{tr('n.open', lang)}: {config.PUBLIC_URL}/#alert={alert['id']}")
    return "\n".join(lines)


async def _deliver(text: str) -> list[dict]:
    results = []
    async with httpx.AsyncClient(timeout=10) as client:
        for ch in channels():
            try:
                if ch == "telegram":
                    r = await client.post(f"{TELEGRAM_API}/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
                                          json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text,
                                                "disable_web_page_preview": True})
                else:
                    r = await client.post(config.ALERT_WEBHOOK_URL, json={"text": text, "content": text})
                r.raise_for_status()
                results.append({"channel": ch, "ok": True})
            except Exception as exc:  # noqa: BLE001
                # never log or return the token embedded in the Telegram URL
                msg = str(exc).replace(config.TELEGRAM_BOT_TOKEN, "***") if config.TELEGRAM_BOT_TOKEN else str(exc)
                log.warning("notification via %s failed: %s", ch, msg)
                results.append({"channel": ch, "ok": False, "error": msg[:160]})
    return results


async def send(alert: dict, lang: str | None = None) -> list[dict]:
    results = await _deliver(format_message(alert, lang))
    if any(r["ok"] for r in results):
        db.mark_notified(alert["id"], iso(utcnow()))
    return results


async def send_test(lang: str | None = None) -> list[dict]:
    return await _deliver(tr("n.test", lang or config.NOTIFY_LANG))


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


# --- setup helper ----------------------------------------------------------------
def find_chats() -> list[dict]:
    """Chats that have messaged the bot recently (Telegram getUpdates)."""
    r = httpx.get(f"{TELEGRAM_API}/bot{config.TELEGRAM_BOT_TOKEN}/getUpdates", timeout=15)
    r.raise_for_status()
    chats: dict[int, dict] = {}
    for upd in r.json().get("result", []):
        msg = upd.get("message") or upd.get("channel_post") or upd.get("my_chat_member") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            name = chat.get("title") or " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")]))
            chats[chat["id"]] = {"id": chat["id"], "type": chat.get("type"), "name": name or chat.get("username")}
    return list(chats.values())


def _save_chat_id(chat_id: int) -> None:
    env = config.BACKEND_DIR / ".env"
    lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
    lines = [line for line in lines if not line.strip().startswith("TELEGRAM_CHAT_ID=")]
    lines.append(f"TELEGRAM_CHAT_ID={chat_id}")
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    import asyncio
    import sys

    if "--setup" not in sys.argv:
        print(__doc__)
        sys.exit(0)
    if not config.TELEGRAM_BOT_TOKEN:
        sys.exit("TELEGRAM_BOT_TOKEN is missing in backend/.env")
    me = httpx.get(f"{TELEGRAM_API}/bot{config.TELEGRAM_BOT_TOKEN}/getMe", timeout=15)
    if me.status_code != 200:
        sys.exit("The bot token was rejected by Telegram - check TELEGRAM_BOT_TOKEN in backend/.env")
    bot = me.json()["result"]
    print(f"Bot: @{bot['username']}")
    chats = find_chats()
    if not chats:
        sys.exit(f"No messages yet. Open https://t.me/{bot['username']} in Telegram, press Start, then run this again.")
    chat = chats[-1]
    _save_chat_id(chat["id"])
    config.TELEGRAM_CHAT_ID = str(chat["id"])
    print(f"Chat found: {chat['name']} ({chat['type']}) - saved TELEGRAM_CHAT_ID to backend/.env")
    print("Test message:", asyncio.run(send_test()))
