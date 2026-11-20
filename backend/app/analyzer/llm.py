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
  "category": "cyber" | "disinformation" | "political" | "infrastructure" | "physical" | "other",
  "subcategory": one value from the list for that category (see below), or "general",
  "secondary_categories": [same category values, excluding category],
  "severity": number 0-1 (potential harm if true),
  "confidence": number 0-1 (how sure you are of the classification),
  "cause": "deliberate" | "accidental" | "natural" | "unknown",
  "claim": "confirmed" | "alleged" | "opinion" | "reported",
  "target": "who or what is affected, as named in the text, or empty",
  "country": "the main country where it happens, in English, or empty",
  "entities": {"actors": [], "orgs": [], "technologies": [], "narratives": []},
  "rationale": "1-2 sentences in English explaining the classification and severity",
  "rationale_sq": "the same rationale in Albanian",
  "rationale_de": "the same rationale in German"
}
Subcategories:
  cyber: ransomware, ddos, data_breach, phishing, espionage, intrusion, vulnerability, malware
  disinformation: fake_news, deepfake, bot_network, impersonation, coordinated_campaign, propaganda
  political: foreign_interference, election_interference, coercion, destabilization
  infrastructure: energy, water, transport, telecom, ics
  physical: terrorism, organized_crime, border, military, sabotage, unrest, violent_incident
"physical" is the SECURITY category: border incidents, terrorism, organised crime, civil unrest, violent incidents,
military activity and physical sabotage relevant to national security.
"political" = foreign interference, election interference, coercion or pressure by another state, attempts to
destabilise institutions. Ordinary political criticism, debate, elections, protests by citizens or diplomatic
disagreement are NOT political threats: use "other".
"other" = not a security threat (sports, culture, routine politics, product news). Ordinary crime, traffic
accidents, personal fights and local incidents with no state, political, critical-infrastructure or hostile-actor
dimension are also "other" (severity <= 0.2). Routine software bugs or patches without exploitation are "cyber" at low severity.
cause: "deliberate" only if the text gives evidence of intent (an attack, a campaign, sabotage); outages from weather
are "natural", technical failures and honest mistakes are "accidental"; otherwise "unknown". For disinformation,
"deliberate" means disinformation and "accidental" means misinformation (false but without evidence of intent).
claim: "confirmed" if an official or the affected party confirms it, "alleged" if it is a claim, accusation or rumour,
"opinion" for commentary, otherwise "reported".
Severity guide: 0.1 routine/no hostile actor, 0.4 notable, 0.7 serious incident, 0.9 major attack with real-world impact.
Do not invent facts that are not in the text."""

VALID = {"cyber", "disinformation", "political", "infrastructure", "physical", "other"}
CAUSES = {"deliberate", "accidental", "natural", "unknown"}
CLAIMS = {"confirmed", "alleged", "opinion", "reported"}
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


SUMMARY_LANG = {"en": "English", "sq": "Albanian", "de": "German"}


def summarize_alert(alert: dict, lang: str = "en") -> str | None:
    """2-3 plain sentences about an alert for non-specialists, written only from its reports."""
    if not config.llm_enabled() or rate_limited():
        return None
    model = resolve_model("analyze")
    if not model:
        return None
    reports = "\n".join(f"- [{s['category']}] {s['title']} ({s.get('source_label') or s['source_name']})"
                        for s in alert["signals"][-10:])
    prompt = (f"Region: {alert.get('zone_label') or alert['zone']}\nRisk level: {alert['level']} ({alert['score']}/100), "
              f"confidence {round(alert['confidence'] * 100)}%\nReports:\n{reports}")
    payload = {
        "model": model, "temperature": 0.2,
        "messages": [
            {"role": "system", "content": (
                f"You explain security alerts to people with no technical background. Write 2-3 short, calm sentences "
                f"in {SUMMARY_LANG.get(lang, 'English')}: what happened, where, and what it may mean. Use only facts from "
                f"the reports, say clearly when something is not confirmed, and avoid jargon and abbreviations.")},
            {"role": "user", "content": prompt},
        ],
    }
    try:
        resp = httpx.post(f"{config.LLM_BASE_URL}/chat/completions", json=payload, headers=_headers(), timeout=45)
        if resp.status_code == 429:
            STATUS["rate_limited_until"] = time.time() + min(max(float(resp.headers.get("retry-after", "30") or 30), 5), 300)
            return None
        resp.raise_for_status()
        return str(resp.json()["choices"][0]["message"]["content"]).strip()[:800] or None
    except Exception as exc:  # noqa: BLE001
        STATUS["last_error"] = f"{type(exc).__name__}: {exc}"[:200]
        return None


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
    from ..assess import SUBCATEGORIES  # local import keeps the module light for status endpoints

    sub = str(data.get("subcategory") or "").strip()
    target = str(data.get("target") or "").strip()[:80]
    return {
        "category": category,
        "subcategory": sub if sub in SUBCATEGORIES.get(category, {}) or (sub == "general" and category != "other") else None,
        "cause": data.get("cause") if data.get("cause") in CAUSES else None,
        "claim": data.get("claim") if data.get("claim") in CLAIMS else None,
        "target": target or None,
        "country": str(data.get("country") or "").strip()[:60] or None,
        "tags": [c for c in data.get("secondary_categories") or [] if c in VALID and c not in (category, "other")],
        "severity": round(severity, 2),
        "confidence": round(confidence, 2),
        "entities": {k: [str(x) for x in ents.get(k) or [] if str(x).strip()][:8]
                     for k in ("actors", "orgs", "technologies", "narratives")},
        "rationale": str(data.get("rationale", "")).strip()[:500],
        "i18n": {lang: {"rationale": str(data[f"rationale_{lang}"]).strip()[:500]}
                 for lang in ("sq", "de") if str(data.get(f"rationale_{lang}") or "").strip()},
        "analyzer": f"llm:{model}",
    }
