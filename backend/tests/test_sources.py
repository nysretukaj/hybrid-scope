"""New sources: ransomware.live claims, the polite web scraper, RSS posts without titles. No network."""
import asyncio
from datetime import timedelta

import httpx
import pytest

from app import config

ARTICLE = """<html><head><title>Ignored</title>
<meta property="og:title" content="KUJDES NGA MASHTRIMET ME VIBER! | KOS-CERT">
<meta content="Sulmuesit po marrin llogaritë Viber të qytetarëve në Kosovë." property="og:description">
<meta property="og:image" content="/uploads/posts/viber.png">
<meta property="article:published_time" content="2026-11-19T06:51:00+00:00">
</head><body>...</body></html>"""
LIST = """<a href="/lajme-njoftime/kujdes-nga-mashtrimet-me-viber">1</a>
<a href="https://kos-cert.org/lajme-njoftime/paralajmerim-per-phishing-ne-banka">2</a>
<a href="/lajme-njoftime/kujdes-nga-mashtrimet-me-viber">dup</a>
<a href="/kontakt">contact</a><a href="https://other.org/lajme-njoftime/abcdefghijk">other site</a>"""


@pytest.fixture()
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "SCRAPE_DELAY_S", 0)
    from app import db

    db.init_db()
    return db


# --- ransomware.live ------------------------------------------------------------------
def test_ransomware_claims_become_alleged_cyber_reports():
    from app.analyzer import analyze_local
    from app.ingest.live import ransomware_items
    from app.normalize import iso, utcnow

    now = utcnow()
    victims = [
        {"group": "akira", "victim": "ex*****le.com", "country": "DE", "activity": "Manufacturing",
         "description": "Car parts maker", "discovered": iso(now - timedelta(hours=5)),
         "url": "https://www.ransomware.live/id/abc", "claim_url": "http://xyz.onion/leak"},
        {"group": "old", "victim": "x", "country": "US", "discovered": iso(now - timedelta(days=9))},
        {"group": "nocountry", "victim": "y", "country": "", "activity": "Not Found", "discovered": iso(now),
         "url": "http://evil.onion/x"},
    ]
    items = ransomware_items(victims, now, days=3)
    assert len(items) == 2  # the 9-day-old claim is skipped
    first = items[0]
    assert first["url"] == "https://www.ransomware.live/id/abc" and "onion" not in first["text"]
    assert "Germany" in first["title"] and "not been confirmed" in first["text"]
    assert items[1]["url"] is None  # only ransomware.live pages are linked, never leak sites
    a = analyze_local(first["title"], first["text"])
    assert a["category"] == "cyber" and a["subcategory"] == "ransomware"
    assert a["claim"] == "alleged" and a["location"]["country"] == "Germany"


# --- scraper ---------------------------------------------------------------------------
def test_meta_tags_and_article_links():
    from app.ingest.scrape import article_links, meta, parse_article

    assert meta(ARTICLE, "og:description").startswith("Sulmuesit")  # content before property
    links = article_links(LIST, "https://kos-cert.org/lajme-njoftime", r"^/lajme-njoftime/[a-z0-9\-]{8,}/?$")
    assert links == ["https://kos-cert.org/lajme-njoftime/kujdes-nga-mashtrimet-me-viber",
                     "https://kos-cert.org/lajme-njoftime/paralajmerim-per-phishing-ne-banka"]
    art = parse_article(ARTICLE, links[0], " | KOS-CERT")
    assert art["title"] == "KUJDES NGA MASHTRIMET ME VIBER!"
    assert art["image_url"] == "https://kos-cert.org/uploads/posts/viber.png"
    assert art["timestamp"].isoformat() == "2026-11-19T06:51:00+00:00"
    assert parse_article("<html><body>no title</body></html>", links[0]) is None


def _client(robots: str, pages: dict, hits: list):
    def handler(request: httpx.Request):
        hits.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=robots)
        body = pages.get(request.url.path)
        return httpx.Response(200, text=body) if body is not None else httpx.Response(404)
    return httpx.AsyncClient(transport=httpx.MockTransport(handler), base_url="https://kos-cert.org")


SOURCE = {"name": "KOS-CERT", "list_url": "https://kos-cert.org/lajme-njoftime", "pattern": r"^/lajme-njoftime/[a-z0-9\-]{8,}/?$",
          "type": "advisory (sq)", "reliability": 0.9, "max": 8, "strip_title": " | KOS-CERT"}


