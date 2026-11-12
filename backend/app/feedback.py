"""Human-in-the-loop learning: analyst verdicts update source reliability.

Each source keeps its prior reliability as K pseudo-observations. Every alert an analyst
confirms counts as a success for all its sources; every false positive counts as a failure:

    reliability = (prior * K + confirmed) / (K + confirmed + rejected)
"""
from . import db

PRIOR_WEIGHT = 4


def adjusted_reliability(prior: float, confirmed: int, rejected: int) -> float:
    return (prior * PRIOR_WEIGHT + confirmed) / (PRIOR_WEIGHT + confirmed + rejected)


def apply_feedback(signals: list[dict]) -> list[dict]:
    stats = db.source_feedback_stats()
    if not stats:
        return signals
    out = []
    for s in signals:
        st = stats.get(s["source_name"])
        if st:
            prior = s["source_reliability"]
            s = {**s, "source_reliability_prior": prior,
                 "source_reliability": round(adjusted_reliability(prior, st["confirmed"], st["rejected"]), 2),
                 "feedback": st}
        out.append(s)
    return out
