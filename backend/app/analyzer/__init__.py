"""Pluggable analysis layer.

Providers:
  claude-precomputed  analysis of the scenario dataset, produced by Claude at build time (see seed/)
  llm:<model>         any OpenAI-compatible LLM, enabled with LLM_API_KEY (see backend/.env.example)
  ollama:<model>      local LLM on this computer (app/ml/local_llm.py), reads text and images
  local-ml            keyword rules corrected by the model trained on our own data (app/ml/classifier.py)
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


# How much each analyzer's vote counts (multiplied by its own confidence).
VOTE_WEIGHT = {"rules": 1.0, "model": 1.5, "local_llm": 2.0, "cloud_llm": 2.0}
_TIE_ORDER = ["cloud_llm", "local_llm", "model", "rules"]


def ensemble(title: str, text: str, local: dict, model_pred: dict | None, llm_results: list[tuple[str, dict]]) -> dict:
    """Combine the analyzers by weighted vote on the category.

    The richest analysis that agrees with the winning category is kept (an LLM's when one agrees), and
    the confidence is lowered when the analyzers disagree. Every vote is returned for transparency."""
    votes = [{"source": "rules", "category": local["category"], "confidence": local["confidence"]}]
    if model_pred and model_pred.get("category"):
        votes.append({"source": "model", "category": model_pred["category"]["label"],
                      "confidence": model_pred["category"]["prob"]})
    for source, res in llm_results:
        votes.append({"source": source, "category": res["category"], "confidence": res["confidence"],
                      "analyzer": res["analyzer"]})
    scores: dict[str, float] = {}
    for v in votes:
        scores[v["category"]] = scores.get(v["category"], 0.0) + VOTE_WEIGHT[v["source"]] * max(0.2, v["confidence"])
    best = max(scores.values())
    tied = {c for c, s in scores.items() if abs(s - best) < 1e-9}
    winner = next(v["category"] for src in _TIE_ORDER for v in votes if v["source"] == src and v["category"] in tied)

    agreeing_llm = next((res for _src, res in llm_results if res["category"] == winner), None)
    if agreeing_llm:
        result = merge_llm(local, agreeing_llm, title, text)
    else:
        result = {**local, "baseline": baseline_of(local)}
        if local["category"] != winner:  # the trained model outvoted the rules
            result.update(classify_extra(winner, title, text))
            result["category"] = winner
            result["tags"] = [t for t in local.get("tags", []) if t != winner]
            result["analyzer"] = "local-ml"
            if winner != "other":
                result["severity"] = max(result["severity"], 0.3)

    total = sum(VOTE_WEIGHT[v["source"]] for v in votes)
    agree = [v for v in votes if v["category"] == winner]
    agreement = sum(VOTE_WEIGHT[v["source"]] for v in agree) / total
    mean_conf = sum(v["confidence"] for v in agree) / len(agree)
    result["confidence"] = round(min(0.97, max(0.05, mean_conf * (0.6 + 0.4 * agreement))), 2)
    result["votes"] = votes
    result["agreement"] = round(agreement, 2)
    if model_pred:
        result["ml"] = model_pred
    return result


def analyze(title: str, text: str, use_llm: bool = True, purpose: str = "analyze",
            use_local_llm: bool = False, use_model: bool = False, image_b64: str | None = None,
            image_vector=None) -> dict:
    """Rules always; then, when asked and available: the trained model, the local LLM (Ollama, can read the
    image) and the cloud LLM. With a single analyzer its result is returned unchanged."""
    local = analyze_local(title, text)
    model_pred, llm_results = None, []
    if use_model:
        from ..ml import classifier, dataset  # imported lazily: the ML stack is optional

        preds = classifier.predict([dataset.model_text(title, text)], image_vectors=[image_vector])
        model_pred = preds[0] if preds else None
    if use_local_llm:
        from ..ml import local_llm

        res = local_llm.analyze(title, text, image_b64=image_b64)
        if res:
            llm_results.append(("local_llm", res))
    if use_llm and config.llm_enabled():
        res = analyze_llm(title, text, purpose)
        if res:
            llm_results.insert(0, ("cloud_llm", res))
    if not model_pred and not llm_results:
        return local
    if not model_pred and len(llm_results) == 1:
        return merge_llm(local, llm_results[0][1], title, text)  # the classic rules + one LLM result
    return ensemble(title, text, local, model_pred, llm_results)


__all__ = ["analyze", "analyze_local", "active_analyzer", "complete_llm", "ensemble", "merge_entities", "merge_llm",
           "CATEGORY_LABELS", "LLM_STATUS"]
