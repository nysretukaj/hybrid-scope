"""A model trained on our own data: category, cause and claim of a report.

Features: multilingual bge-m3 embeddings from the local Ollama server; without Ollama the model
falls back to TF-IDF on words and character n-grams (still works offline, on any machine).
Model: logistic regression with balanced class weights, gold labels weighted 3x.

Training is honest about quality: it is fitted on the train split, measured on the held-out
validation split (accuracy, macro-F1, per-class scores, and the keyword rules on the same texts
as a baseline), and only then refitted on all labelled data for use.
"""
import json
import logging
import shutil
import time
from collections import Counter
from collections.abc import Callable

import numpy as np

from .. import config
from ..normalize import iso, utcnow
from . import dataset, embeddings, ollama

log = logging.getLogger(__name__)

HEADS = ("category", "cause", "claim")
MIN_RECORDS = 30
MIN_CLASS_SIZE = 3
VERSION = 1
_CACHE: dict = {"mtime": None, "bundle": None}


class TrainError(RuntimeError):
    """Not enough data (or no usable labels) to train."""


def _paths():
    return config.MODELS_DIR / "classifier.joblib", config.MODELS_DIR / "classifier.json"


def _estimator(kind: str):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import FeatureUnion, Pipeline

    if kind == "embeddings":
        return LogisticRegression(max_iter=4000, class_weight="balanced", C=4.0)
    features = FeatureUnion([
        ("words", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, max_features=40000)),
        ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=2, max_features=60000)),
    ])
    return Pipeline([("features", features), ("model", LogisticRegression(max_iter=4000, class_weight="balanced", C=8.0))])


def _metrics(y_true: list, y_pred: list) -> dict:
    from sklearn.metrics import accuracy_score, classification_report, f1_score

    labels = sorted(set(y_true) | set(y_pred))
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 3),
        "macro_f1": round(float(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0)), 3),
        "support": len(y_true),
        "per_class": {c: {k: round(float(report[c][k]), 3) for k in ("precision", "recall", "f1-score", "support")}
                      for c in labels if c in report},
    }


def _rows(X, idx):
    return X[idx] if isinstance(X, np.ndarray) else [X[i] for i in idx]


def _operating_point(kind: str, X, rows: list[int], y: list[str], weights: np.ndarray) -> dict:
    """How sure must the model be so that its own decisions are right at least TARGET of the time?

    Every labelled report is predicted once while it is left out of training (k-fold cross-validation).
    For each certainty threshold we measure precision (share of correct decisions above it) and coverage
    (share of reports it decides); the lowest threshold that reaches the target is used. Below it the
    model does not decide: the rules, the local AI or an analyst do."""
    from sklearn.model_selection import StratifiedKFold, cross_val_predict

    target = config.CLASSIFIER_TARGET_PRECISION
    k = max(2, min(5, min(Counter(y).values())))
    cv = StratifiedKFold(n_splits=k, shuffle=True, random_state=42)
    params = {"model__sample_weight": weights[rows]} if kind == "tfidf" else {"sample_weight": weights[rows]}
    proba = cross_val_predict(_estimator(kind), _rows(X, rows), y, cv=cv, method="predict_proba", params=params)
    classes = sorted(set(y))  # predict_proba columns follow the sorted class labels
    pred = [classes[j] for j in proba.argmax(axis=1)]
    conf = proba.max(axis=1)
    correct = np.asarray([p == t for p, t in zip(pred, y)])

    curve, chosen = [], None
    min_decided = max(10, round(0.05 * len(y)))
    for t in np.round(np.arange(0.5, 0.995, 0.01), 2):
        decided = conf >= t
        if decided.sum() < min_decided:
            break
        precision = float(correct[decided].mean())
        point = {"threshold": float(t), "precision": round(precision, 3), "coverage": round(float(decided.mean()), 3),
                 "decided": int(decided.sum())}
        if t in (0.5, 0.6, 0.7, 0.8, 0.9, 0.95):
            curve.append(point)
        if chosen is None and precision >= target:
            chosen = point
    cv_metrics = {k2: v for k2, v in _metrics(y, pred).items() if k2 != "per_class"}
    return {"cross_validated": {**cv_metrics, "folds": k}, "operating_point": chosen, "curve": curve,
            "target_precision": target}


