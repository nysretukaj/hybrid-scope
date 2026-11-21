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


# --- Telegram, state media, Serbian sources ----------------------------------------------
TG_PAGE = """<div class="tgme_channel_info">RT Balkan</div>
<div class="tgme_widget_message_wrap"><div class="tgme_widget_message js-widget_message" data-post="rtbalkan/101">
<a class="tgme_widget_message_photo_wrap" style="width:800px;background-image:url('https://cdn4.telesco.pe/file/abc.jpg')"></a>
<div class="tgme_widget_message_text js-message_text" dir="auto">Albanski <b>teroristi</b> prete Srbima na severu Kosova,<br/>tvrdi izvor.</div>
<time datetime="2026-11-21T10:22:29+00:00" class="time">10:22</time></div></div>
<div class="tgme_widget_message js-widget_message" data-post="rtbalkan/102"><div class="tgme_widget_message_text" dir="auto">ok</div></div>"""
TG_SOURCE = {"name": "RT Balkan (Telegram)", "channel": "rtbalkan", "type": "state-media (sr)", "reliability": 0.2, "lang": "sr"}


def test_telegram_preview_is_parsed():
    from app.ingest.telegram import parse_channel

    items = parse_channel(TG_PAGE, TG_SOURCE)
    assert len(items) == 1  # the 2-letter post is skipped
    post = items[0]
    assert post["url"] == "https://t.me/rtbalkan/101" and post["image_url"] == "https://cdn4.telesco.pe/file/abc.jpg"
    assert post["text"].startswith("Albanski teroristi prete Srbima") and post["timestamp"].year == 2026


def test_telegram_reader_respects_robots(fresh):
    from app.ingest.telegram import fetch_telegram

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /s/")
        return httpx.Response(200, text=TG_PAGE)

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            return await fetch_telegram(c, TG_SOURCE)

    with pytest.raises(PermissionError):
        asyncio.run(run())


def test_foreign_state_media_claims_are_narratives_not_events():
    from app.ingest.policy import apply_policies

    item = {"source_type": "state-media (sr)", "title": "Drone attack on a power plant", "text": "Drones attacked a power plant."}
    a = {"category": "physical", "tags": ["infrastructure"], "severity": 0.8, "confidence": 0.8, "claim": "confirmed",
         "cause": "deliberate", "rationale": "LLM says it happened", "i18n": {}}
    apply_policies(item, a)
    assert a["category"] == "disinformation" and a["subcategory"] == "propaganda"
    assert a["tags"][0] == "physical" and a["claim"] == "alleged" and a["cause"] == "unknown"
    assert a["rationale"].startswith("Published by foreign state-controlled media")
    apply_policies(item, a)  # idempotent: the note is not added twice
    assert a["rationale"].count("Published by foreign state-controlled media") == 1
    other = {"category": "other", "tags": [], "severity": 0.1, "confidence": 0.5, "rationale": "", "i18n": {}}
    assert apply_policies(item, other)["category"] == "other"  # weather news stays weather news


def test_llm_relabel_cannot_undo_the_state_media_rule(fresh):
    from app.normalize import build_signal, utcnow

    sig = build_signal(source_name="Sputnik Srbija", source_type="state-media (sr)", reliability=0.2,
                       title="Napad na Srbe", text="Tekst.", url="https://e.org/s1", timestamp=utcnow(),
                       analysis={"category": "other", "analyzer": "local-nlp"})
    fresh.insert_signals([sig])
    llm = {"category": "physical", "tags": [], "severity": 0.8, "confidence": 0.9, "analyzer": "ollama:gemma3:4b",
           "rationale": "An attack took place.", "entities": {}, "cause": "deliberate", "claim": "confirmed"}
    assert fresh.update_analysis(sig["id"], llm)
    stored = fresh.fetch_signal(sig["id"])
    assert stored["category"] == "disinformation" and stored["claim"] == "alleged" and stored["tags"] == ["physical"]


def test_serbian_reports_go_to_the_local_ai(fresh, monkeypatch):
    from app import main
    from app.ml import jobs, ollama
    from app.normalize import build_signal, utcnow

    sr = build_signal(source_name="N1 Srbija", source_type="news (sr)", reliability=0.7, title="Vest", text="Tekst.",
                      url="https://e.org/sr", timestamp=utcnow(), analysis={"category": "other"})
    sq = build_signal(source_name="Koha", source_type="news (sq)", reliability=0.7, title="Lajm", text="Tekst.",
                      url="https://e.org/sq", timestamp=utcnow(), analysis={"category": "other"})
    about_kosovo = build_signal(source_name="Danas", source_type="news (sr)", reliability=0.7, title="Napetost u Kosovskoj Mitrovici",
                                text="Tekst.", url="https://e.org/sr2", timestamp=utcnow() - timedelta(hours=3),
                                analysis={"category": "other"})
    sputnik = build_signal(source_name="Sputnik Srbija", source_type="state-media (sr)", reliability=0.2, title="Vest",
                           text="Tekst.", url="https://e.org/sr3", timestamp=utcnow() - timedelta(hours=1),
                           analysis={"category": "other"})
    fresh.insert_signals([sr, sq, about_kosovo, sputnik])
    # Kosovo first, then state media, then the rest; Albanian sources are not queued
    assert main.serbian_ids([sr["id"], sq["id"], about_kosovo["id"], sputnik["id"]]) == [about_kosovo["id"], sputnik["id"], sr["id"]]
    queued = []
    monkeypatch.setattr(ollama, "chat_model", lambda: "gemma3:4b")
    monkeypatch.setattr(jobs, "start_label", lambda ids: queued.extend(ids) or True)
    assert main.start_serbian_local_ai([sr["id"]]) == 1 and queued == [sr["id"]]
    monkeypatch.setattr(ollama, "chat_model", lambda: None)
    assert main.start_serbian_local_ai([sr["id"]]) == 0  # without Ollama nothing is queued


def test_every_configured_source_is_well_formed():
    import re

    names = ([f["name"] for f in config.RSS_FEEDS] + [s["name"] for s in config.SCRAPE_SOURCES]
             + [t["name"] for t in config.TELEGRAM_CHANNELS])
    assert len(names) == len(set(names))
    from app.ingest.policy import role_of

    # foreign state media are always low reliability and handled as narratives
    for s in [*config.RSS_FEEDS, *config.TELEGRAM_CHANNELS]:
        if role_of(s["type"]) == "state-media":
            assert s["reliability"] <= 0.3
    for f in config.RSS_FEEDS:
        assert f["url"].startswith("https://") and 0 < f["reliability"] <= 1
    for s in config.SCRAPE_SOURCES:
        re.compile(s["pattern"])
        assert s["list_url"].startswith("https://") and s["max"] <= 10
