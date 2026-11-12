"""Hybrid correlation engine.

1. Cluster threat-relevant signals by correlation zone and time (gap <= CLUSTER_GAP_HOURS).
2. Inside a cluster, link signals that share an actor / org / technology / CVE / narrative
   ("entity" links) or that hit *different* threat domains close in time ("temporal" links).
3. A cluster spanning >= 2 domains with at least one cross-domain link is a HYBRID pattern.
4. Score it with the explainable model in scoring.py.
"""
import hashlib
from collections import defaultdict
from datetime import datetime
from statistics import mean

from . import scoring
from .analyzer.local import CATEGORY_LABELS
from .config import CLUSTER_GAP_HOURS, CROSS_CATEGORY_LINK_HOURS
from .normalize import iso, parse_iso
from .ttp import map_ttps

CATEGORY_ORDER = ["disinformation", "cyber", "infrastructure", "physical"]
LINK_TYPES = {"actors": "actor", "orgs": "organisation", "technologies": "technology", "cves": "CVE", "narratives": "narrative"}


def _hours(a: datetime, b: datetime) -> float:
    return abs((a - b).total_seconds()) / 3600


def cluster_signals(signals: list[dict]) -> list[tuple[str, list[dict]]]:
    by_zone: dict[str, list[dict]] = defaultdict(list)
    for s in signals:
        if s["category"] in CATEGORY_LABELS and s.get("zone"):
            by_zone[s["zone"]].append(s)
    clusters = []
    for zone, items in by_zone.items():
        items.sort(key=lambda s: s["_ts"])
        current = [items[0]]
        for s in items[1:]:
            if _hours(s["_ts"], current[-1]["_ts"]) <= CLUSTER_GAP_HOURS:
                current.append(s)
            else:
                clusters.append((zone, current))
                current = [s]
        clusters.append((zone, current))
    return clusters


def find_links(signals: list[dict]):
    index: dict[tuple, list[dict]] = defaultdict(list)
    display: dict[tuple, str] = {}
    for s in signals:
        seen = set()
        for etype in LINK_TYPES:
            for name in s["entities"].get(etype) or []:
                key = (etype, name.strip().lower())
                if not key[1] or key in seen:
                    continue
                seen.add(key)
                index[key].append(s)
                display.setdefault(key, name.strip())

    links: dict[tuple, dict] = {}

    def add(a: dict, b: dict, kind: str, reason: str):
        if a["id"] == b["id"]:
            return
        first, second = (a, b) if a["_ts"] <= b["_ts"] else (b, a)
        link = links.setdefault((first["id"], second["id"]), {"source": first["id"], "target": second["id"], "kinds": set(), "reasons": []})
        link["kinds"].add(kind)
        if reason not in link["reasons"]:
            link["reasons"].append(reason)

    # Entity links: chain signals sharing an entity in time order (keeps edges linear in size).
    for key, sigs in index.items():
        if len(sigs) < 2:
            continue
        ordered = sorted(sigs, key=lambda s: s["_ts"])
        for a, b in zip(ordered, ordered[1:]):
            add(a, b, "entity", f"Shared {LINK_TYPES[key[0]]}: {display[key]}")

    # Temporal cross-domain links: nearest earlier signal of each *other* domain within the window.
    ordered = sorted(signals, key=lambda s: s["_ts"])
    for i, s in enumerate(ordered):
        linked_cats = set()
        for prev in reversed(ordered[:i]):
            gap = _hours(s["_ts"], prev["_ts"])
            if gap > CROSS_CATEGORY_LINK_HOURS:
                break
            if prev["category"] != s["category"] and prev["category"] not in linked_cats:
                linked_cats.add(prev["category"])
                add(prev, s, "temporal",
                    f"{CATEGORY_LABELS[prev['category']]} -> {CATEGORY_LABELS[s['category']]} within {gap:.0f}h")

    out = [{
        "source": l["source"], "target": l["target"],
        "kind": "entity" if "entity" in l["kinds"] else "temporal",
        "reasons": l["reasons"],
    } for l in links.values()]

    shared = sorted(
        ({"type": LINK_TYPES[k[0]], "name": display[k], "count": len(v), "signal_ids": [s["id"] for s in v]}
         for k, v in index.items() if len(v) >= 2),
        key=lambda e: (-e["count"], e["name"].lower()),
    )
    return out, shared


def _public(sig: dict) -> dict:
    return {k: v for k, v in sig.items() if not k.startswith("_")}