def test_scraper_reads_new_articles_only(fresh):
    from app.ingest.scrape import fetch_scraped
    from app.normalize import build_signal, utcnow

    pages = {"/lajme-njoftime": LIST, "/lajme-njoftime/kujdes-nga-mashtrimet-me-viber": ARTICLE,
             "/lajme-njoftime/paralajmerim-per-phishing-ne-banka": ARTICLE.replace("VIBER", "PHISHING")}
    known = build_signal(source_name="KOS-CERT", source_type="advisory", reliability=0.9, title="old", text="old",
                         url="https://kos-cert.org/lajme-njoftime/kujdes-nga-mashtrimet-me-viber", timestamp=utcnow(),
                         analysis={"category": "cyber"})
    fresh.insert_signals([known])
    hits = []

    async def run():
        async with _client("User-agent: *\nDisallow: /admin", pages, hits) as c:
            return await fetch_scraped(c, SOURCE)

    items = asyncio.run(run())
    assert [i["title"] for i in items] == ["KUJDES NGA MASHTRIMET ME PHISHING!"]
    assert "/lajme-njoftime/kujdes-nga-mashtrimet-me-viber" not in hits  # already stored: not fetched again


def test_scraper_respects_robots_txt(fresh):
    from app.ingest.scrape import fetch_scraped

    hits = []

    async def run():
        async with _client("User-agent: *\nDisallow: /", {"/lajme-njoftime": LIST}, hits) as c:
            return await fetch_scraped(c, SOURCE)

    with pytest.raises(PermissionError):
        asyncio.run(run())
    assert hits == ["/robots.txt"]  # nothing else was requested


def test_scraper_limits_articles_per_run(fresh):
    from app.ingest.scrape import fetch_scraped

    many = "".join(f'<a href="/lajme-njoftime/lajmi-numer-{i:03d}-test">x</a>' for i in range(20))
    pages = {"/lajme-njoftime": many, **{f"/lajme-njoftime/lajmi-numer-{i:03d}-test": ARTICLE for i in range(20)}}
    hits = []

    async def run():
        async with _client("", pages, hits) as c:
            return await fetch_scraped(c, {**SOURCE, "max": 3})

    assert len(asyncio.run(run())) == 3
    assert sum(1 for h in hits if h.startswith("/lajme-njoftime/")) == 3


# --- RSS posts without a title (social media) ----------------------------------------------
def test_rss_post_without_title_gets_one_from_its_text():
    from app.ingest.live import fetch_rss

    feed = """<?xml version="1.0"?><rss version="2.0"><channel><title>t</title>
    <item><link>https://mastodon.social/@a/1</link><description>&lt;p&gt;Bot accounts are spreading a fake story about
    the power grid in Pristina tonight, please check sources before sharing&lt;/p&gt;</description></item></channel></rss>"""

    async def run():
        transport = httpx.MockTransport(lambda r: httpx.Response(200, text=feed))
        async with httpx.AsyncClient(transport=transport) as c:
            return await fetch_rss(c, {"name": "Mastodon", "url": "https://mastodon.social/tags/x.rss", "type": "social", "reliability": 0.4})

    items = asyncio.run(run())
    assert len(items) == 1 and items[0]["title"].startswith("Bot accounts are spreading")
    assert items[0]["image_url"] is None


def test_labour_exploitation_is_not_a_cyber_attack():
    from app.analyzer import analyze_local

    assert analyze_local("", "27 arrests in an action week against labour exploitation in Austria.")["category"] != "cyber"
    assert analyze_local("", "Attackers exploited a zero-day in VPN gateways in Germany.")["category"] == "cyber"
    assert analyze_local("", "A new exploit for the flaw was published.")["category"] == "cyber"


def test_fact_checker_articles_with_indicators_are_disinformation():
    from app.analyzer import analyze_local
    from app.ingest.live import apply_fact_check_hint

    item = {"source_type": "fact-check (sq)", "title": "Edi Rama nuk ka thënë se shqiptarët do të zëvendësohen",
            "text": "Deklarata që qarkullon në rrjete është e sajuar."}
    a = analyze_local(item["title"], item["text"])
    assert apply_fact_check_hint(item, a) and a["category"] == "disinformation" and a["severity"] >= 0.3
    assert "verifikues faktesh" in a["i18n"]["sq"]["rationale"]
    explainer = {"source_type": "fact-check (sq)", "title": "Udhëkryqi i reformës së pensioneve", "text": "Çfarë ndryshon."}
    b = analyze_local(explainer["title"], explainer["text"])
    assert not apply_fact_check_hint(explainer, b) and b["category"] == "other"
    news = {"source_type": "news (sq)", **{k: item[k] for k in ("title", "text")}}
    assert not apply_fact_check_hint(news, analyze_local(news["title"], news["text"]))


def test_every_configured_source_is_well_formed():
    import re

    names = [f["name"] for f in config.RSS_FEEDS] + [s["name"] for s in config.SCRAPE_SOURCES]
    assert len(names) == len(set(names))
    for f in config.RSS_FEEDS:
        assert f["url"].startswith("https://") and 0 < f["reliability"] <= 1
    for s in config.SCRAPE_SOURCES:
        re.compile(s["pattern"])
        assert s["list_url"].startswith("https://") and s["max"] <= 10
