"""Background jobs for the local AI, one at a time, with progress the dashboard can show.

  train  embed the labelled reports and train the classifier
  label  let the local LLM label reports that only the keyword rules have seen (grows the dataset)
"""
import logging
import threading
import time

from .. import db
from ..normalize import iso, utcnow
from . import classifier, local_llm, ollama

log = logging.getLogger(__name__)

STATE: dict = {"job": None, "running": False, "stage": None, "done": 0, "total": 0, "started_at": None,
               "finished_at": None, "error": None, "result": None}
_lock = threading.Lock()
_on_change = []  # callbacks run after a job changed stored data (e.g. clear API caches)


def on_change(callback) -> None:
    _on_change.append(callback)


def _notify_change() -> None:
    for cb in _on_change:
        try:
            cb()
        except Exception:  # noqa: BLE001
            log.exception("on_change callback failed")


def _start(job: str, target) -> bool:
    with _lock:
        if STATE["running"]:
            return False
        STATE.update(job=job, running=True, stage="starting", done=0, total=0, started_at=iso(utcnow()),
                     finished_at=None, error=None, result=None)

    def run():
        try:
            STATE["result"] = target()
        except Exception as exc:  # noqa: BLE001 - shown to the user, never crashes the server
            log.exception("%s job failed", job)
            STATE["error"] = f"{type(exc).__name__}: {exc}"[:300] if not isinstance(exc, classifier.TrainError) else str(exc)
        finally:
            STATE.update(running=False, finished_at=iso(utcnow()), stage="finished")
            _notify_change()

    threading.Thread(target=run, name=f"hybridscope-{job}", daemon=True).start()
    return True


def start_train() -> bool:
    def progress(stage: str, done: int, total: int):
        STATE.update(stage=stage, done=done, total=total)
    return _start("train", lambda: classifier.train(progress))


def _picture(sig: dict) -> tuple[str | None, str | None]:
    """(base64 for the model, small preview) of a report's picture, or (None, None)."""
    from .images import fetch, prepare

    if not sig.get("image_url"):
        return None, None
    try:
        return prepare(fetch(sig["image_url"]))
    except Exception as exc:  # noqa: BLE001 - a missing picture never stops labelling
        log.info("picture of %s not usable: %s", sig["id"], exc)
        return None, None


def start_label(ids: list[str], with_images: bool = False) -> bool:
    """Label the given reports with the local LLM (they become silver training data). With images the
    model reads the text and the picture together, and its description of the picture is kept."""
    from ..analyzer import complete_llm

    def run():
        STATE.update(stage="label", total=len(ids))
        labelled, failed, pictures, started = 0, 0, 0, time.monotonic()
        for sig in db.fetch_by_ids(ids):
            if not ollama.chat_model():
                raise RuntimeError("the local LLM is not available")
            b64, preview = _picture(sig) if with_images else (None, None)
            result = local_llm.analyze(sig["title"], sig["text"], image_b64=b64)
            if result and b64 and result.get("image_findings"):
                pictures += 1
                db.image_analysis_put(sig["image_url"], result["analyzer"].removeprefix("ollama:"), {
                    "description": result["image_findings"], "visible_text": "", "category": result["category"],
                    "threat_relevant": result["category"] != "other", "signs_of_manipulation": [],
                    "confidence": result["confidence"]}, preview, iso(utcnow()))
            if result:
                result = complete_llm(result, sig["title"], sig["text"], {"zone": sig["zone"]} if sig.get("zone") else None)
                db.update_analysis(sig["id"], result)
                labelled += 1
            else:
                failed += 1
            STATE["done"] = labelled + failed
            if labelled + failed in (5, 10) or (labelled + failed) % 20 == 0:
                _notify_change()  # let the board show progress while the job runs
        return {"labelled": labelled, "failed": failed, "pictures": pictures, "seconds": round(time.monotonic() - started)}
    return _start("label", run)


def status() -> dict:
    return dict(STATE)
