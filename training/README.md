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
