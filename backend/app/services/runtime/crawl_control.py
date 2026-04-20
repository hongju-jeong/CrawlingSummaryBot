from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir
from threading import Lock
from uuid import uuid4


@dataclass(slots=True)
class ActiveCrawlRun:
    run_id: str
    cancel_token: str


class CrawlRunRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._active_run: ActiveCrawlRun | None = None

    def start(self) -> ActiveCrawlRun | None:
        with self._lock:
            if self._active_run is not None:
                return None
            run_id = str(uuid4())
            cancel_token = str(Path(gettempdir()) / f"ai_issue_crawl_cancel_{run_id}.flag")
            _clear_token(cancel_token)
            run = ActiveCrawlRun(run_id=run_id, cancel_token=cancel_token)
            self._active_run = run
            return run

    def stop(self) -> bool:
        with self._lock:
            if self._active_run is None:
                return False
            Path(self._active_run.cancel_token).touch()
            return True

    def finish(self, run_id: str) -> None:
        with self._lock:
            if self._active_run and self._active_run.run_id == run_id:
                _clear_token(self._active_run.cancel_token)
                self._active_run = None

    def current(self) -> ActiveCrawlRun | None:
        with self._lock:
            return self._active_run


registry = CrawlRunRegistry()


def is_cancelled(cancel_token: str | None) -> bool:
    return bool(cancel_token and Path(cancel_token).exists())


def _clear_token(cancel_token: str) -> None:
    path = Path(cancel_token)
    if path.exists():
        path.unlink()
