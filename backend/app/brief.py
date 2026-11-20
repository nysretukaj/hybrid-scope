"""Intelligence brief generator.

Turns a correlated alert into an analyst-style product: BLUF, key judgments with standard
estimative language (ICD 203 scale), TTPs, indicators to watch and recommended actions.
Fully deterministic, so it works without any LLM and every sentence traces back to evidence.
Rendered in English, Albanian or German; pass an alert already localized to the same language.
"""
from .i18n import cat_label, entity_name, join_list, norm_lang, place_name, tr, zone_name
from .normalize import parse_iso

ESTIMATIVE_THRESHOLDS = [0.95, 0.80, 0.55, 0.45, 0.20, 0.0]
PLATFORMS = {"Telegram", "TikTok", "Facebook", "YouTube", "WhatsApp", "VKontakte"}
NOT_INFRA_TECH = {"malicious loader", "deepfake", "drone", "AIS", "GPS", "GNSS"}


def estimative(p: float, lang: str = "en") -> str:
    idx = next(i for i, threshold in enumerate(ESTIMATIVE_THRESHOLDS) if p >= threshold)
    return tr(f"est.{idx}", lang)


def _collect(signals: list[dict], key: str, limit: int = 3) -> list[str]:
    seen = []
    for s in signals:
        for v in s["entities"].get(key) or []:
            if v not in seen:
                seen.append(v)
    return seen[:limit]


def _fmt(items: list[str], fallback: str) -> str:
    return ", ".join(items) if items else fallback


def _cat_in_sentence(cat: str, lang: str) -> str:
    """Category names mid-sentence: lower case in English and Albanian; German nouns keep capitals."""
    label = cat_label(cat, lang)
    return label if lang == "de" else label.lower()


def build_brief(alert: dict, lang: str = "en") -> dict:
    lang = norm_lang(lang)
    sigs = alert["signals"]
    shared = alert["shared_entities"]
    cats = alert["categories"]
    zone = alert["zone"]
    zone_label = zone_name(zone, lang)
    likelihood = estimative(alert["confidence"], lang)
    level = tr(f"level.{alert['level']}", lang)

    def fill_for(category: str) -> dict:
        """Entities drawn only from this domain's signals, so each line stays on-topic."""
        dom = [s for s in sigs if s["category"] == category] or sigs
        ranked = [e["name"] for e in shared]

        def pick(key: str, limit: int = 3, exclude=()):
            vals = [v for v in _collect(dom, key, 12) if v not in exclude]
            vals.sort(key=lambda v: ranked.index(v) if v in ranked else len(ranked))
            return vals[:limit]

        places = [place_name(p, lang) for p in pick("locations", 4) if p != zone] or [zone_label]
        return {
            "actors": _fmt(pick("actors"), tr("b.fb.actors", lang)),
            "orgs": _fmt(pick("orgs"), tr("b.fb.orgs", lang)),
            "tech": _fmt(pick("technologies", exclude=PLATFORMS | {entity_name(t, lang) for t in NOT_INFRA_TECH}),
                         tr("b.fb.tech", lang)),
            "narratives": _fmt(pick("narratives"), tr("b.fb.narratives", lang)),
            "cves": _fmt(_collect(sigs, "cves"), tr("b.fb.cves", lang)),
            "platforms": _fmt([p for p in _collect(sigs, "technologies", 12) if p in PLATFORMS], tr("b.fb.platforms", lang)),
            "places": _fmt(places, zone_label),
        }

    infra_orgs = _collect([s for s in sigs if s["category"] in ("infrastructure", "cyber")], "orgs")
    orgs = [e["name"] for e in shared if e["type"] == "organisation" and e["name"] in infra_orgs] or infra_orgs
    target = orgs[0] if orgs else zone_label
    if lang == "en" and target[:1].islower():
        target = f"the {target}"

    # BLUF
    if alert["is_hybrid"]:
        bluf = tr("b.bluf.hybrid", lang, lk=likelihood, zone=zone_label, h=f"{_span_hours(alert):.0f}",
                  cats=join_list([_cat_in_sentence(c, lang) for c in cats], lang), target=target,
                  level=level, score=f"{alert['score']:.0f}")
    else:
        bluf = tr("b.bluf.single", lang, lk=likelihood, cat=_cat_in_sentence(cats[0], lang), zone=zone_label,
                  level=level, score=f"{alert['score']:.0f}")

    # Key judgments
    judgments = []
    if alert["is_hybrid"] and len(alert["sequence"]) > 1:
        start = parse_iso(alert["sequence"][0]["first_seen"])
        steps = [f"{_cat_in_sentence(x['category'], lang)} (+{(parse_iso(x['first_seen']) - start).total_seconds() / 3600:.0f}h)"
                 for x in alert["sequence"]]
        judgments.append(tr("b.j.sequence", lang, steps=" -> ".join(steps),
                            first=_cat_in_sentence(alert["sequence"][0]["category"], lang)))
    if shared:
        items = [tr("b.j.entity_item", lang, name=e["name"], etype=tr(f"etype.{e['type']}", lang), n=e["count"])
                 for e in shared[:3]]
        judgments.append(tr("b.j.entities", lang, list="; ".join(items)))
    impact = max(sigs, key=lambda s: s["severity"])
    judgments.append(tr("b.j.impact", lang, title=impact["title"], sev=f"{impact['severity']:.2f}",
                        source=impact.get("source_label") or impact["source_name"]))
    low = [s for s in sigs if s["source_reliability"] < 0.5]
    rel = sum(s["source_reliability"] for s in sigs) / len(sigs)
    cred = tr("b.j.cred", lang, n=alert["signal_count"], k=alert["source_count"], r=f"{rel:.2f}")
    if low:
        cred += tr("b.j.lowrel", lang, n=len(low))
    judgments.append(cred)

    return {
        "alert_id": alert["id"],
        "lang": lang,
        "title": alert["title"],
        "classification": tr("b.classification", lang) + (tr("b.exercise", lang) if alert["synthetic"] else ""),
        "zone": zone,
        "zone_label": zone_label,
        "level": alert["level"],
        "level_label": level,
        "score": alert["score"],
        "confidence": alert["confidence"],
        "likelihood": likelihood,
        "period": {"from": alert["first_seen"], "to": alert["last_seen"]},
        "bluf": bluf,
        "key_judgments": judgments,
        "ttps": alert.get("ttps", []),
        "indicators": [tr(f"b.watch.{c}", lang, **fill_for(c)) for c in cats],
        "actions": ([tr("b.cell", lang, zone=zone_label)] if alert["is_hybrid"] else [])
                   + [tr(f"b.action.{c}", lang, **fill_for(c)) for c in cats],
        "sources": [{"time": s["timestamp"], "title": s["title"], "source": s.get("source_label") or s["source_name"],
                     "reliability": s["source_reliability"], "category": s["category"], "url": s["url"]}
                    for s in sorted(sigs, key=lambda s: s["timestamp"])],
        "method": tr("b.method", lang),
    }


def _span_hours(alert: dict) -> float:
    return max(1.0, (parse_iso(alert["last_seen"]) - parse_iso(alert["first_seen"])).total_seconds() / 3600)
