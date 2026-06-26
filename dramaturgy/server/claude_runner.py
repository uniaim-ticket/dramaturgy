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

    saw_result = False
    for raw in proc.stdout:  # type: ignore[union-attr]
        line = raw.rstrip("\n")
        if not line:
            continue
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
        summary = _summarize_event(event)
        if summary:
            job.append_progress(summary)

    code = proc.wait()
    if code != 0:
        return False, f"claude exited with code {code}"
    if not saw_result:
        return False, "claude ended without a result event"
    return True, None


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

    Updates the job's status/progress/session_id in place. stream-json lines
    are parsed for progress; non-JSON lines are recorded verbatim so nothing
    is silently dropped.
    """
    job.set_status("running")
    ok, error = stream_claude(
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
