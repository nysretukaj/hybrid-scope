"""Image vectors with CLIP (ViT-B/32, via fastembed/ONNX, runs on the CPU in ~0.05 s per picture).

CLIP places pictures with similar content close together (a burning substation near other fires and
blackouts, a hooded hacker near other cyber-crime stock photos), so a classifier can use them next to
the text vectors. Pictures come from the sources' own URLs (fetched safely, see images.py); vectors are
cached in SQLite, and pictures that could not be fetched are remembered so they are not fetched again.

Optional: without the fastembed package (e.g. on the public deployment) everything falls back to text.
"""
import hashlib
import io
import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

import numpy as np

from .. import config, db

log = logging.getLogger(__name__)

MODEL_NAME = "Qdrant/clip-ViT-B-32-vision"
DIM = 512
_MODEL: dict = {"model": None, "error": None}
_lock = threading.Lock()


def available() -> bool:
    if not config.IMAGE_MODEL_ENABLED:
        return False
    try:
        import fastembed  # noqa: F401
    except ImportError:
        return False
    return _MODEL["error"] is None


_load_lock = threading.Lock()


def _model():
    with _load_lock:
        if _MODEL["model"] is None and _MODEL["error"] is None:
            try:
                from fastembed import ImageEmbedding

                _MODEL["model"] = ImageEmbedding(MODEL_NAME, cache_dir=str(config.MODELS_DIR / "fastembed"))
            except Exception as exc:  # noqa: BLE001 - no image model: text-only training
                _MODEL["error"] = f"{type(exc).__name__}: {exc}"[:200]
                log.warning("CLIP image model not available: %s", exc)
        return _MODEL["model"]


def _key(url: str) -> str:
    return hashlib.sha1(f"clip\n{url}".encode("utf-8")).hexdigest()


def embed_bytes(data: bytes) -> np.ndarray | None:
    """Vector of one picture given as bytes (e.g. an upload)."""
    from PIL import Image

    model = _model()
    if model is None:
        return None
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
        with _lock:  # downloads run in parallel, the model one picture at a time
            vec = np.asarray(list(model.embed([img]))[0], dtype=np.float32)
    except Exception as exc:  # noqa: BLE001
        log.info("picture could not be embedded: %s", exc)
        return None
    n = np.linalg.norm(vec)
    return vec / n if n else vec


def _fetch_and_embed(url: str) -> bytes:
    from .images import fetch

    try:
        vec = embed_bytes(fetch(url))
    except Exception:  # noqa: BLE001 - unreachable or not a picture
        vec = None
    return vec.astype(np.float32).tobytes() if vec is not None else b""


def vectors_for_urls(urls: list[str | None], progress: Callable[[int, int], None] | None = None,
                     fetch_missing: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """(matrix n x 512, mask of rows that have a picture). Rows without a usable picture are zeros."""
    out = np.zeros((len(urls), DIM), dtype=np.float32)
    mask = np.zeros(len(urls), dtype=bool)
    wanted = sorted({u for u in urls if u})
    if not wanted or not available() or _model() is None:  # no pictures: never load (or download) the model
        return out, mask
    stored = db.embeddings_get([_key(u) for u in wanted])
    missing = [u for u in wanted if _key(u) not in stored] if fetch_missing else []
    done = len(wanted) - len(missing)
    if progress:
        progress(done, len(wanted))
    with ThreadPoolExecutor(max_workers=6) as pool:  # downloading is the slow part
        for start in range(0, len(missing), 24):
            batch = missing[start:start + 24]
            blobs = list(pool.map(_fetch_and_embed, batch))
            db.embeddings_put([(_key(u), MODEL_NAME, len(b) // 4, b) for u, b in zip(batch, blobs)])
            stored.update({_key(u): b for u, b in zip(batch, blobs)})
            done += len(batch)
            if progress:
                progress(done, len(wanted))
    for i, u in enumerate(urls):
        blob = stored.get(_key(u)) if u else None
        if blob:  # an empty blob marks a picture that could not be fetched
            out[i] = np.frombuffer(blob, dtype=np.float32)
            mask[i] = True
    return out, mask
