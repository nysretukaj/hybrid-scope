"""Explainable risk scoring.

Alert score (0-100) is a weighted sum of five components in [0, 1]; each component's
contribution is returned so the analyst can see exactly why an alert ranks where it does.
"""
from datetime import datetime
from statistics import mean

from .config import RECENCY_HALF_LIFE_HOURS
from .normalize import parse_iso

WEIGHTS = {"severity": 0.35, "hybrid": 0.25, "corroboration": 0.15, "recency": 0.15, "reliability": 0.10}
LABELS = {
    "severity": "Severity",
    "hybrid": "Hybrid (cross-domain)",
    "corroboration": "Corroboration",
    "recency": "Recency",
    "reliability": "Source reliability",
}
LEVELS = [(75, "CRITICAL"), (55, "HIGH"), (35, "MEDIUM"), (0, "LOW")]


def age_hours(sig: dict, now: datetime) -> float:
    ts = sig.get("_ts") or parse_iso(sig["timestamp"])
    return max(0.0, (now - ts).total_seconds() / 3600)


def recency_weight(age_h: float) -> float:
    return max(0.02, 0.5 ** (age_h / RECENCY_HALF_LIFE_HOURS))


def signal_score(sig: dict, now: datetime) -> float:
    """Per-signal priority used to order evidence: severity x reliability x recency."""
    rel = 0.5 + 0.5 * sig["source_reliability"]
    return round(100 * sig["severity"] * rel * recency_weight(age_hours(sig, now)), 1)


def level_for(score: float) -> str:
    return next(name for threshold, name in LEVELS if score >= threshold)


def alert_confidence(signals: list[dict]) -> float:
    """Noisy-OR over independent sources: each extra independent source raises confidence."""
    best_per_source: dict[str, float] = {}
    for s in signals:
        p = s["source_reliability"] * s["confidence"]
        best_per_source[s["source_name"]] = max(best_per_source.get(s["source_name"], 0), p)
    miss = 1.0
    for p in best_per_source.values():
        miss *= 1 - p
    return round(min(0.99, 1 - miss), 2)


def score_alert(signals: list[dict], categories: list[str], is_hybrid: bool, corroborating_sources: int, now: datetime):
    sev = [s["severity"] for s in signals]
    latest_age = min(age_hours(s, now) for s in signals)
    rel = mean(s["source_reliability"] for s in signals)
    n_cats = len(categories) if is_hybrid else 1

    components = {
        "severity": (0.6 * max(sev) + 0.4 * mean(sev),
                     f"Peak severity {max(sev):.2f}, mean {mean(sev):.2f} across {len(signals)} signal(s)"),
        "hybrid": ((n_cats - 1) / 3,
                   f"{len(categories)} linked threat domain(s)" if is_hybrid else "Single threat domain - no cross-domain link"),
        "corroboration": (min(1.0, (corroborating_sources - 1) / 4),
                          f"{corroborating_sources} independent source(s) share actors, narratives or infrastructure"),
        "recency": (recency_weight(latest_age),
                    f"Latest signal {latest_age:.0f}h ago (half-life {RECENCY_HALF_LIFE_HOURS:.0f}h)"),
        "reliability": (rel, f"Mean source reliability {rel:.2f}"),
    }

    breakdown, total = [], 0.0
    for key, weight in WEIGHTS.items():
        value, explanation = components[key]
        points = 100 * weight * value
        total += points
        breakdown.append({
            "key": key, "label": LABELS[key], "weight": weight, "value": round(value, 3),
            "points": round(points, 1), "max_points": round(100 * weight, 1), "explanation": explanation,
        })
    return round(total, 1), breakdown
