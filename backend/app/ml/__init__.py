"""Local AI layer: everything here runs on this computer through Ollama (no API key, no internet).

  ollama.py      client for the local Ollama server (chat with JSON output, images, embeddings)
  images.py      safe download and preparation of images from the sources
  dataset.py     turns the collected, labelled reports into a training dataset (JSONL export)
  embeddings.py  multilingual text vectors (bge-m3), cached in SQLite
  classifier.py  model trained on our own data (logistic regression on embeddings, TF-IDF fallback)
  local_llm.py   local LLM analysis of text and images, and verification of hybrid alerts
  jobs.py        background jobs (labelling, training) with progress for the dashboard
"""
