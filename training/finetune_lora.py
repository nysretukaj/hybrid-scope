"""Fine-tune the local LLM on the HybridScope dataset with LoRA (runs on a free Google Colab GPU).

What it does
  1. reads sft_chat.jsonl exported by HybridScope (AI Model page -> Export dataset)
  2. trains a LoRA adapter on top of Gemma 3 4B (instruction-tuned), 4-bit, with Unsloth
  3. reports the loss on the validation split
  4. merges and exports a GGUF file (q4_k_m) that Ollama can run on a laptop without a GPU

Run on Colab (Runtime -> Change runtime type -> T4 GPU):
    !pip install -q unsloth
    # upload sft_chat.jsonl with the file browser on the left, then:
    !python finetune_lora.py --data sft_chat.jsonl --epochs 2
    # download hybridscope-gguf/*.gguf and follow training/README.md to load it into Ollama

Check the data without a GPU (any machine):
    python finetune_lora.py --data sft_chat.jsonl --check
"""
import argparse
import json
import random
import sys
from pathlib import Path

BASE_MODEL = "unsloth/gemma-3-4b-it"
CHAT_TEMPLATE = "gemma-3"


def load_examples(path: Path) -> tuple[list[dict], list[dict]]:
    """Read and validate the export: every line needs system/user/assistant messages with a JSON answer."""
    train, val = [], []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            messages = row.get("messages") or []
            roles = [m.get("role") for m in messages]
            if roles != ["system", "user", "assistant"]:
                raise ValueError(f"line {n}: expected system/user/assistant messages, got {roles}")
            answer = json.loads(messages[2]["content"])  # must be valid JSON with a category
            if "category" not in answer:
                raise ValueError(f"line {n}: the assistant answer has no category")
            example = {"messages": messages}
            if row.get("split") == "val":
                val.append(example)
            else:
                # repeat analyst-corrected (gold) examples so they count more, like in the classifier
                train.extend([example] * max(1, round(float(row.get("weight", 1.0)))))
    if not train:
        raise ValueError("no training examples")
    return train, val


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=Path("sft_chat.jsonl"))
    parser.add_argument("--out", type=Path, default=Path("hybridscope-gguf"))
    parser.add_argument("--epochs", type=float, default=2)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--max-seq", type=int, default=2048)
    parser.add_argument("--check", action="store_true", help="only validate the dataset (no GPU needed)")
    args = parser.parse_args()

    train, val = load_examples(args.data)
    cats: dict[str, int] = {}
    for ex in train:
        c = json.loads(ex["messages"][2]["content"])["category"]
        cats[c] = cats.get(c, 0) + 1
    print(f"dataset OK: {len(train)} training examples (gold repeated), {len(val)} validation; categories {cats}")
    if args.check:
        return 0

    # --- everything below needs a CUDA GPU (Colab T4 is enough) ---
    from unsloth import FastModel
    from unsloth.chat_templates import get_chat_template, train_on_responses_only
    from datasets import Dataset
    from trl import SFTConfig, SFTTrainer

    random.seed(42)
    random.shuffle(train)
    model, tokenizer = FastModel.from_pretrained(model_name=BASE_MODEL, max_seq_length=args.max_seq,
                                                 load_in_4bit=True, full_finetuning=False)
    model = FastModel.get_peft_model(model, finetune_vision_layers=False, finetune_language_layers=True,
                                     finetune_attention_modules=True, finetune_mlp_modules=True,
                                     r=args.rank, lora_alpha=args.rank, lora_dropout=0, bias="none", random_state=42)
    tokenizer = get_chat_template(tokenizer, chat_template=CHAT_TEMPLATE)

    def to_text(batch):
        return {"text": [tokenizer.apply_chat_template(m, tokenize=False).removeprefix("<bos>") for m in batch["messages"]]}

    train_ds = Dataset.from_list(train).map(to_text, batched=True)
    val_ds = Dataset.from_list(val).map(to_text, batched=True) if val else None
    trainer = SFTTrainer(
        model=model, tokenizer=tokenizer, train_dataset=train_ds, eval_dataset=val_ds,
        args=SFTConfig(dataset_text_field="text", per_device_train_batch_size=2, gradient_accumulation_steps=4,
                       warmup_steps=5, num_train_epochs=args.epochs, learning_rate=args.lr, logging_steps=5,
                       optim="adamw_8bit", weight_decay=0.01, lr_scheduler_type="linear", seed=42,
                       eval_strategy="epoch" if val_ds is not None else "no", report_to="none", output_dir="outputs"),
    )
    # learn only the answers, not the long system prompt
    trainer = train_on_responses_only(trainer, instruction_part="<start_of_turn>user\n",
                                      response_part="<start_of_turn>model\n")
    stats = trainer.train()
    print(f"training loss {stats.training_loss:.4f}")
    if val_ds is not None:
        print(f"validation loss {trainer.evaluate()['eval_loss']:.4f}")

    args.out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained_gguf(str(args.out), tokenizer, quantization_type="Q4_K_M")
    print(f"GGUF written to {args.out}/ - see training/README.md to load it into Ollama")
    return 0


if __name__ == "__main__":
    sys.exit(main())
