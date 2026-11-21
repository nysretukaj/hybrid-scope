"""Public Telegram channels, read from Telegram's public web preview (https://t.me/s/<channel>).

No account and no API: only what anyone sees in a browser without logging in. Telegram's robots.txt
is respected. Each post becomes a report linking back to https://t.me/<channel>/<id>.
"""
import html
import re
from datetime import datetime, timezone
from urllib.robotparser import RobotFileParser

import httpx

from .. import config
from ..ml.images import clean_url

_POST = re.compile(r'data-post="([A-Za-z0-9_]+/\d+)"')
_TEXT = re.compile(r'<div class="tgme_widget_message_text[^"]*"[^>]*>(.*?)</div>', re.S)
_TIME = re.compile(r'<time[^>]+datetime="([^"]+)"')
_PHOTO = re.compile(r"tgme_widget_message_photo_wrap[^>]+background-image:url\('([^']+)'\)")
_BR = re.compile(r"<br\s*/?>", re.I)
_TAGS = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _clean(fragment: str) -> str:
    return _WS.sub(" ", html.unescape(_TAGS.sub(" ", _BR.sub("\n", fragment)))).strip()


def parse_channel(page: str, source: dict, limit: int = 20) -> list[dict]:
    """Posts of a channel preview page, newest last (as Telegram shows them)."""
    chunks = _POST.split(page)  # [before, post_id, body, post_id, body, ...]
    items = []
    for post_id, body in zip(chunks[1::2], chunks[2::2]):
        m_text = _TEXT.search(body)
        text = _clean(m_text.group(1)) if m_text else ""
        if len(text) < 20:  # photos without a caption, stickers, polls...
            continue
        m_time = _TIME.search(body)
        try:
            ts = datetime.fromisoformat(m_time.group(1)) if m_time else None
        except ValueError:
            ts = None
        if ts and not ts.tzinfo:
            ts = ts.replace(tzinfo=timezone.utc)
        photo = _PHOTO.search(body)
        title = text if len(text) <= 140 else text[:140].rsplit(" ", 1)[0] + "…"
        items.append({
            "source_name": source["name"], "source_type": source["type"], "reliability": source["reliability"],
            "title": title, "text": text[:1500], "url": f"https://t.me/{post_id}",
            "timestamp": ts or datetime.now(timezone.utc), "image_url": clean_url(photo.group(1)) if photo else None,
        })
    return items[-limit:]


async def fetch_telegram(client: httpx.AsyncClient, source: dict) -> list[dict]:
    url = f"https://t.me/s/{source['channel']}"
    rp = RobotFileParser()
    try:
        r = await client.get("https://t.me/robots.txt")
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
    except httpx.HTTPError:
        rp.parse([])
    if not rp.can_fetch(config.USER_AGENT, url):
        raise PermissionError("robots.txt does not allow reading this channel")
    resp = await client.get(url, follow_redirects=True)
    resp.raise_for_status()
    items = parse_channel(resp.text, source)
    if not items and "tgme_channel_info" not in resp.text:
        raise RuntimeError("channel not found or not public")
    return items
