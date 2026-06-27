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
    # Liveness tracking so the UI can prove the session is alive.
    pid: int | None = None
    started_at: float = 0.0           # time.monotonic() when work began
    last_beat_at: float = 0.0         # updated on every streamed event
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def _now(self) -> float:
        import time
        return time.monotonic()

    def append_progress(self, line: str) -> None:
        with self._lock:
            self.progress.append(line)
            self.last_beat_at = self._now()

    def beat(self) -> None:
        """Mark activity without adding a progress line (heartbeat)."""
        with self._lock:
            self.last_beat_at = self._now()

    def set_pid(self, pid: int | None) -> None:
        with self._lock:
            self.pid = pid
            self.last_beat_at = self._now()

    def set_status(self, status: str, *, error: str | None = None) -> None:
        with self._lock:
            self.status = status
            if status == "running" and not self.started_at:
                self.started_at = self._now()
            if error is not None:
                self.error = error
            if status in ("done", "error", "aborted"):
                self.pid = None

    def to_dict(self, *, since: int = 0) -> dict[str, Any]:
        """Serialize for the client; ``since`` slices the progress tail."""
        with self._lock:
            now = self._now()
            elapsed = round(now - self.started_at, 1) if self.started_at else 0.0
            idle = round(now - self.last_beat_at, 1) if self.last_beat_at else 0.0
            return {
                "id": self.id,
                "kind": self.kind,
                "status": self.status,
                "session_id": self.session_id,
                "result_summary": self.result_summary,
                "error": self.error,
                "meta": self.meta,
                "pid": self.pid,
                "elapsed_sec": elapsed,
                "idle_sec": idle,           # seconds since last activity
                "process": _process_stats(self.pid),
                "progress": self.progress[since:],
                "progress_total": len(self.progress),
            }


def _process_stats(pid: int | None) -> dict[str, Any] | None:
    """Best-effort CPU%/RSS for the Claude subprocess via `ps` (stdlib).

    Returns None if there is no live pid or `ps` is unavailable. Kept
    dependency-free so it works anywhere the CLI runs.
    """
    if not pid:
        return None
    import subprocess
    try:
        out = subprocess.run(
            ["ps", "-o", "%cpu=,rss=", "-p", str(pid)],
            capture_output=True, text=True, timeout=3)
    except (OSError, subprocess.SubprocessError):
        return None
    line = out.stdout.strip()
    if out.returncode != 0 or not line:
        return None
    parts = line.split()
    try:
        cpu = float(parts[0])
        rss_kb = int(parts[1])
    except (ValueError, IndexError):
        return None
    return {"cpu_percent": cpu, "rss_mb": round(rss_kb / 1024, 1)}


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
