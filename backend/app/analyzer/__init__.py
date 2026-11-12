"""Pluggable analysis layer.

Providers:
  claude-precomputed  analysis of the scenario dataset, produced by Claude at build time (see seed/)
  llm:<model>         any OpenAI-compatible LLM, enabled with LLM_BASE_URL / LLM_MODEL
  local-nlp           offline keyword + gazetteer analyzer (always available)
"""
from .. import config
from .llm import analyze_llm
from .local import CATEGORY_LABELS, analyze_local, merge_entities


def active_analyzer() -> str:
    return f"llm:{config.LLM_MODEL}" if config.llm_enabled() else "local-nlp"


def analyze(title: str, text: str, use_llm: bool = True) -> dict:
    local = analyze_local(title, text)
    if use_llm and config.llm_enabled():
        llm = analyze_llm(title, text)
        if llm:
            # LLM decides category/severity/rationale; deterministic extraction keeps locations & CVEs.
            return {**local, **llm, "entities": merge_entities(local["entities"], llm["entities"])}
    return local


__all__ = ["analyze", "analyze_local", "active_analyzer", "merge_entities", "CATEGORY_LABELS"]
