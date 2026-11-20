"""Training dataset built from the collected sources.

Every stored report becomes a record (text + labels). Labels have a quality level:
  gold    corrected by an analyst                                   weight 3.0
  silver  analysed by an LLM (cloud or local) or the curated exercise weight 1.0 (local LLM 0.8)
  bronze  only the keyword rules                                    not used for training
Bronze labels are left out on purpose: a model trained on the rules' own output would only learn
to repeat the rules. Near-duplicate reports (syndicated copies) are dropped so they do not count twice.
The split is stable: a report is always in the same part (80% train / 20% validation).

Exports (JSONL, one example per line) go to backend/data/dataset/:
  classification.jsonl  text + labels, for the classifier or any other ML tool
  sft_chat.jsonl        chat format for fine-tuning an LLM (see training/README.md)
  verification.jsonl    alerts with their verification verdict, for training the hybrid verifier
  dataset_card.md       what is inside, label sources and counts
"""
import hashlib
import json
from collections import Counter
from datetime import timedelta

from .. import config, db
from ..assess import mark_duplicates, signal_view
from ..normalize import iso, utcnow

QUALITY_WEIGHT = {"gold": 3.0, "silver": 1.0, "silver-local": 0.8}
LABEL_FIELDS = ("category", "subcategory", "cause", "claim")
VERIFY_LABELS = {"confirmed": "coordinated", "partial": "possibly_coordinated", "disproved": "not_coordinated"}


def label_quality(analyzer: str | None) -> str | None:
    analyzer = analyzer or ""
    if analyzer == "analyst":
        return "gold"
    if analyzer == "claude-precomputed" or analyzer.startswith("llm:"):
        return "silver"
    if analyzer.startswith("ollama:"):
        return "silver-local"
    return None  # local-nlp / local-ml: produced by our own rules or model


def model_text(title: str, text: str) -> str:
    """The exact text the classifier sees, the same for training and prediction."""
    title, text = (title or "").strip(), (text or "").strip()
    body = text if not text.startswith(title) else text[len(title):].strip(" .:-")
    return f"{title}. {body}".strip(". ")[:1500]


def split_of(record_id: str) -> str:
    return "val" if int(hashlib.sha1(record_id.encode()).hexdigest()[:8], 16) % 5 == 0 else "train"


def build(include_bronze: bool = False) -> list[dict]:
    now = utcnow()
    signals = [signal_view(s, now) for s in db.fetch_signals()]
    mark_duplicates(signals)
    images = db.image_analyses_by_url()
    records = []
    for s in signals:
        if s.get("duplicate_of"):
            continue
        quality = label_quality(s.get("analyzer"))
        if quality is None and not include_bronze:
            continue
        image = images.get(s.get("image_url") or "")
        records.append({
            "id": s["id"],
            "text": model_text(s["title"], s["text"]),
            "title": s["title"],
            "category": s["category"],
            "subcategory": s.get("subcategory") if s["category"] != "other" else None,
            "secondary_categories": s.get("tags") or [],
            "cause": s.get("cause"),
            "claim": s.get("claim"),
            "target": s.get("target"),
            "severity": s["severity"],
            "rationale": s.get("rationale"),
            "i18n": s.get("i18n") or {},
            "quality": quality or "bronze",
            "weight": QUALITY_WEIGHT.get(quality or "", 0.0),
            "analyzer": s.get("analyzer"),
            "source": s["source_name"],
            "synthetic": s["synthetic"],
            "url": s.get("url"),
            "image_url": s.get("image_url"),
            "image_description": (image or {}).get("result", {}).get("description"),
            "timestamp": s["timestamp"],
            "split": split_of(s["id"]),
        })
    return records


def stats(records: list[dict] | None = None) -> dict:
    records = build() if records is None else records
    usable = [r for r in records if r["weight"] > 0]
    return {
        "total": len(usable),
        "by_quality": dict(Counter(r["quality"] for r in usable)),
        "by_category": dict(Counter(r["category"] for r in usable)),
        "by_split": dict(Counter(r["split"] for r in usable)),
        "with_image": sum(1 for r in usable if r["image_url"]),
        "unlabelled": db.count_signals() - len(usable),
    }


# --- hybrid verification examples -----------------------------------------------------
def alert_digest(alert: dict, max_signals: int = 14) -> str:
    """A compact, language-neutral description of an alert for the local LLM (and for training)."""
    lines = [
        f"Region: {alert['zone']}",
        f"Time span: {alert['first_seen']} to {alert['last_seen']}",
        f"Threat domains: {', '.join(alert['categories'])}",
        f"Reports: {alert['signal_count']} from {alert['source_count']} sources",
    ]
    shared = [f"{e['name']} ({e['type']}, {e['count']} reports)" for e in alert.get("shared_entities", [])[:6]]
    if shared:
        lines.append("Shared entities: " + "; ".join(shared))
    lines.append("Reports in time order:")
    signals = sorted(alert["signals"], key=lambda s: s["timestamp"])[-max_signals:]
    for s in signals:
        claim = f", stated as {s['claim']}" if s.get("claim") and s["claim"] != "reported" else ""
        lines.append(f"- {s['timestamp'][:16]} [{s['category']}] {s['title']} "
                     f"(source: {s['source_name']}, reliability {s['source_reliability']:.2f}{claim})")
    return "\n".join(lines)


