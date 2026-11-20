"""Loads the synthetic exercise scenario.

Each item carries an `analysis` block that Claude produced at build time (category, severity,
confidence, rationale, entities). The loader re-anchors timestamps to "now" and adds the
deterministic enrichment (locations, CVEs, hashtags) from the local analyzer.
"""
import json
from datetime import datetime, timedelta

from .. import config, db
from ..analyzer.local import analyze_local, merge_entities
from ..assess import classify_extra
from ..normalize import build_signal, utcnow


def load_seed(now: datetime | None = None) -> int:
    now = now or utcnow()
    data = json.loads(config.SEED_PATH.read_text(encoding="utf-8"))
    # Albanian and German versions of every scenario item (title, text, rationale)
    i18n_path = config.SEED_PATH.with_name("scenario_i18n.json")
    translations = json.loads(i18n_path.read_text(encoding="utf-8")) if i18n_path.exists() else {}
    signals = []
    for item in data["signals"]:
        local = analyze_local(item["title"], item["text"])
        pre = item["analysis"]
        analysis = {
            **local,
            **classify_extra(pre["category"], item["title"], item["text"]),
            "category": pre["category"],
            "tags": pre.get("tags", []),
            "severity": pre["severity"],
            "confidence": pre["confidence"],
            "rationale": pre["rationale"],
            "entities": merge_entities(local["entities"], pre.get("entities", {})),
            "analyzer": "claude-precomputed",
            "i18n": translations.get(item["id"], {}),
        }
        signals.append(build_signal(
            source_name=item["source_name"],
            source_type=item["source_type"],
            reliability=item["reliability"],
            title=item["title"],
            text=item["text"],
            url=item.get("url"),
            timestamp=now - timedelta(hours=item["hours_ago"]),
            analysis=analysis,
            synthetic=True,
            signal_id=f"seed-{item['id']}",
        ))
    return db.insert_signals(signals)


def reset_seed() -> int:
    db.delete_synthetic()
    return load_seed()
