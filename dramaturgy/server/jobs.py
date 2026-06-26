"""In-memory job registry for long-running Claude Code invocations.

A job tracks one headless ``claude`` subprocess: its status, streamed
progress lines, the prompt that started it, and the resulting session id
(so a follow-up can ``--resume``). The browser polls ``/api/jobs/<id>``
for progress (polling, not SSE — robust behind buffering proxies, same
choice rr made).

Thread-safe: the runner thread appends progress while request threads read.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

# Lifecycle: queued -> running -> (done | error | aborted)
STATUSES = ("queued", "running", "done", "error", "aborted")


@dataclass
class Job:
    id: str
    kind: str                     # e.g. "area_tree", "area_card"
    prompt: str
    status: str = "queued"
    progress: list[str] = field(default_factory=list)
    session_id: str | None = None
    result_summary: str = ""
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def append_progress(self, line: str) -> None:
        with self._lock:
            self.progress.append(line)

    def set_status(self, status: str, *, error: str | None = None) -> None:
        with self._lock:
            self.status = status
            if error is not None:
                self.error = error

    def to_dict(self, *, since: int = 0) -> dict[str, Any]:
        """Serialize for the client; ``since`` slices the progress tail."""
        with self._lock:
            return {
                "id": self.id,
                "kind": self.kind,
                "status": self.status,
                "session_id": self.session_id,
                "result_summary": self.result_summary,
                "error": self.error,
                "meta": self.meta,
                "progress": self.progress[since:],
                "progress_total": len(self.progress),
            }


class JobRegistry:
    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._counter = 0
        self._lock = threading.Lock()

    def create(self, kind: str, prompt: str, meta: dict | None = None) -> Job:
        with self._lock:
            self._counter += 1
            job_id = f"job-{self._counter}"
            job = Job(id=job_id, kind=kind, prompt=prompt, meta=meta or {})
            self._jobs[job_id] = job
            return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())