def verification_records() -> list[dict]:
    from ..correlation import build_alerts  # local import: correlation imports this package indirectly
    from ..feedback import apply_feedback

    now = utcnow()
    signals = db.fetch_signals(since_iso=iso(now - timedelta(hours=config.LOOKBACK_HOURS)))
    alerts = build_alerts(apply_feedback(signals), now)
    feedback = db.get_feedback()
    out = []
    for a in alerts:
        fb = feedback.get(a["id"])
        if fb and fb["verdict"] in VERIFY_LABELS:
            label, quality, note = VERIFY_LABELS[fb["verdict"]], "gold", fb.get("note")
        elif a["synthetic"] and a["is_hybrid"]:
            label, quality, note = "coordinated", "silver", "curated exercise scenario"
        else:
            continue  # no trustworthy answer for this alert
        out.append({"id": a["id"], "input": alert_digest(a), "verdict": label, "quality": quality,
                    "note": note, "split": split_of(a["id"])})
    return out


# --- export ----------------------------------------------------------------------------
def _sft_answer(r: dict) -> dict:
    answer = {k: r[k] for k in ("category", "subcategory", "secondary_categories", "severity", "cause", "claim", "target")}
    answer["rationale"] = r.get("rationale") or ""
    for lang in ("sq", "de"):
        answer[f"rationale_{lang}"] = (r["i18n"].get(lang) or {}).get("rationale", "")
    return answer


def export(directory=None) -> dict:
    from ..analyzer.llm import SYSTEM_PROMPT  # the fine-tuned model is used with the same prompt
    from .local_llm import VERIFY_SYSTEM

    directory = directory or config.DATASET_DIR
    directory.mkdir(parents=True, exist_ok=True)
    records = [r for r in build() if r["weight"] > 0]
    verify = verification_records()

    paths = {name: directory / name for name in
             ("classification.jsonl", "sft_chat.jsonl", "verification.jsonl", "dataset_card.md")}
    with paths["classification.jsonl"].open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({k: r[k] for k in ("id", "text", *LABEL_FIELDS, "secondary_categories", "severity",
                                                   "quality", "weight", "source", "synthetic", "url", "image_url",
                                                   "image_description", "split")}, ensure_ascii=False) + "\n")
    with paths["sft_chat.jsonl"].open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps({"split": r["split"], "weight": r["weight"], "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"TITLE: {r['title']}\n\nTEXT: {r['text']}"},
                {"role": "assistant", "content": json.dumps(_sft_answer(r), ensure_ascii=False)},
            ]}, ensure_ascii=False) + "\n")
    with paths["verification.jsonl"].open("w", encoding="utf-8") as f:
        for v in verify:
            f.write(json.dumps({"split": v["split"], "quality": v["quality"], "messages": [
                {"role": "system", "content": VERIFY_SYSTEM.format(language="English")},
                {"role": "user", "content": v["input"]},
                {"role": "assistant", "content": json.dumps({"verdict": v["verdict"], "note": v["note"]}, ensure_ascii=False)},
            ]}, ensure_ascii=False) + "\n")

    st = stats(records)
    vst = Counter(v["verdict"] for v in verify)
    card = [
        "# HybridScope training dataset", "",
        f"Exported: {iso(utcnow())}", "",
        f"- Labelled reports: **{st['total']}** (train {st['by_split'].get('train', 0)} / validation {st['by_split'].get('val', 0)})",
        f"- Label quality: {', '.join(f'{k} {v}' for k, v in st['by_quality'].items())}",
        f"- Categories: {', '.join(f'{k} {v}' for k, v in sorted(st['by_category'].items()))}",
        f"- Reports with an image: {st['with_image']}",
        f"- Hybrid-verification examples: {len(verify)} ({', '.join(f'{k} {v}' for k, v in vst.items()) or 'none yet'})", "",
        "Gold = corrected by an analyst, silver = labelled by an LLM or the curated exercise scenario.",
        "Reports labelled only by keyword rules are not included. Near-duplicate copies are removed.",
        "Texts are short excerpts of public articles; every record keeps its source URL.",
    ]
    paths["dataset_card.md"].write_text("\n".join(card) + "\n", encoding="utf-8")
    return {"records": st["total"], "verification": len(verify), "stats": st,
            "files": {k: str(v) for k, v in paths.items()}}
