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


def start_label(ids: list[str]) -> bool:
    """Label the given reports with the local LLM (they become silver training data)."""
    from ..analyzer import complete_llm

    def run():
        STATE.update(stage="label", total=len(ids))
        labelled, failed, started = 0, 0, time.monotonic()
        for sig in db.fetch_by_ids(ids):
            if not ollama.chat_model():
                raise RuntimeError("the local LLM is not available")
            result = local_llm.analyze(sig["title"], sig["text"])
            if result:
                result = complete_llm(result, sig["title"], sig["text"], {"zone": sig["zone"]} if sig.get("zone") else None)
                db.update_analysis(sig["id"], result)
                labelled += 1
            else:
                failed += 1
            STATE["done"] = labelled + failed
            if labelled + failed in (5, 10) or (labelled + failed) % 20 == 0:
                _notify_change()  # let the board show progress while the job runs
        return {"labelled": labelled, "failed": failed, "seconds": round(time.monotonic() - started)}
    return _start("label", run)


def status() -> dict:
    return dict(STATE)
