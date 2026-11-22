"""Evaluate the base and the fine-tuned Gemma directly with transformers (no Ollama needed).

  python training/eval_hf.py --data C:/Users/you/hybridscope-ft/data \
      --model base=C:/Users/you/hybridscope-ft/base --model trained=C:/Users/you/hybridscope-ft/out/merged

Same test rows and same prompts for every model (rows never used in training), greedy decoding.
Writes eval_<name>.json and eval_summary_hf.json next to the data.
"""
import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer


def parse(text):
    """The JSON answer; if it was cut short (we stop early, see max_new_tokens), the first fields still count."""
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:  # noqa: BLE001
            pass
    found = dict(re.findall(r'"(category|verdict)"\s*:\s*"([a-z_]+)"', text))
    return found or None


def metrics(res):
    out = {}
    for task in ("classify", "claim"):
        sub = [x for x in res if x["task"] == task]
        if not sub:
            continue
        m = {"n": len(sub), "accuracy": round(sum(x["pred"] == x["gold"] for x in sub) / len(sub), 3),
             "valid_json": round(sum(x["valid"] for x in sub) / len(sub), 3),
             "sec_per_item": round(sum(x["sec"] for x in sub) / len(sub), 1)}
        if task == "claim":
            tp = sum(x["pred"] == "disinformation" == x["gold"] for x in sub)
            called = sum(x["pred"] == "disinformation" for x in sub)
            actual = sum(x["gold"] == "disinformation" for x in sub)
            m["precision_disinfo"] = round(tp / called, 3) if called else None
            m["recall_disinfo"] = round(tp / actual, 3) if actual else None
        m["predictions"] = dict(Counter(str(x["pred"]) for x in sub))
        out[task] = m
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--model", action="append", required=True, help="name=path")
    ap.add_argument("--threads", type=int, default=14)
    ap.add_argument("--limit", type=int, default=0, help="per task")
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    rows = [json.loads(l) for l in (args.data / "test.jsonl").open(encoding="utf-8")]
    if args.limit:
        rows = [r for r in rows if r["task"] == "classify"][: args.limit] + [r for r in rows if r["task"] == "claim"][: args.limit]

    summary = {}
    for spec in args.model:
        name, path = spec.split("=", 1)
        tok = AutoTokenizer.from_pretrained(path)
        model = AutoModelForCausalLM.from_pretrained(path, dtype=torch.float32)
        model.eval()
        res, start = [], time.time()
        for i, r in enumerate(rows):
            t0 = time.time()
            prompt = tok.apply_chat_template(r["messages"][:-1], add_generation_prompt=True, tokenize=False)
            ids = tok(prompt, return_tensors="pt", add_special_tokens=False)
            with torch.no_grad():
                # "category" / "verdict" is the first field, so a short answer is enough to score it
                out = model.generate(**ids, max_new_tokens=24 if r["task"] == "classify" else 16, do_sample=False)
            text = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)
            obj = parse(text)
            key = "category" if r["task"] == "classify" else "verdict"
            res.append({"task": r["task"], "gold": r["label"], "pred": (obj or {}).get(key), "valid": obj is not None,
                        "sec": round(time.time() - t0, 1), "answer": text[:300]})
            if (i + 1) % 20 == 0:
                print(f"{name}: {i + 1}/{len(rows)} ({round(time.time() - start)} s)", flush=True)
        m = metrics(res)
        summary[name] = m
        (args.data / f"eval_{name}.json").write_text(json.dumps({"metrics": m, "rows": res}, indent=1), encoding="utf-8")
        print(name, json.dumps(m), flush=True)
        del model
    (args.data / "eval_summary_hf.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
