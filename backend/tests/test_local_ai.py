"""Local AI layer: dataset, trained classifier, ensemble, local LLM (with a fake Ollama), images, API."""
import base64
import hashlib
import io
import json
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import config

ROOT = Path(__file__).resolve().parents[2]

# Varied, realistic sentences per category so a small model has something to learn.
TEMPLATES = {
    "cyber": ["Ransomware gang encrypts servers of {org} in {city}", "Hackers breach the email system of {org} in {city}",
              "DDoS attack takes the website of {org} in {city} offline", "Phishing campaign steals passwords at {org} in {city}"],
    "disinformation": ["Fake video claims {org} in {city} faked the results", "Bot accounts spread a false story about {org} in {city}",
                       "Fabricated quote of the head of {org} in {city} goes viral", "Hoax about poisoned water from {org} in {city} spreads online"],
    "infrastructure": ["Power outage leaves {city} without electricity after failure at {org}",
                       "Water supply cut in {city} after damage at the {org} pumping station",
                       "Subsea cable of {org} near {city} damaged, internet slow", "Railway signals of {org} in {city} stopped working"],
    "other": ["Football club from {city} wins the cup, says {org}", "New museum opens in {city} with support of {org}",
              "{org} announces a music festival in {city}", "Weather in {city} will be sunny, {org} says"],
}
ORGS = ["the Ministry", "the City Council", "the national bank", "the grid operator", "the university", "the airport"]
CITIES = ["Pristina", "Tirana", "Berlin", "Vienna", "Riga", "Warsaw"]