def make_alert(zone: str, sigs: list[dict], now: datetime) -> dict:
    sigs = sorted(sigs, key=lambda s: s["_ts"])
    for s in sigs:
        s["score"] = scoring.signal_score(s, now)

    links, shared = find_links(sigs)
    by_id = {s["id"]: s for s in sigs}
    categories = sorted({s["category"] for s in sigs}, key=CATEGORY_ORDER.index)
    category_counts = {c: sum(1 for s in sigs if s["category"] == c) for c in categories}

    cross_domain = any(by_id[l["source"]]["category"] != by_id[l["target"]]["category"] for l in links)
    is_hybrid = len(categories) >= 2 and cross_domain

    entity_linked = {sid for l in links if l["kind"] == "entity" for sid in (l["source"], l["target"])}
    corroborating = len({s["source_name"] for s in sigs if s["id"] in entity_linked}) or 1

    score, breakdown = scoring.score_alert(sigs, categories, is_hybrid, corroborating, now)
    confidence = scoring.alert_confidence(sigs)
    level = scoring.level_for(score)

    first, last = sigs[0]["_ts"], sigs[-1]["_ts"]
    top = max(sigs, key=lambda s: s["score"])
    sources = sorted({s["source_name"] for s in sigs})
    coords = [(s["lat"], s["lon"]) for s in sigs if s.get("lat") is not None]
    centroid = {"lat": round(mean(c[0] for c in coords), 4), "lon": round(mean(c[1] for c in coords), 4)} if coords else None

    sequence = []
    for c in categories:
        first_c = min(s["_ts"] for s in sigs if s["category"] == c)
        sequence.append({"category": c, "label": CATEGORY_LABELS[c], "first_seen": iso(first_c)})
    sequence.sort(key=lambda x: x["first_seen"])

    labels = [CATEGORY_LABELS[c] for c in categories]
    if is_hybrid:
        title = f"Hybrid threat pattern - {zone}"
    else:
        title = f"{CATEGORY_LABELS[categories[0]]} activity - {zone}" if len(categories) == 1 else f"Multi-domain activity - {zone}"

    span_h = (last - first).total_seconds() / 3600
    summary = (f"{len(sigs)} signal(s) from {len(sources)} source(s) in {zone} over {span_h:.0f}h"
               f" spanning {', '.join(labels)}.")
    if is_hybrid and len(sequence) > 1:
        summary += " Sequence: " + " -> ".join(x["label"] for x in sequence) + "."
    if shared:
        summary += " Linked by " + ", ".join(f"{e['name']} ({e['count']})" for e in shared[:3]) + "."

    return {
        "id": hashlib.sha1(f"{zone}|{sigs[0]['id']}".encode()).hexdigest()[:12],
        "zone": zone,
        "countries": sorted({s["country"] for s in sigs if s.get("country")}),
        "title": title,
        "headline": top["title"],
        "summary": summary,
        "level": level,
        "score": score,
        "confidence": confidence,
        "is_hybrid": is_hybrid,
        "categories": categories,
        "category_counts": category_counts,
        "first_seen": iso(first),
        "last_seen": iso(last),
        "signal_count": len(sigs),
        "source_count": len(sources),
        "sources": sources,
        "synthetic": all(s["synthetic"] for s in sigs),
        "centroid": centroid,
        "breakdown": breakdown,
        "sequence": sequence,
        "shared_entities": shared,
        "ttps": map_ttps(sigs),
        "links": links,
        "signals": [_public(s) for s in sigs],
    }


def replay(alert: dict) -> dict:
    """Re-evaluate the alert as each signal arrived, as if the platform had been running live.

    Answers the key question for an early-warning system: when would we have raised the flag,
    and how long before the first real-world impact?
    """
    sigs = sorted(({**s, "_ts": parse_iso(s["timestamp"])} for s in alert["signals"]), key=lambda s: s["_ts"])
    frames = []
    for i, s in enumerate(sigs):
        state = make_alert(alert["zone"], [dict(x) for x in sigs[: i + 1]], s["_ts"])
        frames.append({
            "t": iso(s["_ts"]), "signal_id": s["id"], "title": s["title"], "category": s["category"],
            "source": s["source_name"], "score": state["score"], "level": state["level"],
            "is_hybrid": state["is_hybrid"], "confidence": state["confidence"],
            "categories": state["categories"], "links": len(state["links"]),
        })

    def first(pred):
        return next((f for f in frames if pred(f)), None)

    impact_sig = next((s for s in sigs if s["category"] == "infrastructure" and s["severity"] >= 0.7), None)
    hybrid = first(lambda f: f["is_hybrid"])
    high = first(lambda f: f["score"] >= 55)
    critical = first(lambda f: f["score"] >= 75)

    def lead(frame):
        if not frame or not impact_sig:
            return None
        return round((impact_sig["_ts"] - parse_iso(frame["t"])).total_seconds() / 3600, 1)

    return {
        "alert_id": alert["id"],
        "zone": alert["zone"],
        "frames": frames,
        "milestones": {
            "first_hybrid": hybrid and {"t": hybrid["t"], "signal_id": hybrid["signal_id"], "lead_hours": lead(hybrid)},
            "first_high": high and {"t": high["t"], "signal_id": high["signal_id"], "lead_hours": lead(high)},
            "first_critical": critical and {"t": critical["t"], "signal_id": critical["signal_id"], "lead_hours": lead(critical)},
            "impact": impact_sig and {"t": iso(impact_sig["_ts"]), "signal_id": impact_sig["id"], "title": impact_sig["title"]},
        },
    }


def build_alerts(signals: list[dict], now: datetime) -> list[dict]:
    prepared = [{**s, "_ts": parse_iso(s["timestamp"])} for s in signals]
    alerts = [make_alert(zone, sigs, now) for zone, sigs in cluster_signals(prepared)]
    alerts.sort(key=lambda a: a["score"], reverse=True)
    return alerts
