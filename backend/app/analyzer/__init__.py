"""Pluggable analysis layer.

Providers:
  claude-precomputed  analysis of the scenario dataset, produced by Claude at build time (see seed/)
  llm:<model>         any OpenAI-compatible LLM, enabled with LLM_API_KEY (see backend/.env.example)
  local-nlp           offline keyword + gazetteer analyzer (always available, and the fallback)
"""
from .. import config
from .llm import STATUS as LLM_STATUS
from .llm import analyze_llm, resolve_model
from .local import CATEGORY_LABELS, analyze_local, merge_entities


def active_analyzer() -> str:
    if config.llm_enabled():
        model = resolve_model("analyze")
        if model:
            return f"llm:{model}"
    return "local-nlp"


def baseline_of(local: dict) -> dict:
    return {k: local[k] for k in ("category", "tags", "severity", "confidence")} | {"analyzer": "local-nlp"}


def merge_llm(local: dict, llm: dict) -> dict:
    """LLM decides category, severity and rationale; deterministic extraction keeps locations and CVEs."""
    return {**local, **llm, "entities": merge_entities(local["entities"], llm["entities"]), "baseline": baseline_of(local)}


def analyze(title: str, text: str, use_llm: bool = True, purpose: str = "analyze") -> dict:
    local = analyze_local(title, text)
    if use_llm and config.llm_enabled():
        llm = analyze_llm(title, text, purpose)
        if llm:
            return merge_llm(local, llm)
    return local


__all__ = ["analyze", "analyze_local", "active_analyzer", "merge_entities", "merge_llm", "CATEGORY_LABELS", "LLM_STATUS"]
