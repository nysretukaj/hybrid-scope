"""Client for a local Ollama server (https://ollama.com).

Every call fails soft: when Ollama is not running, a function returns None and the platform keeps
working with its other analyzers. Availability is checked at most every 30 seconds.
"""
import json
import logging
import re
import time

import httpx

from .. import config

log = logging.getLogger(__name__)

STATUS: dict = {"available": False, "checked_at": -1e9, "models": [], "last_error": None, "version": None}
_CHECK_EVERY_S = 30.0   # while Ollama answers
_RETRY_AFTER_FAILURE_S = 5.0


def setting_enabled() -> bool:
    return config.OLLAMA_ENABLED not in ("0", "false", "off", "no")


def refresh(force: bool = False) -> bool:
    """Ask the server which models it has; cached for 30 s."""
    if not setting_enabled():
        STATUS.update(available=False, models=[], last_error="disabled (OLLAMA_ENABLED=0)")
        return False
    wait = _CHECK_EVERY_S if STATUS["available"] else _RETRY_AFTER_FAILURE_S
    if not force and time.monotonic() - STATUS["checked_at"] < wait:
        return STATUS["available"]
    STATUS["checked_at"] = time.monotonic()
    try:
        resp = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=8)
        resp.raise_for_status()
        STATUS["models"] = sorted(m.get("name", "") for m in resp.json().get("models", []) if m.get("name"))
        STATUS["available"] = True
        STATUS["last_error"] = None
        try:
            STATUS["version"] = httpx.get(f"{config.OLLAMA_URL}/api/version", timeout=3).json().get("version")
        except Exception:  # noqa: BLE001 - the version is only informative
            pass
    except Exception as exc:  # noqa: BLE001
        STATUS.update(available=False, models=[], last_error=f"{type(exc).__name__}: {exc}"[:200])
    return STATUS["available"]


def available() -> bool:
    return refresh()


def has_model(name: str) -> bool:
    """'bge-m3' matches 'bge-m3:latest'; 'gemma3:4b' must match exactly."""
    models = STATUS["models"]
    return name in models or (":" not in name and f"{name}:latest" in models)


def chat_model() -> str | None:
    """The fine-tuned/custom HybridScope model when it exists, otherwise the base model."""
    if not available():
        return None
    for name in (config.OLLAMA_CUSTOM_MODEL, config.OLLAMA_MODEL):
        if name and has_model(name):
            return name
    return None


def ft_model() -> str | None:
    """The fine-tuned fact-check model (training/export_ollama.py), when it is installed."""
    if not available() or not config.OLLAMA_FT_MODEL:
        return None
    return config.OLLAMA_FT_MODEL if has_model(config.OLLAMA_FT_MODEL) else None


def embed_model() -> str | None:
    if not available():
        return None
    return config.OLLAMA_EMBED_MODEL if has_model(config.OLLAMA_EMBED_MODEL) else None


def _extract_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def chat_json(messages: list[dict], schema: dict | None = None, model: str | None = None,
              temperature: float = 0.0, num_ctx: int = 8192) -> dict | None:
    """One chat turn whose answer must be a JSON object (optionally matching `schema`).

    A message may carry "images": [base64 strings] for vision models."""
    model = model or chat_model()
    if not model:
        return None
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": schema or "json",
        "keep_alive": "15m",
        "options": {"temperature": temperature, "num_ctx": num_ctx},
    }
    try:
        resp = httpx.post(f"{config.OLLAMA_URL}/api/chat", json=payload, timeout=config.OLLAMA_TIMEOUT)
        resp.raise_for_status()
        data = _extract_json(resp.json()["message"]["content"])
        if not isinstance(data, dict):
            raise ValueError("answer is not a JSON object")
        STATUS["last_error"] = None
        return data
    except Exception as exc:  # noqa: BLE001 - the caller falls back to the other analyzers
        STATUS["last_error"] = f"chat: {type(exc).__name__}: {exc}"[:200]
        log.warning("local LLM call failed: %s", exc)
        return None


def embed(texts: list[str], model: str | None = None) -> list[list[float]] | None:
    """Embedding vectors for several texts in one call (None when unavailable)."""
    model = model or embed_model()
    if not model or not texts:
        return None
    try:
        resp = httpx.post(f"{config.OLLAMA_URL}/api/embed",
                          json={"model": model, "input": texts, "truncate": True, "keep_alive": "15m"},
                          timeout=config.OLLAMA_TIMEOUT)
        resp.raise_for_status()
        vectors = resp.json().get("embeddings") or []
        if len(vectors) != len(texts):
            raise ValueError(f"expected {len(texts)} embeddings, got {len(vectors)}")
        return vectors
    except Exception as exc:  # noqa: BLE001
        STATUS["last_error"] = f"embed: {type(exc).__name__}: {exc}"[:200]
        log.warning("embedding call failed: %s", exc)
        return None


def create_model(name: str, base: str, system: str, messages: list[dict], parameters: dict) -> dict:
    """Build a named model in Ollama from a base model, a system prompt and example messages."""
    payload = {"model": name, "from": base, "system": system, "messages": messages,
               "parameters": parameters, "stream": False}
    resp = httpx.post(f"{config.OLLAMA_URL}/api/create", json=payload, timeout=config.OLLAMA_TIMEOUT)
    resp.raise_for_status()
    refresh(force=True)
    return resp.json() if resp.content else {"status": "success"}


def status() -> dict:
    refresh()
    return {
        "enabled": setting_enabled(),
        "available": STATUS["available"],
        "url": config.OLLAMA_URL,
        "version": STATUS["version"],
        "models": STATUS["models"],
        "chat_model": chat_model(),
        "base_model": config.OLLAMA_MODEL,
        "base_model_ready": has_model(config.OLLAMA_MODEL),
        "custom_model": config.OLLAMA_CUSTOM_MODEL,
        "custom_model_ready": bool(config.OLLAMA_CUSTOM_MODEL) and has_model(config.OLLAMA_CUSTOM_MODEL),
        "ft_model": config.OLLAMA_FT_MODEL,
        "ft_model_ready": bool(config.OLLAMA_FT_MODEL) and has_model(config.OLLAMA_FT_MODEL),
        "embed_model": config.OLLAMA_EMBED_MODEL,
        "embed_model_ready": has_model(config.OLLAMA_EMBED_MODEL),
        "last_error": STATUS["last_error"],
    }
