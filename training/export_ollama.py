"""Merge the LoRA adapter into Gemma 3 1B and load it into Ollama (no GPU, no llama.cpp needed).

  python training/export_ollama.py --base C:/Users/you/hybridscope-ft/base --out C:/Users/you/hybridscope-ft/out \
      --name hybridscope-ft
  python training/export_ollama.py --base ... --out ... --name hybridscope-base1b --no-adapter   # the untrained base,
                                                                                                    # for a fair comparison
--llamacpp: a llama.cpp checkout with convert_hf_to_gguf.py, conversion/ and gguf-py/ (pip install -e gguf-py);
a sparse clone is enough (~2.4 MB). The model is written as q8_0 GGUF (~1 GB). Ollama 0.40 sends a safetensors
import to its MLX engine, which does not support Gemma3ForCausalLM, so the GGUF route is the one that works here.
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATE = '''{{- $sys := "" }}
{{- range .Messages }}{{ if eq .Role "system" }}{{ $sys = .Content }}{{ end }}{{ end }}
{{- $first := true }}
{{- range $i, $_ := .Messages }}
{{- $last := eq (len (slice $.Messages $i)) 1 }}
{{- if eq .Role "user" }}<start_of_turn>user
{{ if and $first $sys }}{{ $sys }}

{{ end }}{{ .Content }}<end_of_turn>
{{ $first = false }}{{ if $last }}<start_of_turn>model
{{ end }}
{{- else if eq .Role "assistant" }}<start_of_turn>model
{{ .Content }}{{ if not $last }}<end_of_turn>
{{ end }}
{{- end }}
{{- end }}'''
# Same layout as Gemma's own chat template (used in training): the system text opens the first user turn.


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--name", required=True)
    ap.add_argument("--no-adapter", action="store_true")
    ap.add_argument("--llamacpp", type=Path, help="llama.cpp checkout; converts to q8_0 GGUF first (recommended)")
    ap.add_argument("--quantize", default="", help="only without --llamacpp: Ollama-side quantization (int8 / int4)")
    args = ap.parse_args()

    if args.no_adapter:
        src = args.base
    else:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model = AutoModelForCausalLM.from_pretrained(args.base, torch_dtype=torch.float32)
        model = PeftModel.from_pretrained(model, args.out / "adapter").merge_and_unload()
        src = args.out / "merged"
        model.to(torch.bfloat16).save_pretrained(src, safe_serialization=True)
        AutoTokenizer.from_pretrained(args.base).save_pretrained(src)
        for f in ("tokenizer.model", "chat_template.jinja", "generation_config.json"):
            if (args.base / f).exists() and not (src / f).exists():
                shutil.copy(args.base / f, src / f)

    if args.llamacpp:
        gguf = args.out / f"{args.name}-q8_0.gguf"
        subprocess.run([sys.executable, str(args.llamacpp / "convert_hf_to_gguf.py"), str(src),
                        "--outtype", "q8_0", "--outfile", str(gguf)], check=True)
        src = gguf

    modelfile = args.out / f"Modelfile.{args.name}"
    modelfile.write_text(
        f"FROM {src.as_posix()}\n\nTEMPLATE \"\"\"{TEMPLATE}\"\"\"\n\n"
        "PARAMETER stop \"<end_of_turn>\"\nPARAMETER temperature 0\nPARAMETER num_ctx 4096\n", encoding="utf-8")
    quant = ["--quantize", args.quantize] if args.quantize and not args.llamacpp else []
    cmd = ["ollama", "create", args.name, "-f", str(modelfile)] + quant
    subprocess.run(cmd, check=True)
    print("created", args.name)


if __name__ == "__main__":
    main()
