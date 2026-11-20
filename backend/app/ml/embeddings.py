"""Multilingual text embeddings from the local Ollama server (bge-m3), cached in SQLite.

A text is embedded once per model; later calls read the stored vector, so training again or
looking up similar examples is fast.
"""
import hashlib
from collections.abc import Callable

import numpy as np

from .. import db
from . import ollama

BATCH = 16


def _key(model: str, text: str) -> str:
    return hashlib.sha1(f"{model}\n{text}".encode("utf-8")).hexdigest()


def vectors(texts: list[str], progress: Callable[[int, int], None] | None = None) -> np.ndarray | None:
    """L2-normalised float32 matrix, one row per text; None when no embedding model is available."""
    model = ollama.embed_model()
    if not model:
        return None
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    keys = [_key(model, t) for t in texts]
    stored = db.embeddings_get(list(dict.fromkeys(keys)))
    missing = [i for i, k in enumerate(keys) if k not in stored]
    done = len(texts) - len(missing)
    if progress:
        progress(done, len(texts))
    for start in range(0, len(missing), BATCH):
        idx = missing[start:start + BATCH]
        result = ollama.embed([texts[i] for i in idx], model)
        if result is None:
            return None
        rows = []
        for i, vec in zip(idx, result):
            arr = np.asarray(vec, dtype=np.float32)
            stored[keys[i]] = arr.tobytes()
            rows.append((keys[i], model, int(arr.shape[0]), arr.tobytes()))
        db.embeddings_put(rows)
        done += len(idx)
        if progress:
            progress(done, len(texts))
    matrix = np.vstack([np.frombuffer(stored[k], dtype=np.float32) for k in keys])
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0, 1.0, norms)
