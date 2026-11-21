"""Rules that depend on WHO published a report, applied after any analyzer (rules, trained model,
local or cloud LLM), so an LLM re-analysis cannot undo them.

  fact-check   an article by a fact-checker that points to a false claim is (low-severity) disinformation
  state-media  foreign state-controlled media (e.g. Sputnik, RT) are monitored for their NARRATIVES:
               whatever they report about attacks, unrest or military moves is recorded as a propaganda
               narrative to watch (disinformation, claim "alleged"), never as a confirmed event
"""
from ..assess import classify_extra
from ..i18n import tr


def role_of(source_type: str | None) -> str | None:
    base = str(source_type or "").split(" ")[0]
    return base if base in ("fact-check", "state-media") else None


def _set_rationale(a: dict, key: str, keep: bool) -> None:
    a["rationale"] = ((tr(key, "en") + " " + (a.get("rationale") or "")) if keep else tr(key, "en")).strip()
    for lang in ("sq", "de"):
        entry = a.setdefault("i18n", {}).setdefault(lang, {})
        entry["rationale"] = ((tr(key, lang) + " " + (entry.get("rationale") or "")) if keep else tr(key, lang)).strip()


def apply_fact_check_hint(item: dict, a: dict) -> bool:
    """Only for the keyword rules' result: they flag weak disinformation indicators in keyword_scores."""
    if role_of(item.get("source_type")) != "fact-check" or a["category"] != "other":
        return False
    if (a.get("keyword_scores") or {}).get("disinformation", 0) < 1:
        return False
    a.update(classify_extra("disinformation", item["title"], item["text"]))
    a.update(category="disinformation", severity=max(a["severity"], 0.3), confidence=max(a["confidence"], 0.5))
    _set_rationale(a, "nlp.factcheck", keep=False)
    return True


def apply_state_media(item: dict, a: dict) -> bool:
    if role_of(item.get("source_type")) != "state-media" or a["category"] == "other":
        return False
    if a["category"] != "disinformation":
        a["tags"] = [a["category"], *[t for t in a.get("tags") or [] if t not in (a["category"], "disinformation")]]
        a["category"] = "disinformation"
    a.update(subcategory="propaganda", claim="alleged", cause="unknown")
    if not (a.get("rationale") or "").startswith(tr("nlp.propaganda", "en")):
        _set_rationale(a, "nlp.propaganda", keep=True)
    return True


def apply_policies(item: dict, a: dict) -> dict:
    """item: anything with source_type, title, text (a raw item or a stored signal)."""
    apply_fact_check_hint(item, a)
    apply_state_media(item, a)
    return a
