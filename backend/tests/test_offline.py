import json
from datetime import timedelta

import pytest

from app import config


@pytest.fixture()
def offline_env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "SNAPSHOT_PATH", tmp_path / "live_snapshot.json")
    from app import db

    db.init_db()
    return db


def _live_signal(title, text, hours_ago, analyzer="llm:test-model"):
    from app.analyzer.local import analyze_local
    from app.normalize import build_signal, utcnow

    analysis = {**analyze_local(title, text), "analyzer": analyzer}
    return build_signal(source_name="Koha", source_type="news (sq)", reliability=0.75, title=title, text=text,
                        url=f"https://example.org/{abs(hash(title))}", timestamp=utcnow() - timedelta(hours=hours_ago),
                        analysis=analysis)


def test_snapshot_roundtrip_reanchors_to_now(offline_env):
    from app.normalize import parse_iso, utcnow
    from app.snapshot import export_snapshot, load_snapshot

    db = offline_env
    long_text = "Cyberattack on the grid operator in Pristina. " + "Details follow. " * 60
    db.insert_signals([
        _live_signal("Grid cyberattack", long_text, hours_ago=50),
        _live_signal("Ransomware in Berlin", "Ransomware hit a hospital in Berlin.", hours_ago=60),
        _live_signal("Football transfer", "The club in Madrid signed a striker.", hours_ago=55, analyzer="local-nlp"),
    ])
    db.cache_put("k1", "", "some text", {"category": "cyber", "analyzer": "llm:test-model"}, "2026-01-01T00:00:00+00:00")

    info = export_snapshot()
    assert info["signals"] == 3 and info["llm_analysed"] == 2 and info["cached_analyses"] == 1
    data = json.loads(config.SNAPSHOT_PATH.read_text(encoding="utf-8"))
    assert all(len(s["text"]) <= 281 for s in data["signals"])  # only short excerpts are stored

    # fresh machine: empty database, snapshot replayed
    config.DB_PATH.unlink()
    db.init_db()
    assert load_snapshot() == 3
    sigs = db.fetch_signals()
    newest = max(parse_iso(s["timestamp"]) for s in sigs)
    assert timedelta(minutes=5) < utcnow() - newest < timedelta(minutes=15)
    assert db.cache_get("k1")["category"] == "cyber"


def test_offline_mode_never_calls_llm_and_uses_cache(offline_env, monkeypatch):
    from app.analyzer import llm as llm_mod
    from app.snapshot import cache_key

    monkeypatch.setattr(config, "LLM_BASE_URL", "https://llm.test/v1")
    monkeypatch.setattr(config, "LLM_API_KEY", "gsk_test")
    monkeypatch.setattr(config, "DEMO_OFFLINE", True)
    assert not config.llm_enabled()

    def boom(*a, **k):
        raise AssertionError("network call in offline mode")

    monkeypatch.setattr(llm_mod.httpx, "post", boom)
    monkeypatch.setattr(llm_mod.httpx, "get", boom)

    from app.main import AnalyzeRequest, analyze_text

    db = offline_env
    db.cache_put(cache_key("", "Cached text"), "", "Cached text", {"category": "cyber", "analyzer": "llm:m"}, "x")
    hit = analyze_text(AnalyzeRequest(text="Cached text"))
    assert hit["cached"] is True and hit["analyzer"] == "llm:m"
    miss = analyze_text(AnalyzeRequest(text="Ransomware hit a hospital in Berlin."))
    assert miss["analyzer"] == "local-nlp" and miss["offline"] is True
