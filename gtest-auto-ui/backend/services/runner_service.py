"""
Runner service — async wrapper around runner/runner.py.

Streams build/run output over an asyncio.Queue so the WebSocket router can
forward messages to the browser in real time.

Path layout:
    __file__  = .../InterfaceTestTool/gtest-auto-ui/backend/services/runner_service.py
    ROOT      = parent x4  →  .../InterfaceTestTool/
"""
from __future__ import annotations

import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: make runner importable
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent.parent  # InterfaceTestTool/
_RUNNER_DIR = str(ROOT / "runner")
if _RUNNER_DIR not in sys.path:
    sys.path.insert(0, _RUNNER_DIR)

import runner as _runner_module  # noqa: E402


# ---------------------------------------------------------------------------
# Module-level thread pool shared across all pipeline invocations
# ---------------------------------------------------------------------------
_executor = ThreadPoolExecutor(max_workers=4)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_stage_start(stage: str) -> dict:
    return {"type": "stage_start", "stage": stage, "timestamp": _now_iso()}


def _make_stage_done(stage: str) -> dict:
    return {"type": "stage_done", "stage": stage, "timestamp": _now_iso()}


def _make_log(stage: str, stream: str, line: str) -> dict:
    return {
        "type": "log",
        "stage": stage,
        "stream": stream,
        "line": line,
        "timestamp": _now_iso(),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def run_pipeline(
    run_id: str,
    project_dir: str,
    options: dict,
    ws_queue: asyncio.Queue,
    result_store: dict,
) -> None:
    """
    Execute build_and_run() in a thread-pool executor and stream progress
    messages through *ws_queue*.

    Message protocol
    ----------------
    stage_start  {"type": "stage_start", "stage": str, "timestamp": str}
    stage_done   {"type": "stage_done",  "stage": str, "timestamp": str}
    log          {"type": "log", "stage": str, "stream": "stdout"|"stderr",
                  "line": str, "timestamp": str}
    done         {"type": "done", "result": dict}
    error        {"type": "error", "message": str}
    sentinel     None  — always the very last item; signals completion
    """
    loop = asyncio.get_event_loop()

    def _put(msg: object) -> None:
        """Thread-safe enqueue from the worker thread."""
        loop.call_soon_threadsafe(ws_queue.put_nowait, msg)

    # Stage tracking shared across the on_output callback
    state: dict = {"current_stage": None}

    def _emit_stage(new_stage: str) -> None:
        """Emit stage_done + stage_start when the stage changes."""
        if state["current_stage"] == new_stage:
            return
        if state["current_stage"] is not None:
            _put(_make_stage_done(state["current_stage"]))
        state["current_stage"] = new_stage
        _put(_make_stage_start(new_stage))

    def on_output(stage: str, stream: str, line: str) -> None:
        """Callback invoked by build_and_run() for each output line."""
        _emit_stage(stage)
        _put(_make_log(stage, stream, line))

    def _blocking_run() -> dict:
        """Runs in a thread-pool worker."""
        _emit_stage("configure")
        opts = dict(options)
        opts["on_output"] = on_output
        return _runner_module.build_and_run(project_dir, opts)

    try:
        result: dict = await loop.run_in_executor(_executor, _blocking_run)

        # Close last stage
        if state["current_stage"] is not None:
            _put(_make_stage_done(state["current_stage"]))

        result_store[run_id] = result
        _put({"type": "done", "result": result})

    except Exception as exc:
        _put({"type": "error", "message": str(exc)})

    finally:
        # Sentinel — always last; WebSocket consumer breaks its loop on this
        _put(None)
