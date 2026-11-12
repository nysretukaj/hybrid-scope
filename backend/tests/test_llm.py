import asyncio
import json
import time

import httpx
import pytest

from app import config
from app.analyzer import llm as llm_mod

LLM_REPLY = {
    "category": "cyber",
    "secondary_categories": ["infrastructure"],
    "severity": 0.82,
    "confidence": 0.9,
    "entities": {"actors": ["GreyMist"], "orgs": ["grid operator"], "technologies": ["SCADA"], "narratives": []},
    "rationale": "Intrusion attempt against the grid operator's control systems.",
}


class FakeResponse:
    def __init__(self, status=200, data=None, headers=None):
        self.status_code = status
        self._data = data or {}
        self.headers = headers or {}

    def json(self):
        return self._data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(f"HTTP {self.status_code}", request=None, response=None)


@pytest.fixture()
def fake_llm(monkeypatch):
    monkeypatch.setattr(config, "LLM_BASE_URL", "https://llm.test/v1")
    monkeypatch.setattr(config, "LLM_API_KEY", "gsk_test")
    monkeypatch.setattr(config, "LLM_MODEL", "")
    monkeypatch.setattr(config, "LLM_MODEL_LIVE", "")
    llm_mod.STATUS.update(last_error=None, rate_limited_until=0.0, models={})
    calls = {"post": [], "status": 200}

    def fake_get(url, headers=None, timeout=None):
        return FakeResponse(data={"data": [{"id": "whisper-large-v3"}, {"id": "llama-3.1-8b-instant"},
                                           {"id": "llama-3.3-70b-versatile"}]})

    def fake_post(url, json=None, headers=None, timeout=None):
        calls["post"].append(json)
        if calls["status"] == 429:
            return FakeResponse(429, headers={"retry-after": "12"})
        return FakeResponse(data={"choices": [{"message": {"content": globals()["json"].dumps(LLM_REPLY)}}]})

    monkeypatch.setattr(llm_mod.httpx, "get", fake_get)
    monkeypatch.setattr(llm_mod.httpx, "post", fake_post)
    yield calls
    llm_mod.STATUS.update(last_error=None, rate_limited_until=0.0, models={})


def test_provider_detected_from_key_prefix():
    assert config.detect_base_url("gsk_abc") == "https://api.groq.com/openai/v1"
    assert config.detect_base_url("AIzaXYZ").startswith("https://generativelanguage.googleapis.com")
    assert config.detect_base_url("sk-other") == ""
    assert config.detect_base_url("gsk_abc", "http://localhost:11434/v1/") == "http://localhost:11434/v1"


def test_models_resolved_per_purpose(fake_llm):
    assert llm_mod.resolve_model("analyze") == "llama-3.3-70b-versatile"
    assert llm_mod.resolve_model("live") == "llama-3.1-8b-instant"


def test_llm_result_merged_with_local_baseline(fake_llm):
    from app.analyzer import analyze

    r = analyze("Grid attack", "Hackers attempted an intrusion at the grid operator in Pristina.")
    assert r["analyzer"] == "llm:llama-3.3-70b-versatile"
    assert r["category"] == "cyber" and r["tags"] == ["infrastructure"] and r["severity"] == 0.82
    assert r["location"]["zone"] == "Kosovo"            # deterministic extraction kept
    assert "GreyMist" in r["entities"]["actors"]          # LLM entities merged
    assert r["baseline"]["analyzer"] == "local-nlp"
    assert fake_llm["post"][0]["response_format"] == {"type": "json_object"}


def test_rate_limit_falls_back_to_local_and_pauses(fake_llm):
    from app.analyzer import analyze

    fake_llm["status"] = 429
    r = analyze("", "Ransomware hit a hospital in Berlin.")
    assert r["analyzer"] == "local-nlp"
    assert llm_mod.STATUS["rate_limited_until"] > time.time() + 5
    posts = len(fake_llm["post"])
    analyze("", "Another ransomware attack in Berlin.")
    assert len(fake_llm["post"]) == posts  # paused: no further calls while rate limited


def test_background_enrichment_upgrades_live_signal(fake_llm, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "LLM_RPM", 6000)
    from app import db, enrich
    from app.analyzer.local import analyze_local
    from app.normalize import build_signal, utcnow

    db.init_db()
    title, text = "Grid operator hit", "An intrusion was detected at the grid operator in Pristina."
    sig = build_signal(source_name="Koha", source_type="news (sq)", reliability=0.75, title=title, text=text,
                       url="https://example.org/a", timestamp=utcnow(), analysis=analyze_local(title, text))
    db.insert_signals([sig])

    state = asyncio.run(enrich.enrich_signals([sig["id"]]))
    assert state["done"] == 1 and state["failed"] == 0
    row = db.fetch_by_ids([sig["id"]])[0]
    assert row["analyzer"] == "llm:llama-3.1-8b-instant"
    assert row["severity"] == 0.82 and "SCADA" in row["entities"]["technologies"]
    assert row["zone"] == "Kosovo"


def test_enrichment_retries_after_rate_limit(fake_llm, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "LLM_RPM", 6000)
    from app import db, enrich
    from app.analyzer.local import analyze_local
    from app.normalize import build_signal, utcnow

    db.init_db()
    title, text = "Grid operator hit", "An intrusion was detected at the grid operator in Pristina."
    sig = build_signal(source_name="Koha", source_type="news", reliability=0.75, title=title, text=text,
                       url="https://example.org/b", timestamp=utcnow(), analysis=analyze_local(title, text))
    db.insert_signals([sig])

    # first call is rate limited (with a tiny pause), the retry succeeds
    real_post = llm_mod.httpx.post
    state = {"n": 0}

    def flaky_post(url, json=None, headers=None, timeout=None):
        state["n"] += 1
        if state["n"] == 1:
            return FakeResponse(429, headers={"retry-after": "0"})
        return real_post(url, json=json, headers=headers, timeout=timeout)

    monkeypatch.setattr(llm_mod.httpx, "post", flaky_post)
    result = asyncio.run(enrich.enrich_signals([sig["id"]]))
    assert result["done"] == 1 and result["failed"] == 0 and state["n"] == 2
