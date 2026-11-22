"""Local LLM (Ollama, e.g. gemma3:4b): analysis of texts and images, and verification of hybrid alerts.

Retrieval-augmented: before analysing a text, the most similar already-labelled reports (gold first)
are looked up with embeddings and shown to the model as worked examples, so it follows the way our
analysts and our data label things, without any GPU training. All answers are forced into a JSON
schema and validated; anything the model cannot back up stays "unknown" / empty.
"""
import json
import logging
import time

import numpy as np

from ..analyzer.llm import SYSTEM_PROMPT, normalize_analysis
from . import dataset, embeddings, ollama

log = logging.getLogger(__name__)

CATEGORIES = ["cyber", "disinformation", "political", "infrastructure", "physical", "other"]
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "subcategory": {"type": "string"},
        "secondary_categories": {"type": "array", "items": {"type": "string", "enum": CATEGORIES}},
        "severity": {"type": "number"},
        "confidence": {"type": "number"},
        "cause": {"type": "string", "enum": ["deliberate", "accidental", "natural", "unknown"]},
        "claim": {"type": "string", "enum": ["confirmed", "alleged", "opinion", "reported"]},
        "target": {"type": "string"},
        "country": {"type": "string"},
        "entities": {"type": "object", "properties": {k: {"type": "array", "items": {"type": "string"}}
                                                       for k in ("actors", "orgs", "technologies", "narratives")}},
        "rationale": {"type": "string"},
        "rationale_sq": {"type": "string"},
        "rationale_de": {"type": "string"},
        "image_findings": {"type": "string"},
    },
    "required": ["category", "severity", "confidence", "cause", "claim", "rationale"],
}
IMAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "visible_text": {"type": "string"},
        "threat_relevant": {"type": "boolean"},
        "category": {"type": "string", "enum": CATEGORIES},
        "signs_of_manipulation": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["description", "threat_relevant", "category", "confidence"],
}
VERIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["coordinated", "possibly_coordinated", "not_coordinated", "insufficient_evidence"]},
        "confidence": {"type": "number"},
        "summary": {"type": "string"},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "missing_evidence": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["verdict", "confidence", "summary", "reasons", "missing_evidence"],
}

IMAGE_PROMPT = """You look at a picture published with a news report and describe it for a security analyst.
Answer in English with ONLY a JSON object:
{"description": "1-2 sentences: what is visible", "visible_text": "text written in the image, or empty",
 "threat_relevant": true/false, "category": "cyber" | "disinformation" | "political" | "infrastructure" | "physical" | "other",
 "signs_of_manipulation": ["visible signs only, e.g. inconsistent shadows, warped text, cut edges; empty if none"],
 "confidence": number 0-1}
"physical" is the security category. Describe only what you can see. You cannot prove that an image is fake:
list visible signs, never conclude manipulation from them alone. Do not identify people by their face."""

VERIFY_SYSTEM = """You are a senior analyst who checks whether reports from one region form a COORDINATED HYBRID
campaign (several kinds of hostile activity - cyber, disinformation, political pressure, infrastructure, security -
working together) or are unrelated events that happen to be close in time.
Judge only from the reports given. Signs of coordination: shared actors, narratives or infrastructure across
domains; disinformation that anticipates or exploits other incidents; a plausible sequence; independent sources.
Signs against: ordinary events, accidents or weather, single unreliable sources, no shared elements.
Answer with ONLY a JSON object, all texts in {language}:
{{"verdict": "coordinated" | "possibly_coordinated" | "not_coordinated" | "insufficient_evidence",
 "confidence": number 0-1, "summary": "2 short sentences in plain words",
 "reasons": ["up to 4 concrete reasons, each pointing to reports"],
 "missing_evidence": ["what would confirm or refute it, up to 3"]}}"""

