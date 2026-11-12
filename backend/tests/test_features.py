import pytest

from app import config


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    from app import db
    from app.ingest.seed import load_seed

    db.init_db()
    load_seed()
    return db


def _alerts(db):
    from app.correlation import build_alerts
    from app.feedback import apply_feedback
    from app.normalize import utcnow

    return build_alerts(apply_feedback(db.fetch_signals()), utcnow())


def _kosovo(db):
    return next(a for a in _alerts(db) if a["zone"] == "Kosovo")


# --- multilingual analyzer ---------------------------------------------------
def test_albanian_text_is_classified_and_located():
    from app.analyzer.local import analyze_local

    r = analyze_local("", "Sulm kibernetik ndaj operatorit të rrjetit elektrik në Prishtinë; hakerët shkaktuan ndërprerje të rrymës.")
    assert r["category"] in ("cyber", "infrastructure")
    assert r["location"]["zone"] == "Kosovo"

    r = analyze_local("", "Lajme të rreme dhe dezinformata për zgjedhjet po përhapen në Shqipëri.")
    assert r["category"] == "disinformation"
    assert r["location"]["zone"] == "Albania"


def test_german_text_is_classified_and_located():
    from app.analyzer.local import analyze_local

    r = analyze_local("", "Cyberangriff auf Netzbetreiber in Deutschland: Angreifer nutzten eine Sicherheitslücke aus.")
    assert r["category"] == "cyber"
    assert r["location"]["zone"] == "Germany"

    r = analyze_local("", "Drohnen über dem Kraftwerk bei Wien gesichtet, Polizei ermittelt wegen Sabotage.")
    assert r["category"] == "physical"
    assert r["location"]["zone"] == "Austria"


# --- TTP mapping, brief, replay ------------------------------------------------
def test_kosovo_ttps_cover_attack_ics_and_disarm(seeded):
    ids = {t["id"] for t in _kosovo(seeded)["ttps"]}
    assert {"T1566", "T1498", "T1650"} <= ids          # ATT&CK enterprise
    assert {"T0883", "T0827"} <= ids                   # ATT&CK for ICS
    assert {"T0049", "T0087", "T0057"} <= ids          # DISARM


def test_storm_outage_does_not_map_to_ics_impact(seeded):
    japan = next(a for a in _alerts(seeded) if a["zone"] == "Japan")
    assert japan["ttps"] == []


def test_brief_has_analyst_structure(seeded):
    from app.brief import build_brief

    b = build_brief(_kosovo(seeded))
    assert "hybrid campaign" in b["bluf"] and b["likelihood"] == "almost certain"
    assert "EXERCISE" in b["classification"]
    assert len(b["key_judgments"]) >= 3 and len(b["actions"]) == 5 and len(b["indicators"]) == 4
    assert len(b["sources"]) == 14


def test_replay_flags_hybrid_before_first_outage(seeded):
    from app.correlation import replay

    r = replay(_kosovo(seeded))
    assert len(r["frames"]) == 14
    m = r["milestones"]
    assert m["impact"]["signal_id"] == "seed-k07"
    assert m["first_hybrid"]["lead_hours"] >= 24
    assert r["frames"][-1]["score"] >= 75


# --- human-in-the-loop -------------------------------------------------------------
def test_feedback_updates_source_reliability(seeded):
    from app.normalize import iso, utcnow

    k = _kosovo(seeded)
    seeded.set_feedback(k["id"], "confirmed", "verified with CERT", k["sources"], iso(utcnow()))
    k2 = _kosovo(seeded)
    votv = next(s for s in k2["signals"] if s["source_name"] == "Telegram: Voice of the Valley")
    assert votv["source_reliability_prior"] == 0.25
    assert votv["source_reliability"] == 0.4  # (0.25*4 + 1) / 5


def test_graph_links_alerts_through_shared_entities(seeded):
    from app.graph import build_graph

    g = build_graph(_alerts(seeded))
    labels = {n["label"] for n in g["nodes"] if n["kind"] == "entity"}
    assert {"GreyMist", "Telegram"} <= labels
    telegram = next(n for n in g["nodes"] if n["kind"] == "entity" and n["label"] == "Telegram")
    assert telegram["alerts"] >= 2  # bridges the Kosovo and Baltic campaigns
