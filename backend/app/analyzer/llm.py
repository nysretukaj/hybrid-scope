"""LLM analyzer for any OpenAI-compatible chat endpoint (Groq, Gemini, Ollama, ...).

Setup: put LLM_API_KEY in backend/.env. The provider is detected from the key prefix and the
model is chosen automatically from the provider's model list:
  - "analyze": the strongest available model, for on-demand analysis of one text
  - "live":    a fast model, for bulk background analysis of live signals
Every failure returns None so callers fall back to the local analyzer. Rate limits (HTTP 429)
pause LLM use until the provider's Retry-After has passed.
"""
import json
import logging
import re
import time

import httpx

from .. import config

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior OSINT analyst specialising in hybrid threats.
Classify the item and extract entities. The text may be in English, Albanian or German.
Respond with ONLY a JSON object:
{
  "category": "cyber" | "disinformation" | "infrastructure" | "physical" | "other",
  "secondary_categories": [same values, excluding category],
  "severity": number 0-1 (potential harm if true),
  "confidence": number 0-1 (how sure you are of the classification),
  "entities": {"actors": [], "orgs": [], "technologies": [], "narratives": []},
  "rationale": "1-2 sentences in English explaining the classification and severity"
}
"physical" covers geopolitical / physical security events (military, sabotage, protests, drones, jamming).
"other" = not a security threat (sports, culture, routine politics, product news). Ordinary crime, traffic
accidents, personal fights and local incidents with no state, political, critical-infrastructure or hostile-actor
dimension are also "other" (severity <= 0.2). Routine software bugs or patches without exploitation are "cyber" at low severity.
Severity guide: 0.1 routine/no hostile actor, 0.4 notable, 0.7 serious incident, 0.9 major attack with real-world impact.
Do not invent facts that are not in the text."""

VALID = {"cyber", "disinformation", "infrastructure", "physical", "other"}
PREFERRED = {
    "analyze": ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "gemini-2.5-flash", "gemini-2.0-flash",
                "openai/gpt-oss-20b", "llama-3.1-8b-instant"],
    "live": ["llama-3.1-8b-instant", "gemini-2.0-flash-lite", "gemini-2.0-flash", "openai/gpt-oss-20b",
             "llama-3.3-70b-versatile"],
}
STATUS: dict = {"last_error": None, "rate_limited_until": 0.0, "models": {}, "transient": False}


def _headers() -> dict:
    return {"Authorization": f"Bearer {config.LLM_API_KEY}"} if config.LLM_API_KEY else {}


def list_models() -> list[str]:
    resp = httpx.get(f"{config.LLM_BASE_URL}/models", headers=_headers(), timeout=15)
    resp.raise_for_status()
    return [str(m.get("id", "")).removeprefix("models/") for m in resp.json().get("data", []) if m.get("id")]


def known_model(purpose: str = "analyze") -> str | None:
    """The model in use, without any network call (for status endpoints)."""
    explicit = config.LLM_MODEL if purpose == "analyze" else (config.LLM_MODEL_LIVE or config.LLM_MODEL)
    return explicit or STATUS["models"].get(purpose)


def resolve_model(purpose: str = "analyze") -> str | None:
    explicit = config.LLM_MODEL if purpose == "analyze" else (config.LLM_MODEL_LIVE or config.LLM_MODEL)
    if explicit:
        return explicit
    if purpose in STATUS["models"]:
        return STATUS["models"][purpose]
    try:
        ids = list_models()
    except Exception as exc:  # noqa: BLE001
        STATUS["last_error"] = f"model list: {exc}"[:200]
        return None
    chat = [i for i in ids if not re.search(r"whisper|tts|embed|guard|vision|imagen|aqa|audio", i, re.I)]
    pick = next((p for p in PREFERRED[purpose] if p in chat), None) or next(
        (i for i in chat if re.search(r"llama|gemini|qwen|mistral|gpt", i, re.I)), chat[0] if chat else None)
    if pick:
        STATUS["models"][purpose] = pick
    return pick


def _extract_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def rate_limited() -> bool:
    return time.time() < STATUS["rate_limited_until"]


def analyze_llm(title: str, text: str, purpose: str = "analyze") -> dict | None:
    if not config.llm_enabled() or rate_limited():
        return None
    model = resolve_model(purpose)
    if not model:
        return None
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"TITLE: {title}\n\nTEXT: {text[:4000]}"},
        ],
    }
    STATUS["transient"] = False
    try:
        resp = httpx.post(f"{config.LLM_BASE_URL}/chat/completions", json=payload, headers=_headers(), timeout=45)
        if resp.status_code == 429:
            wait = float(resp.headers.get("retry-after", "30") or 30)
            STATUS["rate_limited_until"] = time.time() + min(max(wait, 5), 300)
            STATUS["last_error"] = f"rate limited by provider, pausing {wait:.0f}s"
            return None
        resp.raise_for_status()
        data = _extract_json(resp.json()["choices"][0]["message"]["content"])
    except Exception as exc:  # noqa: BLE001 - any provider failure falls back to local
        STATUS["last_error"] = f"{type(exc).__name__}: {exc}"[:200]
        # network drops and timeouts are worth retrying; bad requests and parse errors are not
        STATUS["transient"] = isinstance(exc, httpx.TransportError) or (
            isinstance(exc, httpx.HTTPStatusError) and exc.response is not None and exc.response.status_code >= 500)
        log.warning("LLM analysis failed, using local analyzer: %s", exc)
        return None

    STATUS["last_error"] = None
    category = data.get("category") if data.get("category") in VALID else "other"
    ents = data.get("entities") or {}
    try:
        severity = max(0.0, min(1.0, float(data.get("severity", 0.3))))
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    except (TypeError, ValueError):
        severity, confidence = 0.3, 0.5
    return {
        "category": category,
        "tags": [c for c in data.get("secondary_categories") or [] if c in VALID and c not in (category, "other")],
        "severity": round(severity, 2),
        "confidence": round(confidence, 2),
        "entities": {k: [str(x) for x in ents.get(k) or [] if str(x).strip()][:8]
                     for k in ("actors", "orgs", "technologies", "narratives")},
        "rationale": str(data.get("rationale", "")).strip()[:500],
        "analyzer": f"llm:{model}",
    }
