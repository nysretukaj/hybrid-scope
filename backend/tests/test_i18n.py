import pytest
from fastapi.testclient import TestClient

from app import config


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "LIVE_INGEST_INTERVAL_MIN", 0)
    monkeypatch.setattr(config, "PUBLIC_MODE", False)
    from app import main

    with TestClient(main.app) as c:
        yield c


def _kosovo_id(client):
    alerts = client.get("/api/alerts", params={"source": "synthetic"}).json()["alerts"]
    return next(a["id"] for a in alerts if a["zone"] == "Kosovo")


@pytest.mark.parametrize("lang,title,signal_word,bluf_word", [
    ("en", "Hybrid threat pattern - Kosovo", "CERT confirms", "almost certain"),
    ("sq", "Model kërcënimi hibrid - Kosovë", "CERT konfirmon", "pothuajse e sigurt"),
    ("de", "Hybrides Bedrohungsmuster - Kosovo", "CERT bestätigt", "nahezu sicher"),
])
def test_alert_and_brief_follow_the_language(client, lang, title, signal_word, bluf_word):
    aid = _kosovo_id(client)
    alert = client.get(f"/api/alerts/{aid}", params={"lang": lang}).json()
    assert alert["title"] == title
    assert alert["headline"].startswith(signal_word)
    assert all(b["label"] and b["explanation"] for b in alert["breakdown"])
    brief = client.get(f"/api/alerts/{aid}/brief", params={"lang": lang}).json()
    assert bluf_word in brief["bluf"]


def test_albanian_has_no_english_template_text(client):
    aid = _kosovo_id(client)
    a = client.get(f"/api/alerts/{aid}", params={"lang": "sq"}).json()
    b = client.get(f"/api/alerts/{aid}/brief", params={"lang": "sq"}).json()
    text = " ".join([a["summary"], *[x["explanation"] for x in a["breakdown"]],
                     *[r for link in a["links"] for r in link["reasons"]],
                     b["bluf"], *b["key_judgments"], *b["actions"], *b["indicators"], b["method"], b["classification"]])
    for english in ("signal(s)", "Sequence", "Linked by", "Peak severity", "Shared ", "within", "It is ",
                    "national grid operator", "grid collapse", "UNCLASSIFIED", "Convene"):
        assert english not in text, english
    assert all(s["rationale"] and "Local NLP" not in s["rationale"] for s in a["signals"])


def test_zone_filter_options_are_translated(client):
    zones = client.get("/api/alerts", params={"lang": "de"}).json()["zones"]
    assert {"value": "Germany", "label": "Deutschland"} in zones
    assert {"value": "Baltic Sea Region", "label": "Ostseeraum"} in zones


def test_local_nlp_rationale_in_three_languages():
    from app.analyzer.local import analyze_local

    r = analyze_local("", "Ransomware encrypted systems at a hospital in Berlin.")
    assert r["rationale"].startswith("Local NLP")
    assert r["i18n"]["sq"]["rationale"].startswith("NLP lokal")
    assert r["i18n"]["de"]["rationale"].startswith("Lokales NLP")


def test_notification_message_in_albanian(client):
    from app.notify import format_message

    aid = _kosovo_id(client)
    alert = client.get(f"/api/alerts/{aid}", params={"lang": "sq"}).json()
    msg = format_message(alert, "sq")
    assert "KRITIK" in msg and "HIBRID" in msg and "Domenet:" in msg and "STËRVITJE" in msg
