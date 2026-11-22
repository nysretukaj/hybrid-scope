"""Measure Ollama models on the held-out test set (rows never used in training).

  python training/eval_finetune.py --data C:/Users/you/hybridscope-ft/data --models hybridscope-base1b hybridscope-ft

Per task: accuracy, valid-JSON rate and, for the claim check, precision/recall of "disinformation"
(precision = of the texts the model calls disinformation, how many really are; recall = of the real
disinformation, how much it catches). Results are saved next to the data as eval_<model>.json.
"""
import argparse
import json
import re
import time
import urllib.request
from collections import Counter
from pathlib import Path

URL = "http://127.0.0.1:11434/api/chat"


def ask(model, messages, timeout=300):
    body = json.dumps({"model": model, "messages": messages, "stream": False, "format": "json",
                       "options": {"temperature": 0, "num_predict": 400}}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())["message"]["content"]


def parse(text):
    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        m = re.search(r"\{.*\}", text, re.S)
        try:
            return json.loads(m.group(0)) if m else None
        except Exception:  # noqa: BLE001
            return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--limit", type=int, default=0, help="per task")
    args = ap.parse_args()
    rows = [json.loads(l) for l in (args.data / "test.jsonl").open(encoding="utf-8")]
    if args.limit:
        rows = [r for r in rows if r["task"] == "classify"][: args.limit] + [r for r in rows if r["task"] == "claim"][: args.limit]

    summary = {}
    for model in args.models:
        res, start = [], time.time()
        for i, r in enumerate(rows):
            t0 = time.time()
            try:
                out = parse(ask(model, r["messages"][:-1]))
            except Exception as exc:  # noqa: BLE001
                out = None
                print("error", exc)
            key = "category" if r["task"] == "classify" else "verdict"
            pred = (out or {}).get(key)
            res.append({"task": r["task"], "gold": r["label"], "pred": pred, "valid": out is not None, "sec": round(time.time() - t0, 1)})
            if (i + 1) % 20 == 0:
                print(f"{model}: {i + 1}/{len(rows)}", flush=True)
        m = {}
        for task in ("classify", "claim"):
            sub = [x for x in res if x["task"] == task]
            if not sub:
                continue
            m[task] = {"n": len(sub), "accuracy": round(sum(x["pred"] == x["gold"] for x in sub) / len(sub), 3),
                       "valid_json": round(sum(x["valid"] for x in sub) / len(sub), 3),
                       "sec_per_item": round(sum(x["sec"] for x in sub) / len(sub), 1)}
            if task == "claim":
                tp = sum(x["pred"] == "disinformation" == x["gold"] for x in sub)
                called = sum(x["pred"] == "disinformation" for x in sub)
                actual = sum(x["gold"] == "disinformation" for x in sub)
                m[task]["precision_disinfo"] = round(tp / called, 3) if called else None
                m[task]["recall_disinfo"] = round(tp / actual, 3) if actual else None
                m[task]["predictions"] = dict(Counter(str(x["pred"]) for x in sub))
        summary[model] = m
        (args.data / f"eval_{model.replace(':', '_')}.json").write_text(json.dumps({"metrics": m, "rows": res}, indent=1), encoding="utf-8")
        print(model, json.dumps(m), f"({round(time.time() - start)} s)", flush=True)
    (args.data / "eval_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
