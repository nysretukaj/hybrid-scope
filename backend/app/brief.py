"""Intelligence brief generator.

Turns a correlated alert into an analyst-style product: BLUF, key judgments with standard
estimative language (ICD 203 scale), TTPs, indicators to watch and recommended actions.
Fully deterministic, so it works without any LLM and every sentence traces back to evidence.
"""
from .analyzer.local import CATEGORY_LABELS
from .normalize import parse_iso

ESTIMATIVE = [
    (0.95, "almost certain"), (0.80, "highly likely"), (0.55, "likely"),
    (0.45, "roughly even chance"), (0.20, "unlikely"), (0.0, "highly unlikely"),
]

ACTIONS = {
    "cyber": "Hunt for indicators tied to {actors}; prioritise patching or mitigating {cves}; restrict and monitor remote access ({tech}).",
    "disinformation": "Coordinate fast, factual public communication through official channels; prebunk the {narratives} narrative(s); report coordinated accounts to {platforms}.",
    "infrastructure": "Raise the alert level of affected operators ({orgs}); verify manual-fallback readiness and spare capacity.",
    "physical": "Increase physical protection and patrols around critical sites in {places}; share sightings with law enforcement.",
}
WATCH = {
    "cyber": "New exploitation, access-sale or leak-site activity involving {actors} or {tech}",
    "disinformation": "Further amplification of {narratives}, especially calls for offline action or cross-language spread",
    "infrastructure": "Additional unexplained outages or control-system anomalies at {orgs}",
    "physical": "Drone sightings, vessel loitering, jamming or crowd mobilisation near critical sites in {places}",
}
PLATFORMS = {"Telegram", "TikTok", "Facebook", "YouTube", "WhatsApp", "VKontakte"}
NOT_INFRA_TECH = {"malicious loader", "deepfake", "drone", "AIS", "GPS", "GNSS"}


def estimative(p: float) -> str:
    return next(label for threshold, label in ESTIMATIVE if p >= threshold)


def _names(entities: list[dict], etype: str, limit: int = 3) -> list[str]:
    return [e["name"] for e in entities if e["type"] == etype][:limit]


def _collect(signals: list[dict], key: str, limit: int = 3) -> list[str]:
    seen = []
    for s in signals:
        for v in s["entities"].get(key) or []:
            if v not in seen:
                seen.append(v)
    return seen[:limit]


def _fmt(items: list[str], fallback: str) -> str:
    return ", ".join(items) if items else fallback


