import pytest

from app import config


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    from app import db

    db.init_db()
    return db


def test_local_analyzer_cyber_with_cve_and_location():
    from app.analyzer.local import analyze_local

    r = analyze_local(
        "Ransomware hits hospital",
        "A ransomware attack encrypted systems at a hospital in Berlin; attackers exploited CVE-2024-12345 in a VPN appliance.",
    )
    assert r["category"] == "cyber"
    assert "CVE-2024-12345" in r["entities"]["cves"]
    assert "VPN" in r["entities"]["technologies"]
    assert r["location"]["zone"] == "Germany"


def test_local_analyzer_disinformation_and_hashtags():
    from app.analyzer.local import analyze_local

    r = analyze_local("", "A bot network spreads fake news and a deepfake video about the election in Chisinau #StolenVote")
    assert r["category"] == "disinformation"
    assert r["location"]["zone"] == "Moldova"
    assert "#StolenVote" in r["entities"]["narratives"]


def test_local_analyzer_weather_outage_is_low_severity():
    from app.analyzer.local import analyze_local

    r = analyze_local("", "A storm caused power outages in Tokyo.")
    assert r["category"] == "infrastructure"
    assert r["severity"] < 0.3


def test_irrelevant_text_is_other():
    from app.analyzer.local import analyze_local

    assert analyze_local("", "The football club announced a new coach in Madrid.")["category"] == "other"


def test_seed_scenario_produces_hybrid_alerts(tmp_db):
    from app.correlation import build_alerts
    from app.ingest.seed import load_seed
    from app.normalize import utcnow

    assert load_seed() >= 30
    alerts = build_alerts(tmp_db.fetch_signals(), utcnow())

    top = alerts[0]
    assert top["is_hybrid"] and top["level"] == "CRITICAL"

    kosovo = next(a for a in alerts if a["zone"] == "Kosovo")
    assert set(kosovo["categories"]) == {"disinformation", "cyber", "infrastructure", "physical"}
    assert any(e["name"] == "GreyMist" for e in kosovo["shared_entities"])
    assert kosovo["sequence"][0]["category"] == "disinformation"

    baltic = next(a for a in alerts if a["zone"] == "Baltic Sea Region")
    assert baltic["is_hybrid"] and baltic["score"] >= 75

    brazil = next(a for a in alerts if a["zone"] == "Brazil")
    assert not brazil["is_hybrid"] and brazil["score"] < kosovo["score"]

    tokyo = next(a for a in alerts if a["zone"] == "Japan")
    assert tokyo["level"] == "LOW"


def test_breakdown_sums_to_score(tmp_db):
    from app.correlation import build_alerts
    from app.ingest.seed import load_seed
    from app.normalize import utcnow

    load_seed()
    for a in build_alerts(tmp_db.fetch_signals(), utcnow()):
        assert abs(sum(c["points"] for c in a["breakdown"]) - a["score"]) < 0.6
