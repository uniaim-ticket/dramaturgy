"""Run Claude Code as a headless subprocess and stream its progress.

Mirrors requirements-reviewer: invoke

    claude -p "<prompt>" \
      --output-format stream-json --verbose \
      --permission-mode acceptEdits [--resume <session>] \
      --add-dir <repo_root>

parse the stream-json lines for progress + the final session id, and record
everything on a :class:`~dramaturgy.server.jobs.Job`. ``acceptEdits`` is the
default because a headless run cannot answer interactive permission prompts,
so Claude must be allowed to write the JSON artifacts in the workspace.

The actual command is configurable (``claude_bin`` / ``extra_args``) and the
spawn function is injectable, so tests run without a real Claude binary.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from typing import Callable, Sequence

from .jobs import Job

# A spawn function takes argv and returns a Popen-like object with a
# line-iterable ``stdout`` and a ``wait()`` returning an exit code.
SpawnFn = Callable[[Sequence[str]], subprocess.Popen]


def default_spawn(argv: Sequence[str]) -> subprocess.Popen:
    return subprocess.Popen(
        list(argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,  # line-buffered
    )


def preflight(claude_bin: str = "claude") -> tuple[bool, str]:
    """Check that the Claude CLI is available before a long run."""
    path = shutil.which(claude_bin)
    if not path:
        return False, f"'{claude_bin}' not found on PATH"
    try:
        out = subprocess.run(
            [claude_bin, "--version"], capture_output=True, text=True, timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"failed to run '{claude_bin} --version': {exc}"
    if out.returncode != 0:
        return False, out.stderr.strip() or "claude --version failed"
    return True, out.stdout.strip()


def build_argv(
    prompt: str,
    repo_root: str,
    *,
    claude_bin: str = "claude",
    permission_mode: str = "acceptEdits",
    resume_session: str | None = None,
    extra_args: Sequence[str] = (),
) -> list[str]:
    argv = [
        claude_bin, "-p", prompt,
        "--output-format", "stream-json",
        "--verbose",
        "--permission-mode", permission_mode,
        "--add-dir", repo_root,
    ]
    if resume_session:
        argv += ["--resume", resume_session]
    argv += list(extra_args)
    return argv


def _summarize_event(event: dict) -> str | None:
    """Turn one stream-json event into a short human progress line."""
    etype = event.get("type")
    if etype == "system" and event.get("subtype") == "init":
        return "session started"
    if etype == "assistant":
        # Assistant message may contain text and/or tool_use blocks.
        msg = event.get("message", {})
        for block in msg.get("content", []):
            if block.get("type") == "text" and block.get("text", "").strip():
                text = block["text"].strip().splitlines()[0]
                return f"claude: {text[:200]}"
            if block.get("type") == "tool_use":
                return f"tool: {block.get('name', '?')}"
        return None
    if etype == "result":
        if event.get("is_error"):
            return f"error: {event.get('subtype', 'unknown')}"
        return "result received"
    return None


def stream_claude(
    job: Job,
    prompt: str,
    repo_root: str,
    *,
    claude_bin: str = "claude",
    permission_mode: str = "acceptEdits",
    resume_session: str | None = None,
    extra_args: Sequence[str] = (),
    spawn: SpawnFn = default_spawn,
) -> tuple[bool, str | None]:
    """Run one headless Claude invocation, streaming progress into ``job``.

    Appends progress and updates ``job.session_id``/``result_summary`` but does
    NOT set a terminal job status — the caller decides, so several invocations
    can share one job (used by the pipeline). Returns ``(ok, error)``.
    """
    argv = build_argv(
        prompt, repo_root,
        claude_bin=claude_bin, permission_mode=permission_mode,
        resume_session=resume_session, extra_args=extra_args,
    )
    job.append_progress(f"$ {claude_bin} -p … --permission-mode {permission_mode}")

    try:
        proc = spawn(argv)
    except OSError as exc:
        return False, f"failed to start claude: {exc}"

    # Record the subprocess pid so the UI can show it's alive (CPU/RSS).
    job.set_pid(getattr(proc, "pid", None))

    saw_result = False
    result_error: str | None = None
    seen_api_error = False
    for raw in proc.stdout:  # type: ignore[union-attr]
        job.beat()  # heartbeat: we received output, the session is alive
        line = raw.rstrip("\n")
        if not line:
            continue
        if "API Error" in line or "Overloaded" in line:
            seen_api_error = True
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            job.append_progress(line[:500])
            continue
        if event.get("type") == "system" and event.get("session_id"):
            job.session_id = event["session_id"]
        if event.get("type") == "result":
            saw_result = True
            job.result_summary = (
                event.get("result") or event.get("subtype") or "")[:500]
            if event.get("session_id"):
                job.session_id = event["session_id"]
            if event.get("is_error") or event.get("subtype") not in (
                    None, "success"):
                result_error = (event.get("result")
                                or event.get("subtype") or "error")[:300]
        summary = _summarize_event(event)
        if summary:
            job.append_progress(summary)

    code = proc.wait()
    job.set_pid(None)  # subprocess has exited
    if result_error:
        return False, result_error
    if code != 0:
        # An API error often surfaces only as a non-zero exit.
        hint = " (API error)" if seen_api_error else ""
        return False, f"claude exited with code {code}{hint}"
    if not saw_result:
        return False, "claude ended without a result event"
    return True, None


# Substrings that mark a transient, retryable failure (vs. a real error).
TRANSIENT_MARKERS = (
    "api error", "overloaded", "rate limit", "timeout", "timed out",
    "503", "502", "529", "connection", "unexpected error",
)


def _is_transient(error: str | None) -> bool:
    if not error:
        return False
    low = error.lower()
    return any(m in low for m in TRANSIENT_MARKERS)


def stream_claude_with_retry(
    job: Job,
    prompt: str,
    repo_root: str,
    *,
    max_attempts: int = 3,
    sleep: Callable[[float], None] | None = None,
    **kwargs,
) -> tuple[bool, str | None]:
    """stream_claude with backoff on transient API errors.

    Resumes the same session between attempts when possible, so a retry
    continues rather than restarting. Non-transient errors fail immediately.
    """
    import time
    sleep = sleep or time.sleep
    resume = kwargs.pop("resume_session", None)
    last_error: str | None = None
    for attempt in range(1, max_attempts + 1):
        ok, error = stream_claude(
            job, prompt, repo_root, resume_session=resume, **kwargs)
        if ok:
            return True, None
        last_error = error
        # Prefer resuming the session that was established, if any.
        resume = job.session_id or resume
        if attempt < max_attempts and _is_transient(error):
            backoff = 2.0 * attempt
            job.append_progress(
                f"transient error (attempt {attempt}/{max_attempts}): "
                f"{error} — retrying in {backoff:.0f}s")
            sleep(backoff)
            continue
        break
    return False, last_error


def run_job(
    job: Job,
    repo_root: str,
    *,
    claude_bin: str = "claude",
    permission_mode: str = "acceptEdits",
    resume_session: str | None = None,
    extra_args: Sequence[str] = (),
    spawn: SpawnFn = default_spawn,
) -> None:
    """Run one single-invocation job to completion (blocking, for a thread).

    Retries transient API errors. Updates the job's status/progress/session_id
    in place.
    """
    job.set_status("running")
    ok, error = stream_claude_with_retry(
        job, job.prompt, repo_root,
        claude_bin=claude_bin, permission_mode=permission_mode,
        resume_session=resume_session, extra_args=extra_args, spawn=spawn)
    if ok:
        job.set_status("done")
    else:
        status = "aborted" if error and "without a result" in error else "error"
        job.set_status(status, error=error)


def start_job_thread(job: Job, repo_root: str, **kwargs) -> threading.Thread:
    thread = threading.Thread(
        target=run_job, args=(job, repo_root), kwargs=kwargs, daemon=True)
    thread.start()
    return thread