# Fake-news check by the fine-tuned model. The prompt must stay word for word the one it was trained with
# (training/prepare_finetune.py, CLAIM_SYSTEM and the "TEXT: " prefix, at most 700 characters).
CLAIM_SYSTEM = (
    "You are a fact-checking analyst. Decide whether the text below is DISINFORMATION (a false or misleading "
    "claim, e.g. a known propaganda narrative) or CREDIBLE (factual reporting). Respond with ONLY a JSON object: "
    '{"verdict": "disinformation" | "credible", "reason": "one short sentence in English"}'
)
CLAIM_MAX_TEXT = 700
FACT_SCHEMA = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["disinformation", "credible"]}, "reason": {"type": "string"}},
    "required": ["verdict", "reason"],
}
# Measured in Ollama on 200 held-out texts never used in training (EUvsDisinfo + Polyglot), see training/README.md
FACT_CHECK_EVAL = {"n": 200, "accuracy": 0.83, "precision": 0.77, "recall": 0.95, "base_accuracy": 0.70}

LANG_NAME = {"en": "English", "sq": "Albanian", "de": "German"}
EXAMPLE_LIMIT = 3
_INDEX: dict = {"key": None, "records": [], "matrix": None}


def _index():
    """Embeddings of every labelled report, rebuilt when the dataset changes."""
    records = [r for r in dataset.build() if r["weight"] > 0]
    key = (len(records), max((r["timestamp"] for r in records), default=""), ollama.embed_model())
    if _INDEX["key"] != key:
        matrix = embeddings.vectors([r["text"] for r in records]) if records else None
        _INDEX.update(key=key, records=records, matrix=matrix)
    return _INDEX["records"], _INDEX["matrix"]


def similar_examples(text: str, k: int = EXAMPLE_LIMIT, min_similarity: float = 0.45) -> list[dict]:
    """The k most similar labelled reports (gold labels count a little more)."""
    if not ollama.embed_model():
        return []
    records, matrix = _index()
    if matrix is None or not len(records):
        return []
    q = embeddings.vectors([text])
    if q is None:
        return []
    sims = matrix @ q[0]
    bonus = np.asarray([0.05 if r["quality"] == "gold" else 0.0 for r in records])
    order = np.argsort(-(sims + bonus))
    out = []
    for i in order:
        r = records[int(i)]
        if sims[i] >= 0.995 or sims[i] < min_similarity:  # skip the text itself and weak matches
            continue
        out.append({**r, "similarity": round(float(sims[i]), 3)})
        if len(out) >= k:
            break
    return out


def _example_answer(r: dict) -> str:
    return json.dumps({"category": r["category"], "subcategory": r.get("subcategory") or "general",
                       "secondary_categories": r.get("secondary_categories") or [], "severity": r["severity"],
                       "confidence": 0.9 if r["quality"] == "gold" else 0.75, "cause": r.get("cause") or "unknown",
                       "claim": r.get("claim") or "reported", "target": r.get("target") or "",
                       "rationale": r.get("rationale") or ""}, ensure_ascii=False)


def analyze(title: str, text: str, image_b64: str | None = None, use_examples: bool = True) -> dict | None:
    """Full analysis of one report (and its picture) by the local LLM; None when Ollama is not available."""
    model = ollama.chat_model()
    if not model:
        return None
    started = time.monotonic()
    examples = similar_examples(dataset.model_text(title, text)) if use_examples else []
    messages = [{"role": "system", "content": SYSTEM_PROMPT + (
        "\nWorked examples from analysts follow; label the new item the same way." if examples else "")}]
    for ex in examples:
        messages.append({"role": "user", "content": f"TITLE: {ex['title']}\n\nTEXT: {ex['text'][:600]}"})
        messages.append({"role": "assistant", "content": _example_answer(ex)})
    content = f"TITLE: {title}\n\nTEXT: {text[:4000]}"
    if image_b64:
        content += ("\n\nA picture published with this report is attached. Use it only as supporting evidence and "
                    "describe what it shows in \"image_findings\".")
    user = {"role": "user", "content": content}
    if image_b64:
        user["images"] = [image_b64]
    messages.append(user)
    data = ollama.chat_json(messages, ANALYSIS_SCHEMA, model=model)
    if not data:
        return None
    out = normalize_analysis(data, f"ollama:{model}")
    out["image_findings"] = str(data.get("image_findings") or "").strip()[:500] or None
    out["examples"] = [{"title": e["title"], "category": e["category"], "quality": e["quality"],
                        "similarity": e["similarity"]} for e in examples]
    out["seconds"] = round(time.monotonic() - started, 1)
    return out


