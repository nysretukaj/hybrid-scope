"""Pluggable analysis layer.

Providers:
  claude-precomputed  analysis of the scenario dataset, produced by Claude at build time (see seed/)
  llm:<model>         any OpenAI-compatible LLM, enabled with LLM_API_KEY (see backend/.env.example)
  local-nlp           offline keyword + gazetteer analyzer (always available, and the fallback)
"""
from .. import config
from ..assess import classify_extra
from ..gazetteer import resolve
from .llm import STATUS as LLM_STATUS
from .llm import analyze_llm, known_model
from .local import CATEGORY_LABELS, analyze_local, merge_entities


def active_analyzer() -> str:
    """Never touches the network: the model is resolved at startup and on first use."""
    if config.llm_enabled():
        model = known_model("analyze")
        return f"llm:{model}" if model else "llm:(connecting)"
    return "local-nlp"


def baseline_of(local: dict) -> dict:
    return {k: local[k] for k in ("category", "tags", "severity", "confidence")} | {"analyzer": "local-nlp"}


def complete_llm(llm: dict, title: str, text: str, location: dict | None) -> dict:
    """Fill what the LLM left out: subcategory/cause/claim/target from the deterministic rules (for the
    LLM's category), and a location from the gazetteer when the text matched none but the LLM named a country."""
    extra = classify_extra(llm["category"], title, text)
    out = {k: v for k, v in llm.items() if v is not None}
    for k, v in extra.items():
        out.setdefault(k, v)
    if not location and llm.get("country"):
        place = resolve(llm["country"])
        if place:
            out["location"] = place
    out.pop("country", None)
    return out


def merge_llm(local: dict, llm: dict, title: str = "", text: str = "") -> dict:
    """LLM decides category, severity and rationale; deterministic extraction keeps locations and CVEs."""
    llm = complete_llm(llm, title, text, local.get("location"))
    return {**local, **llm, "entities": merge_entities(local["entities"], llm["entities"]), "baseline": baseline_of(local)}


def analyze(title: str, text: str, use_llm: bool = True, purpose: str = "analyze") -> dict:
    local = analyze_local(title, text)
    if use_llm and config.llm_enabled():
        llm = analyze_llm(title, text, purpose)
        if llm:
            return merge_llm(local, llm, title, text)
    return local


__all__ = ["analyze", "analyze_local", "active_analyzer", "complete_llm", "merge_entities", "merge_llm",
           "CATEGORY_LABELS", "LLM_STATUS"]
