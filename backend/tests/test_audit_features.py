"""Features added after the feature audit: political/security taxonomy, subcategories, cause and claim,
verification status, manual correction, duplicates, bands, assessment, time filter, statistics, density map."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from app import config
from app.analyzer import analyze_local
from app.assess import affected_count, mark_duplicates, signal_view
from app.normalize import iso, utcnow


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "PUBLIC_MODE", False)
    monkeypatch.setattr(config, "LIVE_INGEST_INTERVAL_MIN", 0)
    from app import main

    with TestClient(main.app) as c:
        yield c


# --- taxonomy -----------------------------------------------------------------------
def test_political_interference_is_its_own_category():
    r = analyze_local("Foreign interference", "Officials warn of foreign interference and vote buying ahead of the "
                                              "election in Moldova, financed through covert funding.")
    assert r["category"] == "political"
    assert r["subcategory"] in ("election_interference", "foreign_interference")


def test_ordinary_politics_is_not_a_threat():
    r = analyze_local("Parliament debate", "The opposition criticised the budget during a heated parliament debate in Tirana.")
    assert r["category"] == "other"


def test_security_category_covers_terrorism_and_organised_crime():
    terror = analyze_local("", "Police foiled a terrorist plot against a train station in Vienna.")
    crime = analyze_local("", "An organised crime network smuggling migrants across the border was dismantled in Serbia.")
    assert terror["category"] == crime["category"] == "physical"
    assert terror["subcategory"] == "terrorism"
    assert crime["subcategory"] in ("organized_crime", "border")


def test_english_espionage_is_cyber():
    r = analyze_local("", "A cyber espionage campaign targeted ministries in Warsaw.")
    assert r["category"] == "cyber" and r["subcategory"] == "espionage"


# --- cause and claim --------------------------------------------------------------
def test_storm_outage_is_natural_not_an_attack():
    r = analyze_local("", "A storm caused a power outage in the suburbs of Tokyo; the grid operator restored electricity.")
    assert r["category"] == "infrastructure" and r["cause"] == "natural"


def test_sabotage_is_deliberate_and_unknown_by_default():
    assert analyze_local("", "Sabotage at a substation near Pristina cut power.")["cause"] == "deliberate"
    assert analyze_local("", "A blackout hit Riga on Monday evening.")["cause"] == "unknown"


def test_misinformation_is_not_called_deliberate():
    r = analyze_local("", "Misinformation and rumours about fuel shortages spread in Belgrade; officials say it is untrue.")
    assert r["category"] == "disinformation" and r["cause"] == "accidental"


def test_claims_and_allegations_are_distinguished():
    assert analyze_local("", "The ministry confirmed a ransomware attack in Berlin.")["claim"] == "confirmed"
    assert analyze_local("", "Hackers allegedly breached a bank in Rome.")["claim"] == "alleged"


def test_affected_people_are_extracted():
    assert affected_count("The outage left 200,000 households without power.") == 200_000
    assert affected_count("About 1.5 million people were affected.") == 1_500_000
    assert affected_count("Nothing to count here.") is None


# --- duplicates, bands, precision ----------------------------------------------------
def _sig(i, title, source, hours_ago=1, **kw):
    now = utcnow()
    return {"id": f"s{i}", "title": title, "text": title, "source_name": source, "timestamp": iso(now - timedelta(hours=hours_ago)),
            "ingested_at": iso(now), "category": "cyber", "severity": 0.8, "confidence": 0.4, "lat": 42.6629, "lon": 21.1655,
            "source_reliability": 0.8, **kw}


def test_syndicated_copies_are_marked_as_duplicates():
    sigs = [_sig(1, "Ransomware attack disrupts hospital network in Pristina", "a.com", 3),
            _sig(2, "Ransomware attack disrupts hospital network in Pristina", "b.com", 2),
            _sig(3, "Phishing wave targets ministry staff in Pristina", "c.com", 1)]
    assert mark_duplicates(sigs) == 1
    assert sigs[1]["duplicate_of"] == "s1" and sigs[2]["duplicate_of"] is None


def test_severity_and_confidence_are_separate_and_precision_known():
    v = signal_view(_sig(1, "Ransomware attack in Pristina", "a.com"), utcnow())
    assert v["severity_level"] == "CRITICAL" and v["confidence_level"] == "low" and v["uncertain"] is True
    assert v["geo_precision"] == "city"
    country = signal_view(_sig(2, "x", "a.com", lat=42.60, lon=20.90), utcnow())
    assert country["geo_precision"] == "country"


# --- API ------------------------------------------------------------------------------
def test_alerts_carry_assessment_and_verification(client):
    a = client.get("/api/alerts").json()["alerts"][0]
    # no analyst yet: the status comes from the evidence
    assert a["verification_source"] == "auto"
    assert a["verification"] == a["assessment"]["auto_verification"]["status"]
    assert a["verification"] in ("unverified", "investigating", "partial", "confirmed", "disproved")
    for k in ("severity_level", "confidence_level", "impact", "urgency", "scope", "evidence_quality"):
        assert k in a["assessment"]
    assert a["geo_precision"] in ("city", "country")


def _ev(name, rel, stype="news", title="Explosion at substation in Pristina", claim="reported", cat="infrastructure"):
    from app.normalize import utcnow

    return {"id": name, "source_name": name, "source_reliability": rel, "source_type": stype, "title": title,
            "text": title, "claim": claim, "category": cat, "timestamp": utcnow().isoformat()}


def test_automatic_verification_from_evidence():
    from app.assess import auto_verification

    three = [_ev("a.com", 0.8), _ev("b.com", 0.85), _ev("c.com", 0.9)]
    assert auto_verification(three)["status"] == "confirmed"
    official = [_ev("Policia e Kosovës", 0.9, "official (sq)"), _ev("b.com", 0.8)]
    res = auto_verification(official)
    assert res["status"] == "confirmed" and res["confidence"] >= 0.85 and res["reasons"][0]["k"] == "official"
    assert auto_verification([_ev("a.com", 0.8), _ev("b.com", 0.8)])["status"] == "partial"
    assert auto_verification([_ev("a.com", 0.8)])["status"] == "investigating"
    assert auto_verification([_ev("blog", 0.4), _ev("Mastodon", 0.4, "social")])["status"] == "unverified"
    state = auto_verification([_ev("Sputnik Srbija", 0.9, "state-media (sr)")])  # even if misconfigured as reliable
    assert state["status"] == "unverified" and {"k": "state_only"} in state["reasons"]
    denied = [_ev("a.com", 0.8), _ev("Policy statement", 0.85, "news", title="Police denied reports of an explosion")]
    assert auto_verification(denied)["status"] == "disproved"
    # a fact-checker calling a claim false CONFIRMS a disinformation campaign, it does not disprove it
    disinfo = [_ev("Hibrid.info", 0.85, "fact-check (sq)", title="Hoax about power cuts debunked", cat="disinformation"),
               _ev("x.com", 0.8, cat="disinformation")]
    assert auto_verification(disinfo)["status"] == "partial"
    # copies of one story are one source
    copies = [{**_ev("a.com", 0.8), "id": "1"}, {**_ev("b.com", 0.8), "id": "2", "duplicate_of": "1"},
              {**_ev("c.com", 0.8), "id": "3", "duplicate_of": "1"}]
    assert auto_verification(copies)["status"] == "investigating"


def test_analyst_overrides_the_automatic_status(client):
    a = client.get("/api/alerts").json()["alerts"][0]
    client.post(f"/api/alerts/{a['id']}/feedback", json={"verdict": "disproved"})
    b = client.get(f"/api/alerts/{a['id']}").json()
    assert b["verification"] == "disproved" and b["verification_source"] == "analyst"
    client.post(f"/api/alerts/{a['id']}/feedback", json={"verdict": "unverified"})  # clears the override
    c = client.get(f"/api/alerts/{a['id']}").json()
    assert c["verification_source"] == "auto" and c["verification"] == a["verification"]


def test_verification_status_workflow(client):
    alert_id = client.get("/api/alerts").json()["alerts"][0]["id"]
    for status in ("investigating", "partial", "confirmed", "disproved"):
        assert client.post(f"/api/alerts/{alert_id}/feedback", json={"verdict": status}).json()["verification"] == status
        assert client.get(f"/api/alerts/{alert_id}").json()["verification"] == status
    ids = [a["id"] for a in client.get("/api/alerts", params={"hide_dismissed": True}).json()["alerts"]]
    assert alert_id not in ids
    # the old name still works
    assert client.post(f"/api/alerts/{alert_id}/feedback", json={"verdict": "false_positive"}).json()["verification"] == "disproved"
    assert client.post(f"/api/alerts/{alert_id}/feedback", json={"verdict": "unverified"}).json()["verification"] == "unverified"


def test_manual_category_correction(client):
    sig = client.get("/api/signals", params={"category": "cyber"}).json()["signals"][0]
    r = client.post(f"/api/signals/{sig['id']}/classification", json={"category": "political", "subcategory": "coercion"})
    assert r.status_code == 200 and r.json()["original_category"] == "cyber"
    again = next(s for s in client.get("/api/signals").json()["signals"] if s["id"] == sig["id"])
    assert again["category"] == "political" and again["subcategory"] == "coercion" and again["analyzer"] == "analyst"
    assert client.post("/api/signals/nope/classification", json={"category": "cyber"}).status_code == 404


def test_time_filter_keeps_alert_ids_stable(client):
    full = {a["id"]: a for a in client.get("/api/alerts").json()["alerts"]}
    day = client.get("/api/alerts", params={"hours": 24}).json()["alerts"]
    assert day and len(day) <= len(full)
    assert all(a["id"] in full for a in day)


def test_stats_are_computed_from_data(client):
    s = client.get("/api/stats", params={"lang": "sq"}).json()
    assert sum(s["by_category"].values()) == s["threat_relevant"]
    assert sum(s["by_verification"].values()) == s["alerts"]
    assert s["trend"] and s["source_stats"] and s["by_country"]
    assert any(c["name"] == "Kosovë" for c in s["by_country"])


def test_geo_density_points(client):
    pts = client.get("/api/geo").json()["points"]
    assert pts and all(p["count"] >= 1 and p["precision"] in ("city", "country") for p in pts)


def test_ai_summary_needs_an_llm(client):
    alert_id = client.get("/api/alerts").json()["alerts"][0]["id"]
    assert client.get(f"/api/alerts/{alert_id}/ai-summary").status_code == 400