def analyze_image(image_b64: str, context: str = "") -> dict | None:
    model = ollama.chat_model()
    if not model:
        return None
    started = time.monotonic()
    prompt = "Describe this picture." + (f" It was published with the report: \"{context[:300]}\"" if context else "")
    data = ollama.chat_json([{"role": "system", "content": IMAGE_PROMPT},
                             {"role": "user", "content": prompt, "images": [image_b64]}], IMAGE_SCHEMA, model=model)
    if not data:
        return None
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5
    signs = data.get("signs_of_manipulation") if isinstance(data.get("signs_of_manipulation"), list) else []
    return {
        "description": str(data.get("description") or "").strip()[:600],
        "visible_text": str(data.get("visible_text") or "").strip()[:400],
        "threat_relevant": bool(data.get("threat_relevant")),
        "category": data.get("category") if data.get("category") in CATEGORIES else "other",
        "signs_of_manipulation": [str(s).strip()[:160] for s in signs if str(s).strip()][:5],
        "confidence": round(confidence, 2),
        "model": model,
        "seconds": round(time.monotonic() - started, 1),
    }


def verify_alert(alert: dict, lang: str = "en") -> dict | None:
    """Second opinion on an alert: is it really one coordinated hybrid campaign?"""
    model = ollama.chat_model()
    if not model:
        return None
    started = time.monotonic()
    language = LANG_NAME.get(lang, "English")
    system = VERIFY_SYSTEM.format(language=language)
    # small models follow the language best when it is repeated right before they answer
    user = f"{dataset.alert_digest(alert)}\n\nWrite \"summary\", \"reasons\" and \"missing_evidence\" in {language}."
    data = ollama.chat_json([{"role": "system", "content": system},
                             {"role": "user", "content": user}], VERIFY_SCHEMA, model=model)
    if not data:
        return None
    verdicts = VERIFY_SCHEMA["properties"]["verdict"]["enum"]
    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    except (TypeError, ValueError):
        confidence = 0.5

    def strings(key: str, limit: int) -> list[str]:
        value = data.get(key) if isinstance(data.get(key), list) else []
        return [str(x).strip()[:300] for x in value if str(x).strip()][:limit]

    return {
        "verdict": data.get("verdict") if data.get("verdict") in verdicts else "insufficient_evidence",
        "confidence": round(confidence, 2),
        "summary": str(data.get("summary") or "").strip()[:600],
        "reasons": strings("reasons", 4),
        "missing_evidence": strings("missing_evidence", 3),
        "model": model,
        "seconds": round(time.monotonic() - started, 1),
    }


def fact_check(title: str, text: str) -> dict | None:
    """Disinformation or credible? Answer of the fine-tuned model; None when it is not installed or fails."""
    model = ollama.ft_model()
    if not model:
        return None
    started = time.monotonic()
    body = f"{title}. {text}" if title.strip() and title.strip() not in text else text
    content = "TEXT: " + " ".join(body.split())[:CLAIM_MAX_TEXT]
    data = ollama.chat_json([{"role": "system", "content": CLAIM_SYSTEM}, {"role": "user", "content": content}],
                            FACT_SCHEMA, model=model, num_ctx=2048)
    verdict = str((data or {}).get("verdict") or "").strip().lower()
    if verdict not in ("disinformation", "credible"):
        return None
    return {"verdict": verdict, "reason": str(data.get("reason") or "").strip()[:300], "model": model,
            "measured": FACT_CHECK_EVAL, "seconds": round(time.monotonic() - started, 1)}
