"""Render alerts, signals and analyzer rationales in the requested language.

The analysis layer stores structured facts (categories, counts, entity names, keywords); this
module turns them into sentences, so the same alert reads naturally in English, Albanian or German.
"""
from .i18n import cat_label, entity_name, norm_lang, source_label, source_type_label, tr, zone_name

TRANSLATED_SIGNAL_FIELDS = ("title", "text", "rationale")


def link_reason(r: dict, lang: str) -> str:
    if r["k"] == "entity":
        return tr("link.entity", lang, etype=tr(f"etype.{r['etype']}", lang), name=entity_name(r["name"], lang))
    return tr("link.temporal", lang, a=cat_label(r["a"], lang), b=cat_label(r["b"], lang), h=r["h"])


def alert_texts(zone: str, p: dict, lang: str) -> tuple[str, str]:
    z = zone_name(zone, lang)
    if p["kind"] == "hybrid":
        title = tr("alert.title.hybrid", lang, zone=z)
    elif p["kind"] == "single":
        title = tr("alert.title.single", lang, cat=cat_label(p["cats"][0], lang), zone=z)
    else:
        title = tr("alert.title.multi", lang, zone=z)
    summary = tr("alert.summary", lang, n=p["n"], k=p["k"], zone=z, h=p["h"],
                 cats=", ".join(cat_label(c, lang) for c in p["cats"]))
    if p["seq"]:
        summary += tr("alert.sequence", lang, seq=" -> ".join(cat_label(c, lang) for c in p["seq"]))
    if p["shared"]:
        summary += tr("alert.linked", lang,
                      ents=", ".join(f"{entity_name(name, lang)} ({count})" for name, count in p["shared"]))
    return title, summary


def nlp_rationale(p: dict, lang: str) -> str:
    """Local-NLP rationale from its structured findings (keywords stay as matched in the text)."""
    if p["category"] == "other":
        return tr("nlp.other", lang)
    text = tr("nlp.classified", lang, cat=cat_label(p["category"], lang), kws=", ".join(p["kws"]))
    if p["tags"]:
        text += tr("nlp.secondary", lang, cats=", ".join(cat_label(t, lang) for t in p["tags"]))
    if p["ups"]:
        text += tr("nlp.raised", lang, kws=", ".join(p["ups"]))
    if p["downs"]:
        text += tr("nlp.lowered", lang, kws=", ".join(p["downs"]))
    if p["noloc"]:
        text += tr("nlp.noloc", lang)
    return text


def localize_signal(s: dict, lang: str | None) -> dict:
    lang = norm_lang(lang)
    # source_name stays the key for reliability feedback; the *_label fields are for display only
    out = {**s, "zone_label": zone_name(s.get("zone"), lang),
           "source_label": source_label(s["source_name"], lang) if s.get("synthetic") else s["source_name"],
           "source_type_label": source_type_label(s.get("source_type", ""), lang)}
    if lang != "en":
        translated = (s.get("i18n") or {}).get(lang) or {}
        for field in TRANSLATED_SIGNAL_FIELDS:
            if translated.get(field):
                out[field] = translated[field]
        out["entities"] = {k: [entity_name(v, lang) for v in vals or []] for k, vals in (s.get("entities") or {}).items()}
    return out


def localize_alert(a: dict, lang: str | None) -> dict:
    lang = norm_lang(lang)
    out = dict(a)
    out["zone_label"] = zone_name(a["zone"], lang)
    out["title"], out["summary"] = alert_texts(a["zone"], a["text_params"], lang)
    out["breakdown"] = [{**b, "label": tr(f"sc.{b['key']}", lang), "explanation": tr(b["ex_key"], lang, **b["ex_params"])}
                        for b in a["breakdown"]]
    out["sequence"] = [{**x, "label": cat_label(x["category"], lang)} for x in a["sequence"]]
    out["shared_entities"] = [{**e, "name": entity_name(e["name"], lang)} for e in a["shared_entities"]]
    if "links" in a:
        out["links"] = [{**l, "reasons": [link_reason(r, lang) for r in l["reason_params"]]} for l in a["links"]]
    if "signals" in a:
        out["signals"] = [localize_signal(s, lang) for s in a["signals"]]
        top = next((s for s in out["signals"] if s["id"] == a.get("headline_id")), None)
        if top:
            out["headline"] = top["title"]
    return out
