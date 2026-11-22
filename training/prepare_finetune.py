"""Build the fine-tuning set for the local LLM: our labelled reports + public, human-verified data.

Two tasks, each with the exact prompt the app uses:
  1. threat classification  - our reports (backend/data/dataset/sft_chat.jsonl, same split as the classifier)
  2. claim check            - is a text disinformation or credible?
        disinformation: EUvsDisinfo cases (EEAS East StratCom, CC BY 4.0) with their factual rebuttal,
                        PolyglotFakeFacts "Fake" (human-labelled, CC BY 4.0)
        credible:       PolyglotFakeFacts "Real" (articles from trusted outlets, CC BY 4.0)

Usage (inside the fine-tuning venv):
  python training/prepare_finetune.py --raw C:/Users/you/hybridscope-ft/raw --out C:/Users/you/hybridscope-ft/data
Writes train.jsonl / test.jsonl (chat format) and a card with the counts. Test rows are never trained on.
"""
import argparse
import csv
import hashlib
import json
import random
import re
from pathlib import Path

CLAIM_SYSTEM = (
    "You are a fact-checking analyst. Decide whether the text below is DISINFORMATION (a false or misleading "
    "claim, e.g. a known propaganda narrative) or CREDIBLE (factual reporting). Respond with ONLY a JSON object: "
    '{"verdict": "disinformation" | "credible", "reason": "one short sentence in English"}'
)
MAX_TEXT = 700  # characters of the text shown to the model (keeps CPU training affordable)


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def first_sentence(text: str, limit: int = 220) -> str:
    text = clean(text)
    m = re.search(r"(.{30,}?[.!?])\s", text + " ")
    s = m.group(1) if m else text
    return s[:limit].rstrip()


def split_of(key: str, test_share: float) -> str:
    """Stable split from a hash of the text, so reruns never move a test row into training."""
    h = int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "test" if h < test_share else "train"


def claim_example(text: str, verdict: str, reason: str) -> dict:
    return {"task": "claim", "label": verdict, "messages": [
        {"role": "system", "content": CLAIM_SYSTEM},
        {"role": "user", "content": "TEXT: " + clean(text)[:MAX_TEXT]},
        {"role": "assistant", "content": json.dumps({"verdict": verdict, "reason": reason}, ensure_ascii=False)},
    ]}


def load_euvsdisinfo(path: Path) -> list[dict]:
    csv.field_size_limit(10 ** 8)
    out = []
    with path.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            text, info = clean(r.get("Disinformation")), clean(r.get("Information"))
            if len(text) < 80 or len(info) < 40:
                continue
            out.append({"text": text, "label": "disinformation", "reason": first_sentence(info), "source": "euvsdisinfo",
                        "balkans": any(c in (r.get("Country") or "") for c in ("Serbia", "Kosovo", "Bosnia", "Montenegro", "Albania", "Macedonia"))})
    return out


def load_polyglot(path: Path, label: str) -> list[dict]:
    import pandas as pd

    df = pd.read_excel(path)
    cols = {c.lower(): c for c in df.columns}
    # the English translation, not the original: fake and real articles come in different language mixes,
    # and the model must learn disinformation, not "this language is usually real"
    text_col = next((cols[c] for c in ("english translated version", "text", "content", "article", "body") if c in cols), None)
    title_col = None  # the headlines are in the original language; English text only
    if text_col is None:  # fall back to the longest text column
        text_col = max(df.columns, key=lambda c: df[c].astype(str).str.len().median())
    reason = ("Labelled fake by human annotators; the claim is not supported by trusted sources." if label == "disinformation"
              else "Factual reporting from a trusted outlet, consistent with verified sources.")
    out = []
    for _, r in df.iterrows():
        text = clean(r[text_col])
        if title_col is not None and clean(r[title_col]) and not text.startswith(clean(r[title_col])[:40]):
            text = clean(r[title_col]) + ". " + text
        if len(text) >= 120:
            out.append({"text": text, "label": label, "reason": reason, "source": "polyglot", "balkans": False})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--ours", type=Path, default=Path(__file__).resolve().parents[1] / "backend/data/dataset/sft_chat.jsonl")
    ap.add_argument("--claims-per-class", type=int, default=400, help="training rows per verdict")
    ap.add_argument("--test-per-class", type=int, default=100)
    args = ap.parse_args()
    rnd = random.Random(7)
    args.out.mkdir(parents=True, exist_ok=True)

    train, test = [], []
    # 1. our threat classification (same train/val split as the classifier)
    for line in args.ours.open(encoding="utf-8"):
        d = json.loads(line)
        row = {"task": "classify", "label": json.loads(d["messages"][-1]["content"]).get("category"), "messages": d["messages"]}
        (train if d["split"] == "train" else test).append(row)

    # 2. claim check
    eu = load_euvsdisinfo(args.raw / "euvsdisinfo.csv")
    fake = load_polyglot(args.raw / "polyglot_fake.xlsx", "disinformation")
    real = load_polyglot(args.raw / "polyglot_real.xlsx", "credible")
    pools = {"train": {"disinformation": [], "credible": []}, "test": {"disinformation": [], "credible": []}}
    for item in eu + fake + real:
        pools[split_of(item["text"][:300], 0.2)][item["label"]].append(item)
    counts = {}
    for split, per_class in (("train", args.claims_per_class), ("test", args.test_per_class)):
        for label, items in pools[split].items():
            rnd.shuffle(items)
            if label == "disinformation":  # half EU-verified cases (Balkan ones first), half Polyglot fakes
                eu_items = sorted([i for i in items if i["source"] == "euvsdisinfo"], key=lambda i: not i["balkans"])
                pg_items = [i for i in items if i["source"] == "polyglot"]
                chosen = eu_items[: per_class // 2] + pg_items[: per_class - per_class // 2]
            else:
                chosen = items[:per_class]
            counts[f"{split}/{label}"] = len(chosen)
            target = train if split == "train" else test
            target += [claim_example(i["text"], i["label"], i["reason"]) | {"source": i["source"]} for i in chosen]

    rnd.shuffle(train)
    for name, rows in (("train.jsonl", train), ("test.jsonl", test)):
        with (args.out / name).open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    card = {"train": len(train), "test": len(test), "classify_train": sum(r["task"] == "classify" for r in train),
            "classify_test": sum(r["task"] == "classify" for r in test), "claims": counts,
            "available": {"euvsdisinfo": len(eu), "polyglot_fake": len(fake), "polyglot_real": len(real)}}
    (args.out / "card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    print(json.dumps(card, indent=2))


if __name__ == "__main__":
    main()
