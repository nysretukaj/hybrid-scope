"""Polite reader for public websites that have no RSS feed.

For each configured site: read robots.txt and stop if it disallows us, fetch the news list page,
pick the article links that match the site's pattern, and read at most `max` articles we do not
have yet, one per SCRAPE_DELAY_S seconds. From each article only its own public metadata is kept:
title, summary, picture and publication date (OpenGraph / article meta tags, <time>, JSON-LD).
"""
import asyncio
import html
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from .. import config, db
from ..ml.images import clean_url
from ..normalize import make_id, utcnow

_HREF = re.compile(r'href=["\']([^"\'#]+)["\']', re.I)
_TIME_TAG = re.compile(r'<time[^>]+datetime=["\']([^"\']+)["\']', re.I)
_JSONLD_DATE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')
_TAGS = re.compile(r"<[^>]+>")


def meta(page: str, prop: str) -> str | None:
    """Content of <meta property|name="prop" content="..."> in either attribute order."""
    for rx in (rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]*content=["\']([^"\']*)["\']',
               rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']{re.escape(prop)}["\']'):
        m = re.search(rx, page, re.I)
        if m:
            value = html.unescape(m.group(1)).strip()
            return value or None
    return None


def article_links(page: str, base_url: str, pattern: str) -> list[str]:
    """Same-site links whose path matches the article pattern, in page order, without duplicates."""
    host = urlparse(base_url).netloc
    rx = re.compile(pattern)
    out = []
    for href in _HREF.findall(page):
        url = urljoin(base_url, href.strip())
        p = urlparse(url)
        if p.netloc == host and p.scheme in ("http", "https") and rx.search(p.path) and url not in out:
            out.append(url.split("?")[0])
    return list(dict.fromkeys(out))


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def parse_article(page: str, url: str, strip_title: str = "") -> dict | None:
    title = meta(page, "og:title") or (re.search(r"<title>(.*?)</title>", page, re.S | re.I) or [None, None])[1]
    if not title:
        return None
    title = _TAGS.sub(" ", html.unescape(title)).strip()
    if strip_title and title.endswith(strip_title):
        title = title[: -len(strip_title)].strip()
    text = meta(page, "og:description") or meta(page, "description") or title
    published = (_parse_date(meta(page, "article:published_time"))
                 or _parse_date((_TIME_TAG.search(page) or [None, None])[1])
                 or _parse_date((_JSONLD_DATE.search(page) or [None, None])[1]))
    image = meta(page, "og:image")
    return {"title": title[:300], "text": _TAGS.sub(" ", text).strip()[:1500], "timestamp": published,
            "image_url": clean_url(urljoin(url, image)) if image else None}


async def _robots(client: httpx.AsyncClient, url: str) -> RobotFileParser:
    p = urlparse(url)
    rp = RobotFileParser()
    try:
        r = await client.get(f"{p.scheme}://{p.netloc}/robots.txt", follow_redirects=True)
        rp.parse(r.text.splitlines() if r.status_code == 200 else [])
    except httpx.HTTPError:
        rp.parse([])  # robots.txt unreachable: treat as no rules, like browsers and crawlers do
    return rp


async def fetch_scraped(client: httpx.AsyncClient, source: dict) -> list[dict]:
    rp = await _robots(client, source["list_url"])
    if not rp.can_fetch(config.USER_AGENT, source["list_url"]):
        raise PermissionError("robots.txt does not allow reading this page")
    resp = await client.get(source["list_url"], follow_redirects=True)
    resp.raise_for_status()
    links = article_links(resp.text, str(resp.url), source["pattern"])
    known = await asyncio.to_thread(db.existing_ids, [make_id(u, source["name"], "") for u in links])
    new = [u for u in links if make_id(u, source["name"], "") not in known and rp.can_fetch(config.USER_AGENT, u)]
    items = []
    for url in new[: source.get("max", 8)]:
        await asyncio.sleep(config.SCRAPE_DELAY_S)
        try:
            page = await client.get(url, follow_redirects=True)
            page.raise_for_status()
        except httpx.HTTPError:
            continue  # one broken article does not stop the source
        art = parse_article(page.text, url, source.get("strip_title", ""))
        if not art:
            continue
        items.append({"source_name": source["name"], "source_type": source["type"], "reliability": source["reliability"],
                      "title": art["title"], "text": art["text"], "url": url,
                      "timestamp": art["timestamp"] or utcnow(), "image_url": art["image_url"]})
    return items


def describe() -> list[dict]:
    """The configured sites, for documentation and the status page."""
    return [{k: s[k] for k in ("name", "list_url", "type", "reliability")} for s in config.SCRAPE_SOURCES]

