"""LoRA fine-tuning of Gemma 3 1B on the CPU (no GPU needed; slow but real).

Only the answer tokens are trained (the prompt is masked), with the same chat template the model uses at
inference. Checkpoints are written every --save-every steps and a run can be resumed with --resume.

Usage (inside the fine-tuning venv):
  python training/finetune_cpu.py --base C:/Users/you/hybridscope-ft/base --data C:/Users/you/hybridscope-ft/data \
      --out C:/Users/you/hybridscope-ft/out
"""
import argparse
import json
import math
import random
import time
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model
from transformers import AutoModelForCausalLM, AutoTokenizer


def encode(tok, messages, max_len):
    prompt = tok.apply_chat_template(messages[:-1], add_generation_prompt=True, tokenize=False)
    answer = messages[-1]["content"] + "<end_of_turn>\n"
    p_ids = tok(prompt, add_special_tokens=False)["input_ids"]
    a_ids = tok(answer, add_special_tokens=False)["input_ids"]
    if len(p_ids) + len(a_ids) > max_len:  # keep the answer, cut the end of the prompt text
        p_ids = p_ids[: max_len - len(a_ids) - 8] + p_ids[-8:]
    ids = p_ids + a_ids
    labels = [-100] * len(p_ids) + a_ids
    return torch.tensor([ids]), torch.tensor([labels])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--data", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--epochs", type=float, default=1.0)
    ap.add_argument("--lr", type=float, default=2e-4)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--max-len", type=int, default=1400)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--save-every", type=int, default=25, help="optimizer steps")
    ap.add_argument("--limit", type=int, default=0, help="only the first N examples (speed test)")
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()
    torch.set_num_threads(args.threads)
    torch.manual_seed(7)
    args.out.mkdir(parents=True, exist_ok=True)

    tok = AutoTokenizer.from_pretrained(args.base)
    model = AutoModelForCausalLM.from_pretrained(args.base, torch_dtype=torch.float32, attn_implementation="eager")
    model.config.use_cache = False
    if args.resume and (args.out / "adapter" / "adapter_config.json").exists():
        model = PeftModel.from_pretrained(model, args.out / "adapter", is_trainable=True)
        state = json.loads((args.out / "state.json").read_text())
    else:
        model = get_peft_model(model, LoraConfig(
            r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05, task_type="CAUSAL_LM",
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]))
        state = {"example": 0, "step": 0, "log": []}
    model.print_trainable_parameters()
    model.train()

    rows = [json.loads(l) for l in (args.data / "train.jsonl").open(encoding="utf-8")]
    if args.limit:
        rows = rows[: args.limit]
    order = list(range(len(rows))) * math.ceil(args.epochs)
    random.Random(7).shuffle(order)
    order = order[: int(len(rows) * args.epochs)]
    total_steps = math.ceil(len(order) / args.accum)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.0)
    if args.resume and (args.out / "optimizer.pt").exists():
        opt.load_state_dict(torch.load(args.out / "optimizer.pt"))

    def lr_at(step):  # warm-up 5%, then linear decay
        warm = max(1, int(0.05 * total_steps))
        return args.lr * (step + 1) / warm if step < warm else args.lr * max(0.05, (total_steps - step) / (total_steps - warm))

    run_start, first, losses = time.time(), state["example"], []
    for i in range(state["example"], len(order)):
        ids, labels = encode(tok, rows[order[i]]["messages"], args.max_len)
        loss = model(input_ids=ids, labels=labels).loss / args.accum
        loss.backward()
        losses.append(loss.item() * args.accum)
        if (i + 1) % args.accum == 0 or i + 1 == len(order):
            for g in opt.param_groups:
                g["lr"] = lr_at(state["step"])
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            opt.step()
            opt.zero_grad(set_to_none=True)
            state["step"] += 1
            rate = (time.time() - run_start) / (i + 1 - first)  # seconds per example in this run
            eta = rate * (len(order) - i - 1) / 60
            entry = {"step": state["step"], "of": total_steps, "example": i + 1, "loss": round(sum(losses) / len(losses), 4),
                     "sec_per_example": round(rate, 2), "eta_min": round(eta, 1)}
            state["log"].append(entry)
            print(json.dumps(entry), flush=True)
            losses = []
            if state["step"] % args.save_every == 0 or i + 1 == len(order):
                state["example"] = i + 1
                model.save_pretrained(args.out / "adapter")
                torch.save(opt.state_dict(), args.out / "optimizer.pt")
                (args.out / "state.json").write_text(json.dumps(state))
    state["example"] = len(order)
    model.save_pretrained(args.out / "adapter")
    (args.out / "state.json").write_text(json.dumps(state))
    print("training finished", flush=True)


if __name__ == "__main__":
    main()