def decision_threshold() -> float | None:
    """Certainty above which the trained model may decide on its own (None: it never decides alone)."""
    meta = info()
    op = ((meta or {}).get("metrics", {}).get("category") or {}).get("operating_point")
    if not op:
        return None
    return max(config.CLASSIFIER_MIN_PROB, op["threshold"])


def train(progress: Callable[[str, int, int], None] | None = None) -> dict:
    from ..analyzer.local import analyze_local

    def report(stage: str, done: int = 0, total: int = 0):
        if progress:
            progress(stage, done, total)

    report("dataset")
    records = [r for r in dataset.build() if r["weight"] > 0]
    if len(records) < MIN_RECORDS:
        raise TrainError(f"need at least {MIN_RECORDS} labelled reports, have {len(records)}")
    if len({r["category"] for r in records}) < 2:
        raise TrainError("need at least two different categories")

    kind, X = "tfidf", [r["text"] for r in records]
    if ollama.embed_model():
        report("embeddings", 0, len(records))
        vecs = embeddings.vectors([r["text"] for r in records], lambda d, t: report("embeddings", d, t))
        if vecs is not None:
            kind, X = "embeddings", vecs
    weights = np.asarray([r["weight"] for r in records], dtype=float)
    train_idx = [i for i, r in enumerate(records) if r["split"] == "train"]
    val_idx = [i for i, r in enumerate(records) if r["split"] == "val"]
    if len(val_idx) < 8 or len(train_idx) < MIN_RECORDS - 8:
        raise TrainError("the validation split is too small; collect more labelled reports")

    heads, metrics = {}, {}
    for h_i, head in enumerate(HEADS):
        report(f"train:{head}", h_i, len(HEADS))
        labels = [r.get(head) for r in records]
        counts = Counter(lab for lab in labels if lab)
        keep_classes = {c for c, n in counts.items() if n >= MIN_CLASS_SIZE}
        rows = [i for i, lab in enumerate(labels) if lab in keep_classes]
        if len(keep_classes) < 2 or len(rows) < MIN_RECORDS:
            continue  # not enough variety for this head yet
        row_set = set(rows)
        tr = [i for i in train_idx if i in row_set]
        va = [i for i in val_idx if i in row_set]
        if len({labels[i] for i in tr}) < 2 or not va:
            continue
        est = _estimator(kind)
        fit_kw = {"model__sample_weight": weights[tr]} if kind == "tfidf" else {"sample_weight": weights[tr]}
        est.fit(_rows(X, tr), [labels[i] for i in tr], **fit_kw)
        pred = list(est.predict(_rows(X, va)))
        m = _metrics([labels[i] for i in va], pred)
        if head == "category":
            # the keyword rules on the very same validation texts, for comparison
            rule = [analyze_local(records[i]["title"], records[i]["text"])["category"] for i in va]
            m["rules_baseline"] = {k: v for k, v in _metrics([labels[i] for i in va], rule).items() if k != "per_class"}
            m.update(_operating_point(kind, X, rows, [labels[i] for i in rows], weights))
        metrics[head] = m
        final = _estimator(kind)
        fit_all = {"model__sample_weight": weights[rows]} if kind == "tfidf" else {"sample_weight": weights[rows]}
        final.fit(_rows(X, rows), [labels[i] for i in rows], **fit_all)
        heads[head] = final

    if "category" not in heads:
        raise TrainError("could not train the category model (too few examples per category)")

    import joblib

    model_path, meta_path = _paths()
    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if model_path.exists():  # keep the previous model so a worse one can be rolled back by hand
        shutil.copy2(model_path, model_path.with_suffix(".prev.joblib"))
    meta = {
        "version": VERSION, "trained_at": iso(utcnow()), "features": kind,
        "embed_model": ollama.embed_model() if kind == "embeddings" else None,
        "records": len(records), "train": len(train_idx), "validation": len(val_idx),
        "by_quality": dict(Counter(r["quality"] for r in records)),
        "by_category": dict(Counter(r["category"] for r in records)),
        "heads": list(heads), "metrics": metrics,
    }
    joblib.dump({"meta": meta, "heads": heads}, model_path)
    meta_path.write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    _CACHE.update(mtime=None, bundle=None)
    report("done", len(HEADS), len(HEADS))
    return meta


