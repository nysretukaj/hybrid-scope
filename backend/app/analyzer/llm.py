"""Optional LLM analyzer using any OpenAI-compatible chat endpoint.

Works with free options, for example:
  Groq:   LLM_BASE_URL=https://api.groq.com/openai/v1   LLM_MODEL=llama-3.1-8b-instant  LLM_API_KEY=...
  Gemini: LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai  LLM_MODEL=gemini-2.0-flash  LLM_API_KEY=...
  Ollama: LLM_BASE_URL=http://localhost:11434/v1        LLM_MODEL=qwen2.5:7b  (no key)
Returns None on any failure so callers fall back to the local analyzer.
"""
import json
import logging
import re

import httpx

from .. import config

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a senior OSINT analyst specialising in hybrid threats.
Classify the item and extract entities. Respond with ONLY a JSON object:
{
  "category": "cyber" | "disinformation" | "infrastructure" | "physical" | "other",
  "secondary_categories": [same values, excluding category],
  "severity": number 0-1 (potential harm if true),
  "confidence": number 0-1 (how sure you are of the classification),
  "entities": {"actors": [], "orgs": [], "technologies": [], "narratives": []},
  "rationale": "1-2 sentences explaining the classification and severity"
}
"physical" covers geopolitical / physical security events (military, sabotage, protests, drones, jamming).
Do not invent facts that are not in the text."""

VALID = {"cyber", "disinformation", "infrastructure", "physical", "other"}


def _extract_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", content, re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def analyze_llm(title: str, text: str) -> dict | None:
    if not config.llm_enabled():
        return None
    headers = {"Authorization": f"Bearer {config.LLM_API_KEY}"} if config.LLM_API_KEY else {}
    payload = {
        "model": config.LLM_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"TITLE: {title}\n\nTEXT: {text[:4000]}"},
        ],
    }
    try:
        resp = httpx.post(f"{config.LLM_BASE_URL}/chat/completions", json=payload, headers=headers, timeout=45)
        resp.raise_for_status()
        data = _extract_json(resp.json()["choices"][0]["message"]["content"])
    except Exception as exc:  # noqa: BLE001 - any provider failure falls back to local
        log.warning("LLM analysis failed, falling back to local analyzer: %s", exc)
        return None

    category = data.get("category") if data.get("category") in VALID else "other"
    ents = data.get("entities") or {}
    return {
        "category": category,
        "tags": [c for c in data.get("secondary_categories") or [] if c in VALID and c not in (category, "other")],
        "severity": max(0.0, min(1.0, float(data.get("severity", 0.3)))),
        "confidence": max(0.0, min(1.0, float(data.get("confidence", 0.5)))),
        "entities": {k: [str(x) for x in ents.get(k) or []] for k in ("actors", "orgs", "technologies", "narratives")},
        "rationale": str(data.get("rationale", "")).strip(),
        "analyzer": f"llm:{config.LLM_MODEL}",
    }
