import pytest
from fastapi.testclient import TestClient

from app import config


@pytest.fixture()
def public_client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "PUBLIC_MODE", True)
    monkeypatch.setattr(config, "ADMIN_TOKEN", "s3cret-token")
    monkeypatch.setattr(config, "ANALYZE_PER_MINUTE", 2)
    monkeypatch.setattr(config, "LIVE_INGEST_INTERVAL_MIN", 0)
    from app import main

    main._ANALYZE_HITS.clear()
    with TestClient(main.app) as client:
        yield client


def test_state_changing_endpoints_need_admin_token(public_client):
    assert public_client.get("/api/health").json()["public_mode"] is True
    assert public_client.post("/api/demo/reset").status_code == 403
    assert public_client.post("/api/demo/reset", headers={"X-Admin-Token": "wrong"}).status_code == 403
    assert public_client.post("/api/demo/reset", headers={"X-Admin-Token": "s3cret-token"}).status_code == 200

    alert_id = public_client.get("/api/alerts").json()["alerts"][0]["id"]
    r = public_client.post(f"/api/alerts/{alert_id}/feedback", json={"verdict": "confirmed"})
    assert r.status_code == 403
    assert public_client.post("/api/demo/snapshot").status_code == 403


def test_read_only_features_stay_open(public_client):
    alert_id = public_client.get("/api/alerts").json()["alerts"][0]["id"]
    assert public_client.get(f"/api/alerts/{alert_id}/brief").status_code == 200
    assert public_client.get(f"/api/alerts/{alert_id}/replay").status_code == 200
    assert public_client.get("/api/graph").status_code == 200


def test_analyze_is_rate_limited_per_client(public_client):
    body = {"text": "Ransomware hit a hospital in Berlin."}
    assert public_client.post("/api/analyze", json=body).status_code == 200
    assert public_client.post("/api/analyze", json={"text": "Phishing wave in Pristina."}).status_code == 200
    assert public_client.post("/api/analyze", json={"text": "DDoS on a ministry in Tirana."}).status_code == 429
    # the presenter is never limited
    r = public_client.post("/api/analyze", json={"text": "Drones over a power plant in Wien."},
                           headers={"X-Admin-Token": "s3cret-token"})
    assert r.status_code == 200