def info() -> dict | None:
    _, meta_path = _paths()
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _load():
    model_path, _ = _paths()
    try:
        mtime = model_path.stat().st_mtime
    except OSError:
        return None
    if _CACHE["mtime"] != mtime:
        import joblib

        try:
            _CACHE.update(bundle=joblib.load(model_path), mtime=mtime)
        except Exception as exc:  # noqa: BLE001 - a broken file must not break analysis
            log.warning("could not load the trained model: %s", exc)
            _CACHE.update(bundle=None, mtime=mtime)
    return _CACHE["bundle"]


def predict(texts: list[str], allow_embeddings: bool = True) -> list[dict] | None:
    """Per text: {head: {"label", "prob"}}. None when no model is trained or its features are unavailable.
    allow_embeddings=False skips an embeddings model (computing vectors on a CPU takes time)."""
    bundle = _load()
    if not bundle or not texts:
        return None
    if bundle["meta"]["features"] == "embeddings":
        if not allow_embeddings:
            return None
        X = embeddings.vectors(texts)
        if X is None:
            return None
    else:
        X = texts
    out = [{} for _ in texts]
    for head, est in bundle["heads"].items():
        proba = est.predict_proba(X)
        classes = list(est.classes_)
        for i, row in enumerate(proba):
            j = int(np.argmax(row))
            out[i][head] = {"label": classes[j], "prob": round(float(row[j]), 3)}
    return out


def uses_embeddings() -> bool:
    bundle = _load()
    return bool(bundle) and bundle["meta"]["features"] == "embeddings"


def refine(items: list[tuple[str, str]], analyses: list[dict], allow_embeddings: bool = True) -> int:
    """Let the trained model correct the keyword rules where it is confident. Returns how many changed."""
    from ..assess import classify_extra
    from ..i18n import cat_label, tr

    started = time.monotonic()
    preds = predict([dataset.model_text(t, x) for t, x in items], allow_embeddings)
    if not preds:
        return 0
    threshold = decision_threshold()  # None: the model never reached the target precision, so it never decides
    changed = 0
    for (title, text), a, p in zip(items, analyses, preds):
        a["ml"] = p
        cat = p.get("category")
        if threshold is None or not cat or cat["prob"] < threshold or cat["label"] == a["category"]:
            continue
        new, old = cat["label"], a["category"]
        a.update(classify_extra(new, title, text))
        a["tags"] = [t for t in a.get("tags", []) if t != new]
        a["category"] = new
        if new != "other":
            a["severity"] = max(a["severity"], 0.3)
        a["analyzer"] = "local-ml"
        pct = round(cat["prob"] * 100)
        # the rules' "no threat indicators" sentence would contradict the model: replace it instead of appending
        keep = old != "other"
        a["rationale"] = (((a.get("rationale") or "") if keep else "") + tr("nlp.model", "en", cat=cat_label(new, "en"), p=pct)).strip()
        for lang in ("sq", "de"):
            entry = a.setdefault("i18n", {}).setdefault(lang, {})
            entry["rationale"] = (((entry.get("rationale") or "") if keep else "")
                                  + tr("nlp.model", lang, cat=cat_label(new, lang), p=pct)).strip()
        changed += 1
    log.info("trained model checked %s reports in %.1fs, changed %s", len(items), time.monotonic() - started, changed)
    return changed


def refine_stored(ids: list[str]) -> int:
    """Background pass over freshly stored reports (used when the model needs embeddings, which are slow
    on a CPU). Only reports still labelled by the rules alone are touched, so an LLM label that arrived
    in the meantime is never overwritten."""
    from .. import db

    sigs = [s for s in db.fetch_by_ids(ids) if s["analyzer"] == "local-nlp"]
    if not sigs:
        return 0
    analyses = [{k: s.get(k) for k in ("category", "tags", "severity", "confidence", "analyzer", "rationale",
                                       "entities", "i18n", "subcategory", "cause", "claim", "target")} for s in sigs]
    refine([(s["title"], s["text"]) for s in sigs], analyses)
    changed = 0
    for s, a in zip(sigs, analyses):
        if a["analyzer"] == "local-ml" and db.update_analysis(s["id"], a, only_if_analyzer="local-nlp"):
            changed += 1
    return changed
