"""
process_manager.py — Subprocess execution with real-time output streaming.

Design rules
------------
* Never uses shell=True or os.system()
* stdout and stderr are read concurrently via background threads so neither
  pipe blocks
* On timeout the process tree is killed and wait()-ed (no zombie processes)
* on_output callback is called per-line, not buffered until exit
"""
from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from typing import Callable


def run_process(
    cmd: list[str],
    cwd: str | None = None,
    env: dict | None = None,
    timeout: float = 300.0,
    on_output: Callable[[str, str, str], None] | None = None,
    stage: str = "",
) -> tuple[int, str, str, bool]:
    """
    Run *cmd* as a subprocess and return (exit_code, stdout, stderr, timed_out).

    Args:
        cmd        - Command list (no shell expansion).
        cwd        - Working directory for the subprocess.
        env        - Full environment dict; defaults to the current process env.
        timeout    - Seconds before the process is killed.
        on_output  - Optional callback(line, stream, stage) called per output line.
        stage      - Stage label passed to the callback ("configure"/"build"/"test").

    Returns:
        (exit_code, stdout_text, stderr_text, timed_out)
        exit_code is -1 when timed out.
    """
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    def _reader(stream, lines: list[str], stream_name: str) -> None:
        try:
            for raw_line in stream:
                line = raw_line.rstrip("\r\n")
                lines.append(line)
                if on_output is not None:
                    try:
                        on_output(line, stream_name, stage)
                    except Exception:
                        pass  # never crash due to a bad callback
        finally:
            stream.close()

    t_out = threading.Thread(
        target=_reader, args=(proc.stdout, stdout_lines, "stdout"), daemon=True
    )
    t_err = threading.Thread(
        target=_reader, args=(proc.stderr, stderr_lines, "stderr"), daemon=True
    )
    t_out.start()
    t_err.start()

    timed_out = False
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_process_tree(proc)
        proc.wait()

    t_out.join(timeout=5.0)
    t_err.join(timeout=5.0)

    exit_code = proc.returncode if not timed_out else -1
    return exit_code, "\n".join(stdout_lines), "\n".join(stderr_lines), timed_out


# ---------------------------------------------------------------------------
# Process tree kill (handles Windows and POSIX)
# ---------------------------------------------------------------------------

def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill the process and, on POSIX, its entire process group."""
    try:
        if sys.platform == "win32":
            # taskkill kills child processes too
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True,
            )
        else:
            import signal
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                proc.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