def _add_labelled(db, n_per_cat: int = 18) -> int:
    from app.normalize import build_signal, utcnow

    now, sigs = utcnow(), []
    for cat, templates in TEMPLATES.items():
        for i in range(n_per_cat):
            title = templates[i % len(templates)].format(org=ORGS[i % len(ORGS)], city=CITIES[(i // 2) % len(CITIES)])
            title += f" (report {i})"
            analysis = {"category": cat, "severity": 0.6 if cat != "other" else 0.1, "confidence": 0.8,
                        "analyzer": "llm:test", "cause": "deliberate" if cat in ("cyber", "disinformation") else "unknown",
                        "claim": "reported", "rationale": f"labelled as {cat}"}
            sigs.append(build_signal(source_name=f"src{i % 5}", source_type="news", reliability=0.8, title=title,
                                     text=title + ".", url=f"https://example.org/{cat}/{i}",
                                     timestamp=now - timedelta(hours=i), analysis=analysis))
    return db.insert_signals(sigs)


def _vec(text: str, dim: int = 64) -> list[float]:
    """Deterministic bag-of-words hashing vector: similar texts get similar vectors."""
    v = np.zeros(dim)
    for w in text.lower().split():
        v[int(hashlib.md5(w.encode()).hexdigest(), 16) % dim] += 1.0
    return list(v)


@pytest.fixture()
def fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "t.db")
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(config, "DATASET_DIR", tmp_path / "dataset")
    monkeypatch.setattr(config, "PUBLIC_MODE", False)
    monkeypatch.setattr(config, "LIVE_INGEST_INTERVAL_MIN", 0)
    from app import db
    from app.ingest.seed import load_seed
    from app.ml import classifier, local_llm

    classifier._CACHE.update(mtime=None, bundle=None)
    local_llm._INDEX.update(key=None, records=[], matrix=None)
    db.init_db()
    load_seed()
    return db


@pytest.fixture()
def fake_ollama(monkeypatch):
    """A stand-in for the Ollama server: answers by schema, embeds by word hashing."""
    from app.ml import ollama

    calls = {"chat": []}

    def chat_json(messages, schema=None, model=None, temperature=0.0, num_ctx=8192):
        calls["chat"].append({"messages": messages, "schema": schema})
        props = (schema or {}).get("properties", {})
        if "verdict" in props:
            return {"verdict": "coordinated", "confidence": 0.8, "summary": "Linked reports.",
                    "reasons": ["shared actor"], "missing_evidence": ["official attribution"]}
        if "description" in props:
            return {"description": "A burning substation.", "visible_text": "", "threat_relevant": True,
                    "category": "infrastructure", "signs_of_manipulation": [], "confidence": 0.7}
        text = messages[-1]["content"].lower()
        category = "cyber" if any(w in text for w in ("ransomware", "hack", "ddos", "phishing")) else "other"
        return {"category": category, "subcategory": "ransomware" if "ransomware" in text else "general",
                "severity": 0.7, "confidence": 0.85, "cause": "deliberate", "claim": "reported",
                "rationale": "fake local answer", "entities": {"actors": [], "orgs": [], "technologies": [], "narratives": []},
                "country": "Germany", "image_findings": "a picture" if messages[-1].get("images") else ""}

    monkeypatch.setattr(ollama, "available", lambda: True)
    monkeypatch.setattr(ollama, "chat_model", lambda: "gemma3:4b")
    monkeypatch.setattr(ollama, "embed_model", lambda: "fake-embed")
    monkeypatch.setattr(ollama, "has_model", lambda name: True)
    monkeypatch.setattr(ollama, "chat_json", chat_json)
    monkeypatch.setattr(ollama, "embed", lambda texts, model=None: [_vec(t) for t in texts])
    return calls


def _png(color=(200, 30, 30), size=(64, 48)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _wait_job(timeout=120):
    from app.ml import jobs

    start = time.time()
    while jobs.STATE["running"] and time.time() - start < timeout:
        time.sleep(0.1)
    assert not jobs.STATE["running"], "job did not finish"
    return jobs.STATE


# --- images ----------------------------------------------------------------------------
def test_image_found_in_feed_entries():
    from app.ml.images import image_from_entry

    assert image_from_entry({"media_content": [{"url": "https://x.org/a.jpg", "medium": "image"}]}) == "https://x.org/a.jpg"
    assert image_from_entry({"links": [{"rel": "enclosure", "type": "image/png", "href": "https://x.org/b.png"}]}) == "https://x.org/b.png"
    assert image_from_entry({"summary": '<p><img src="https://x.org/c.webp" alt=""></p>'}) == "https://x.org/c.webp"
    assert image_from_entry({"summary": "no picture"}) is None


def test_images_are_validated_and_shrunk():
    from app.ml.images import ImageError, decode_upload, prepare

    big, small = prepare(_png(size=(3000, 2000)))
    from PIL import Image

    assert max(Image.open(io.BytesIO(base64.b64decode(big))).size) <= config.IMAGE_MAX_SIDE
    assert max(Image.open(io.BytesIO(base64.b64decode(small))).size) <= 320
    with pytest.raises(ImageError):
        prepare(b"definitely not an image")
    with pytest.raises(ImageError):
        decode_upload("%%%not-base64%%%")
    data_url = "data:image/png;base64," + base64.b64encode(_png()).decode()
    assert decode_upload(data_url)[:4] == b"\x89PNG"


def test_image_download_refuses_the_local_network():
    from app.ml.images import ImageError, fetch

    for url in ("http://127.0.0.1:8000/x.png", "http://localhost/x.png", "file:///etc/passwd", "ftp://x.org/a.png"):
        with pytest.raises(ImageError):
            fetch(url)


# --- dataset ---------------------------------------------------------------------------
def test_dataset_uses_only_trustworthy_labels(fresh):
    from app.ml import dataset
    from app.normalize import build_signal, utcnow

    rules_only = build_signal(source_name="x", source_type="news", reliability=0.5, title="Ransomware in Berlin",
                              text="Ransomware in Berlin.", url="https://e.org/r", timestamp=utcnow(),
                              analysis={"category": "cyber", "analyzer": "local-nlp"})
    fresh.insert_signals([rules_only])
    records = dataset.build()
    assert records and all(r["quality"] in ("gold", "silver", "silver-local") for r in records)
    assert rules_only["id"] not in {r["id"] for r in records}
    assert {r["split"] for r in records} <= {"train", "val"}
    assert dataset.split_of("abc") == dataset.split_of("abc")  # stable split


def test_dataset_export_is_valid_for_fine_tuning(fresh):
    from app.ml import dataset

    _add_labelled(fresh, 12)
    out = dataset.export()
    files = {k: Path(v) for k, v in out["files"].items()}
    assert all(p.exists() for p in files.values())
    lines = files["sft_chat.jsonl"].read_text(encoding="utf-8").splitlines()
    assert len(lines) == out["records"] > 40
    first = json.loads(lines[0])
    assert [m["role"] for m in first["messages"]] == ["system", "user", "assistant"]
    assert "category" in json.loads(first["messages"][2]["content"])
    # the scenario's hybrid alerts are silver examples for the hybrid verifier
    assert out["verification"] >= 1
    # the Colab script accepts the export
    res = subprocess.run([sys.executable, str(ROOT / "training" / "finetune_lora.py"), "--data", str(files["sft_chat.jsonl"]), "--check"],
                         capture_output=True, text=True, timeout=60)
    assert res.returncode == 0, res.stderr
    assert "dataset OK" in res.stdout


# --- trained classifier ------------------------------------------------------------------
def test_classifier_trains_offline_with_word_features(fresh):
    from app.ml import classifier

    _add_labelled(fresh, 18)
    meta = classifier.train()
    assert meta["features"] == "tfidf"  # no Ollama in this test
    m = meta["metrics"]["category"]
    assert m["support"] >= 8 and 0.0 <= m["accuracy"] <= 1.0 and "rules_baseline" in m
    preds = classifier.predict(["Ransomware gang encrypts servers of the airport in Riga (report 99)"])
    assert preds[0]["category"]["label"] == "cyber"
    assert classifier.info()["records"] == meta["records"]


def test_classifier_trains_on_embeddings_when_available(fresh, fake_ollama):
    from app.ml import classifier

    _add_labelled(fresh, 18)
    meta = classifier.train()
    assert meta["features"] == "embeddings" and meta["embed_model"] == "fake-embed"
    assert fresh.count_embeddings() >= meta["records"]
    assert classifier.predict(["Bot accounts spread a false story about the bank in Tirana"])[0]["category"]["label"] == "disinformation"


def test_classifier_refines_rules_only_when_confident(fresh, monkeypatch):
    from app.analyzer import analyze_local
    from app.ml import classifier

    items = [("Concert in Berlin", "A concert in Berlin."), ("Concert in Vienna", "A concert in Vienna.")]
    analyses = [analyze_local(t, x) for t, x in items]
    monkeypatch.setattr(classifier, "predict", lambda texts, allow_embeddings=True, **kw: [
        {"category": {"label": "cyber", "prob": 0.95}}, {"category": {"label": "cyber", "prob": 0.5}}])
    monkeypatch.setattr(classifier, "decision_threshold", lambda: None)
    assert classifier.refine(items, analyses) == 0  # never reached 90% precision: the model does not decide alone
    monkeypatch.setattr(classifier, "decision_threshold", lambda: 0.9)
    assert classifier.refine(items, analyses) == 1
    assert analyses[0]["category"] == "cyber" and analyses[0]["analyzer"] == "local-ml"
    assert "Trained model" in analyses[0]["rationale"] and "Modeli i trajnuar" in analyses[0]["i18n"]["sq"]["rationale"]
    assert analyses[1]["category"] == "other"  # 50% is not enough


def test_background_check_never_overwrites_llm_labels(fresh, monkeypatch):
    from app.ml import classifier
    from app.normalize import build_signal, utcnow

    rules = build_signal(source_name="x", source_type="news", reliability=0.6, title="Concert in Riga", text="A concert.",
                         url="https://e.org/1", timestamp=utcnow(), analysis={"category": "other", "analyzer": "local-nlp"})
    llm = build_signal(source_name="x", source_type="news", reliability=0.6, title="Concert in Tirana", text="A concert.",
                       url="https://e.org/2", timestamp=utcnow(), analysis={"category": "other", "analyzer": "llm:test"})
    fresh.insert_signals([rules, llm])
    monkeypatch.setattr(classifier, "predict", lambda texts, allow_embeddings=True, **kw: [{"category": {"label": "cyber", "prob": 0.95}}] * len(texts))
    monkeypatch.setattr(classifier, "decision_threshold", lambda: 0.9)
    assert classifier.refine_stored([rules["id"], llm["id"]]) == 1
    stored = {s["id"]: s for s in fresh.fetch_by_ids([rules["id"], llm["id"]])}
    assert stored[rules["id"]]["category"] == "cyber" and stored[rules["id"]]["analyzer"] == "local-ml"
    assert stored[llm["id"]]["category"] == "other" and stored[llm["id"]]["analyzer"] == "llm:test"


def test_pictures_are_used_only_when_they_help():
    from app.ml.classifier import _compare_modalities, fuse

    rng = np.random.default_rng(0)
    n = 120
    y = ["cyber" if i % 2 else "physical" for i in range(n)]
    text = rng.normal(size=(n, 16)).astype(np.float32)          # text says nothing here
    mask = np.ones(n, dtype=bool)
    informative = np.zeros((n, 8), dtype=np.float32)
    informative[:, 0] = [1.0 if c == "cyber" else -1.0 for c in y]  # the picture tells the class
    weights = np.ones(n)
    good = _compare_modalities(text, fuse(text, informative, mask), y, weights, mask)
    assert good["chosen"] == "text+image" and good["text+image"]["macro_f1"] > good["text"]["macro_f1"]
    # pictures that carry no information are not adopted
    text_good = np.zeros((n, 16), dtype=np.float32)
    text_good[:, 0] = [1.0 if c == "cyber" else -1.0 for c in y]
    noise = rng.normal(size=(n, 8)).astype(np.float32)
    bad = _compare_modalities(text_good, fuse(text_good, noise, mask), y, weights, mask)
    assert bad["chosen"] == "text"


def test_text_image_model_trains_and_predicts(fresh, fake_ollama, monkeypatch):
    from app.ml import classifier, image_embeddings

    _add_labelled(fresh, 18)
    # give every report a "picture" whose vector reveals its category, as an informative picture would
    sigs = {s["url"]: s for s in fresh.fetch_signals()}

    def vectors_for_urls(urls, progress=None, fetch_missing=True):
        img = np.zeros((len(urls), image_embeddings.DIM), dtype=np.float32)
        mask = np.zeros(len(urls), dtype=bool)
        for i, u in enumerate(urls):
            if u:
                cat = u.split("/")[-2]
                img[i, ["cyber", "disinformation", "infrastructure", "other"].index(cat)] = 1.0
                mask[i] = True
        return img, mask

    for s in sigs.values():
        if s["url"] and s["url"].startswith("https://example.org/"):
            with fresh.get_conn() as conn:
                conn.execute("UPDATE signals SET image_url = ? WHERE id = ?", (s["url"] + "/pic.jpg", s["id"]))
    monkeypatch.setattr(image_embeddings, "available", lambda: True)
    monkeypatch.setattr(image_embeddings, "vectors_for_urls",
                        lambda urls, progress=None, fetch_missing=True: vectors_for_urls([u.rsplit("/", 1)[0] if u else None for u in urls]))
    meta = classifier.train()
    mod = meta["modalities"]
    assert mod["images_used"] >= 40  # only the example.org reports have a picture and mod["chosen"] in ("text", "text+image")
    assert meta["features"] == ("embeddings+image" if mod["chosen"] == "text+image" else "embeddings")
    # a report without a picture still gets a prediction
    pred = classifier.predict(["Ransomware gang encrypts servers of the bank in Riga"], image_vectors=[None])
    assert pred[0]["category"]["label"] == "cyber"


def test_too_little_data_is_reported(fresh):
    from app.ml import classifier

    with pytest.raises(classifier.TrainError):
        classifier.train()  # only the 36 scenario reports, validation split too small


# --- ensemble and local LLM ----------------------------------------------------------------
def test_ensemble_votes_and_agreement():
    from app.analyzer import analyze_local, ensemble

    title, text = "Ransomware hits hospital", "Ransomware hits a hospital in Berlin."
    local = analyze_local(title, text)
    llm = {**local, "category": "cyber", "confidence": 0.9, "analyzer": "ollama:gemma3:4b", "entities": local["entities"]}
    res = ensemble(title, text, local, {"category": {"label": "other", "prob": 0.95}}, [("local_llm", llm)])
    assert res["category"] == "cyber"
    assert [v["source"] for v in res["votes"]] == ["rules", "model", "local_llm"]
    assert 0 < res["agreement"] < 1 and res["analyzer"] == "ollama:gemma3:4b"


def test_local_llm_uses_similar_examples_and_reads_images(fresh, fake_ollama):
    from app.ml import local_llm

    _add_labelled(fresh, 10)
    res = local_llm.analyze("Ransomware gang encrypts servers", "Ransomware gang encrypts servers of the Ministry in Pristina.",
                            image_b64="aGVsbG8=")
    assert res["category"] == "cyber" and res["analyzer"] == "ollama:gemma3:4b"
    assert res["examples"] and res["image_findings"] == "a picture"
    last_call = fake_ollama["chat"][-1]["messages"]
    assert last_call[-1]["images"] == ["aGVsbG8="]
    assert any(m["role"] == "assistant" for m in last_call)  # worked examples were included


# --- API ----------------------------------------------------------------------------------
@pytest.fixture()
def client(fresh):
    from app import main

    main._VERIFICATIONS.clear()
    with TestClient(main.app) as c:
        yield c


def test_ml_status_without_ollama(client):
    s = client.get("/api/ml/status").json()
    assert s["ollama"]["available"] is False and s["classifier"] is None
    assert s["dataset"]["total"] >= 30
    assert client.get("/api/health").json()["local_ai"]["available"] is False
    assert client.post("/api/ml/label").status_code == 400


def test_analyze_with_image_when_local_ai_is_off(client):
    img = base64.b64encode(_png()).decode()
    r = client.post("/api/analyze", json={"text": "Drones over a power plant near Vienna", "image_base64": img}).json()
    assert r["image_skipped"] is True and r["image_preview"]
    assert client.post("/api/analyze", json={"text": "abc text", "image_base64": "bm90IGFuIGltYWdl"}).status_code == 400


def test_analyze_with_local_ai_returns_votes(client, fake_ollama):
    r = client.post("/api/analyze", json={"text": "Ransomware attack hit a hospital in Berlin", "use_llm": False}).json()
    assert r["category"] == "cyber" and r["analyzer"].startswith("ollama:")


def test_train_job_and_prediction_at_ingest(client, fresh):
    _add_labelled(fresh, 18)
    assert client.post("/api/ml/train").json() == {"started": True}
    state = _wait_job()
    assert state["error"] is None and state["result"]["heads"][0] == "category"
    assert client.get("/api/ml/status").json()["classifier"]["features"] == "tfidf"
    assert client.get("/api/health").json()["local_ai"]["trained_model"] is True
    from app.ingest.live import _analyze_all
    from app.normalize import utcnow

    sig = _analyze_all([{"source_name": "x", "source_type": "news", "reliability": 0.7,
                         "title": "Phishing campaign steals passwords at the university in Vienna (report 77)",
                         "text": "Phishing campaign steals passwords.", "url": "https://e.org/p",
                         "timestamp": utcnow(), "image_url": "https://e.org/p.jpg"}])[0]
    assert sig["category"] == "cyber" and sig["image_url"] == "https://e.org/p.jpg"


def test_export_endpoints(client, fresh):
    _add_labelled(fresh, 12)
    out = client.post("/api/ml/export").json()
    assert out["records"] > 40
    r = client.get("/api/ml/export/sft_chat.jsonl")
    assert r.status_code == 200 and r.text.count("\n") == out["records"]
    assert client.get("/api/ml/export/..%2F..%2Fapp%2Fconfig.py").status_code == 404


def test_verify_alert_and_image_with_local_ai(client, fresh, fake_ollama, monkeypatch):
    alert_id = client.get("/api/alerts").json()["alerts"][0]["id"]
    v = client.post(f"/api/alerts/{alert_id}/verify-ai", params={"lang": "sq"}).json()
    assert v["verdict"] == "coordinated" and v["reasons"] == ["shared actor"]
    msgs = fake_ollama["chat"][-1]["messages"]
    assert "Albanian" in msgs[0]["content"] and msgs[-1]["content"].endswith("in Albanian.")

    from app import main
    from app.normalize import build_signal, utcnow

    sig = build_signal(source_name="x", source_type="news", reliability=0.7, title="Fire at substation", text="Fire.",
                       url="https://e.org/f", timestamp=utcnow(), analysis={"category": "infrastructure"},
                       image_url="https://e.org/f.jpg")
    fresh.insert_signals([sig])
    monkeypatch.setattr(main, "fetch_image", lambda url: _png())
    r = client.post(f"/api/signals/{sig['id']}/image").json()
    assert r["description"] == "A burning substation." and r["preview"]
    again = client.post(f"/api/signals/{sig['id']}/image").json()
    assert again["cached"] is True
    assert client.post("/api/signals/nope/image").status_code == 404


def test_create_model_sends_examples(client, fresh, fake_ollama, monkeypatch):
    from app.ml import ollama

    sent = {}
    monkeypatch.setattr(ollama, "create_model", lambda name, base, system, messages, parameters:
                        sent.update(name=name, base=base, n=len(messages)) or {"status": "success"})
    r = client.post("/api/ml/create-model").json()
    assert r["model"] == config.OLLAMA_CUSTOM_MODEL and sent["base"] == config.OLLAMA_MODEL and sent["n"] >= 4


def test_public_mode_protects_training(client, monkeypatch):
    monkeypatch.setattr(config, "PUBLIC_MODE", True)
    monkeypatch.setattr(config, "ADMIN_TOKEN", "tok")
    for path in ("/api/ml/train", "/api/ml/label", "/api/ml/export", "/api/ml/create-model"):
        assert client.post(path).status_code == 403
    assert client.get("/api/ml/status").status_code == 200
