"""Entity network: alerts <-> the actors, organisations, technologies, CVEs and narratives they share.

Entities that bridge several alerts (e.g. the same platform or actor in two regions) stand out
as hubs - something a list view cannot show.
"""
from collections import defaultdict

ENTITY_TYPES = {"actors": "actor", "orgs": "organisation", "technologies": "technology", "cves": "CVE", "narratives": "narrative"}


def build_graph(alerts: list[dict], max_entities: int = 70) -> dict:
    totals: dict[tuple, int] = defaultdict(int)
    display: dict[tuple, str] = {}
    per_alert: dict[str, dict[tuple, int]] = {}

    for a in alerts:
        counts: dict[tuple, int] = defaultdict(int)
        for s in a["signals"]:
            for etype, label in ENTITY_TYPES.items():
                for name in {n.strip() for n in s["entities"].get(etype) or [] if n.strip()}:
                    key = (label, name.lower())
                    counts[key] += 1
                    display.setdefault(key, name)
        per_alert[a["id"]] = counts
        for key, n in counts.items():
            totals[key] += n

    keep = {k for k, n in sorted(totals.items(), key=lambda kv: -kv[1]) if n >= 2}
    keep = set(sorted(keep, key=lambda k: -totals[k])[:max_entities])

    nodes, edges = [], []
    bridges: dict[tuple, int] = defaultdict(int)
    for a in alerts:
        linked = {k: n for k, n in per_alert[a["id"]].items() if k in keep}
        if not linked:
            continue
        nodes.append({"id": f"a:{a['id']}", "kind": "alert", "label": a["zone"], "alert_id": a["id"],
                      "level": a["level"], "score": a["score"], "is_hybrid": a["is_hybrid"], "synthetic": a["synthetic"]})
        for key, n in linked.items():
            edges.append({"source": f"a:{a['id']}", "target": f"e:{key[0]}:{key[1]}", "weight": n})
            bridges[key] += 1

    used = {e["target"] for e in edges}
    for key in keep:
        nid = f"e:{key[0]}:{key[1]}"
        if nid in used:
            nodes.append({"id": nid, "kind": "entity", "type": key[0], "label": display[key],
                          "count": totals[key], "alerts": bridges[key]})
    return {"nodes": nodes, "edges": edges}