def build_brief(alert: dict) -> dict:
    sigs = alert["signals"]
    shared = alert["shared_entities"]
    cats = alert["categories"]
    zone = alert["zone"]
    likelihood = estimative(alert["confidence"])

    def fill_for(category: str) -> dict:
        """Entities drawn only from this domain's signals, so each line stays on-topic."""
        dom = [s for s in sigs if s["category"] == category] or sigs
        ranked = [e["name"] for e in shared]

        def pick(key: str, limit: int = 3, exclude=()):
            vals = [v for v in _collect(dom, key, 12) if v not in exclude]
            vals.sort(key=lambda v: ranked.index(v) if v in ranked else len(ranked))
            return vals[:limit]

        places = [p for p in pick("locations", 4) if p != zone] or [zone]
        return {
            "actors": _fmt(pick("actors"), "the actors observed"),
            "orgs": _fmt(pick("orgs"), "affected operators"),
            "tech": _fmt(pick("technologies", exclude=PLATFORMS | NOT_INFRA_TECH), "exposed systems"),
            "narratives": _fmt(pick("narratives"), "the observed"),
            "cves": _fmt(_collect(sigs, "cves"), "relevant vulnerabilities"),
            "platforms": _fmt([p for p in _collect(sigs, "technologies", 12) if p in PLATFORMS], "the platforms involved"),
            "places": _fmt(places, zone),
        }

    infra_orgs = _collect([s for s in sigs if s["category"] in ("infrastructure", "cyber")], "orgs")
    orgs = [e["name"] for e in shared if e["type"] == "organisation" and e["name"] in infra_orgs] or infra_orgs
    target = orgs[0] if orgs else zone
    if target[:1].islower():
        target = f"the {target}"

    # BLUF
    if alert["is_hybrid"]:
        bluf = (f"It is {likelihood} that the activity observed in {zone} over the last "
                f"{_span_hours(alert):.0f} hours is a coordinated hybrid campaign combining "
                f"{_join([CATEGORY_LABELS[c].lower() for c in cats])} lines of effort, with {target} as the most "
                f"exposed target. Risk is assessed {alert['level']} ({alert['score']:.0f}/100).")
    else:
        bluf = (f"It is {likelihood} that the reported {CATEGORY_LABELS[cats[0]].lower()} activity in {zone} is accurate; "
                f"no linked activity in other threat domains was found. Risk is assessed {alert['level']} "
                f"({alert['score']:.0f}/100).")

    # Key judgments
    judgments = []
    if alert["is_hybrid"] and len(alert["sequence"]) > 1:
        start = parse_iso(alert["sequence"][0]["first_seen"])
        steps = [f"{x['label'].split(' ')[0].lower()} (+{(parse_iso(x['first_seen']) - start).total_seconds() / 3600:.0f}h)"
                 for x in alert["sequence"]]
        judgments.append(f"The pattern unfolded in sequence: {' -> '.join(steps)}. A "
                         f"{alert['sequence'][0]['label'].split(' ')[0].lower()}-first sequence is consistent with "
                         "preparing the information space before disruptive action.")
    if shared:
        top = shared[:3]
        judgments.append("The signals are linked by shared entities: " +
                         "; ".join(f"{e['name']} ({e['type']}, {e['count']} signals)" for e in top) +
                         ". Shared entities across independent sources reduce the chance of coincidence.")
    impact = max(sigs, key=lambda s: s["severity"])
    judgments.append(f"The most severe development is \"{impact['title']}\" (severity {impact['severity']:.2f}, "
                     f"{impact['source_name']}).")
    low = [s for s in sigs if s["source_reliability"] < 0.5]
    rel = sum(s["source_reliability"] for s in sigs) / len(sigs)
    cred = (f"The assessment draws on {alert['signal_count']} signals from {alert['source_count']} sources "
            f"(mean reliability {rel:.2f}).")
    if low:
        cred += (f" {len(low)} signal(s) come from low-reliability sources; they are used as indicators of intent, "
                 "not as confirmation of events.")
    judgments.append(cred)

    return {
        "alert_id": alert["id"],
        "title": alert["title"],
        "classification": "UNCLASSIFIED // OSINT" + (" // EXERCISE - SYNTHETIC DATA" if alert["synthetic"] else ""),
        "zone": zone,
        "level": alert["level"],
        "score": alert["score"],
        "confidence": alert["confidence"],
        "likelihood": likelihood,
        "period": {"from": alert["first_seen"], "to": alert["last_seen"]},
        "bluf": bluf,
        "key_judgments": judgments,
        "ttps": alert.get("ttps", []),
        "indicators": [WATCH[c].format(**fill_for(c)) for c in cats],
        "actions": ([f"Convene a cross-agency cell (CERT, operators, police, strategic communications) for {zone}; "
                     "treat the domains as one campaign, not separate incidents."] if alert["is_hybrid"] else [])
                   + [ACTIONS[c].format(**fill_for(c)) for c in cats],
        "sources": [{"time": s["timestamp"], "title": s["title"], "source": s["source_name"],
                     "reliability": s["source_reliability"], "category": s["category"], "url": s["url"]}
                    for s in sorted(sigs, key=lambda s: s["timestamp"])],
        "method": "Generated deterministically from correlated signals; estimative language per ICD 203. "
                  "TTP mappings are heuristic and require analyst validation.",
    }


def _span_hours(alert: dict) -> float:
    return max(1.0, (parse_iso(alert["last_seen"]) - parse_iso(alert["first_seen"])).total_seconds() / 3600)


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
