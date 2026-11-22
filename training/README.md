# Training the HybridScope AI

HybridScope learns from the reports it collects in three ways. The first two run on any laptop
(no GPU); the third fine-tunes the LLM itself and needs a GPU, for example a free Google Colab one.

| Level | What is trained | Where | Time |
|---|---|---|---|
| 1. Trained classifier | category / cause / claim model on bge-m3 embeddings | this computer, page **AI model → Train** | seconds to minutes |
| 2. Examples in the prompt | the local LLM sees the most similar verified reports before answering; `hybridscope` model with our instructions and examples | this computer, automatic / **Create model** | instant |
| 3. LoRA fine-tuning | the weights of Gemma 3 4B | Google Colab (GPU) | 20-60 min |

## The dataset

Page **AI model → Export dataset** (or `POST /api/ml/export`) writes `backend/data/dataset/`:

- `classification.jsonl` - text + labels (category, subcategory, cause, claim), quality, source URL, image URL
- `sft_chat.jsonl` - the same reports in chat format for LLM fine-tuning
- `verification.jsonl` - alerts with the verification verdict (coordinated / not coordinated)
- `dataset_card.md` - counts and label sources

Label quality: **gold** = corrected by an analyst (counts 3x), **silver** = labelled by an LLM or the
curated exercise scenario. Reports seen only by the keyword rules are not used. To grow the dataset:
- correct categories by hand on the alert page (gold),
- set the verification status of alerts (gold examples for the hybrid verifier),
- **AI model → Label with local AI** lets the local LLM label reports the rules alone have seen (silver).
  **Label with pictures** also shows it each report's picture (gemma3 reads images), so it labels from both.

## Text + pictures

With the optional package `fastembed` (`pip install -r backend/requirements-local-ai.txt`; the CLIP
ViT-B/32 model, about 350 MB, is downloaded once into `backend/data/models/fastembed`), every training
also turns the reports' pictures into 512-number CLIP vectors and appends them to the 1024-number bge-m3
text vectors, plus a flag saying "no picture" for reports without one. Text only and text + picture are
tested on the same cross-validation folds. Pictures are kept **only if they make the model better**
(macro-F1), so adding images can never make it worse. The **AI model** page shows both results. Without
fastembed, or with `IMAGE_MODEL_ENABLED=0`, training uses text only.

## Level 3: LoRA fine-tuning on Google Colab

1. Export the dataset and download `sft_chat.jsonl` (AI model page).
2. Open https://colab.research.google.com, *New notebook*, *Runtime → Change runtime type → T4 GPU*.
3. Upload `sft_chat.jsonl` and `training/finetune_lora.py` with the file browser on the left.
4. Run:
   ```
   !pip install -q unsloth
   !python finetune_lora.py --data sft_chat.jsonl --check
   !python finetune_lora.py --data sft_chat.jsonl --epochs 2
   ```
   The script prints the training and validation loss and writes `hybridscope-gguf/*.gguf`.
5. Download the `.gguf` file into `training/` on your computer and load it into Ollama:
   ```
   cd training
   ollama create hybridscope -f Modelfile
   ```
   (`Modelfile` points at `hybridscope-gguf/model-unsloth.Q4_K_M.gguf`; change the file name if yours differs.)
6. Restart HybridScope. The local LLM automatically uses the `hybridscope` model when it exists
   (setting `OLLAMA_CUSTOM_MODEL` in `backend/.env`).

Check that the fine-tuned model is better before keeping it: run the same texts through
**Check a text** before and after, and keep the old model (`ollama cp`) if it is not.

Note: `finetune_lora.py --check` was run locally to validate the data. The GPU part has to run on
Colab and depends on the versions of `unsloth`/`trl` installed there.

## Fine-tuned Gemma 3 1B (fake-news check)

The LLM weights themselves trained with LoRA on a normal laptop CPU (no GPU, ~3.5 h):

```
python training/prepare_finetune.py --raw <dir with euvsdisinfo.csv, polyglot_fake.xlsx, polyglot_real.xlsx> --out <ft>/data
python training/finetune_cpu.py --base <ft>/base --data <ft>/data --out <ft>/out
python training/export_ollama.py --base <ft>/base --out <ft>/out --name hybridscope-ft --llamacpp <llama.cpp checkout>
python training/eval_finetune.py --data <ft>/data --models hybridscope-ft
```

Data: our labelled reports (classification) + EUvsDisinfo (debunked pro-Kremlin claims, Balkans first) and
Polyglot fake/real news (English translation) for "disinformation" vs "credible". 1098 training rows,
267 test rows that never reach training (stable hash split).

Results on the 267 test rows (claim check = 200 of them):

| | Gemma 3 1B untrained | fine-tuned, in Ollama (q8_0) |
|---|---|---|
| fake-news check accuracy | 70% | **83%** |
| precision for "disinformation" | 63% | **77%** |
| recall for "disinformation" | 95% | 95% |
| report category accuracy | 45% | 72% |

The app uses it as `OLLAMA_FT_MODEL` (default `hybridscope-ft`): every local analysis gets a
"Fake-news check" card. The prompt in `backend/app/ml/local_llm.py` (CLAIM_SYSTEM) must stay identical to
the one in `prepare_finetune.py`. Ollama 0.40 cannot import Gemma 3 safetensors (MLX engine), hence the GGUF step;
the Modelfile template puts the system text inside the first user turn, exactly like Gemma's chat template.
