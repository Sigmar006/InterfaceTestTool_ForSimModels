"""
Run router — /api/v1/session/{session_id}/run, /ws/{run_id}, /run/{run_id}/result

Manages test-run lifecycle: code-generation, build, execution, and real-time
WebSocket streaming of build/run output.
"""
from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

# Ensure backend/ is importable as a package root
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from models.schemas import RunOptions, RunRequest, RunResponse  # noqa: E402
from services import codegen_service, runner_service  # noqa: E402
from state import result_store, sessions, ws_queues  # noqa: E402

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/v1", tags=["run"])

_WORKSPACE = Path(__file__).resolve().parent.parent / "workspace"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# POST /session/{session_id}/run
# ---------------------------------------------------------------------------

@router.post(
    "/session/{session_id}/run",
    response_model=RunResponse,
    status_code=202,
)
async def start_run(session_id: str, body: RunRequest) -> RunResponse:
    # 1. Validate session
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    session = sessions[session_id]

    # 2. Validate parse_id
    if body.parse_id not in session["parses"]:
        raise HTTPException(
            status_code=404,
            detail=f"parse_id '{body.parse_id}' not found in session '{session_id}'.",
        )

    parse_result: dict = session["parses"][body.parse_id]

    # 3. Resolve library path
    upload_dir = _WORKSPACE / session_id / "uploads"
    lib_path = upload_dir / body.library_filename
    if not lib_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Library file '{body.library_filename}' not found in session uploads."
            ),
        )

    # Resolve header path — prefer the file already recorded in uploads
    header_path: str | None = None
    for up in session.get("uploads", []):
        if up.get("type") == "header":
            header_path = up["path"]
            break
    if header_path is None:
        raise HTTPException(
            status_code=404,
            detail="No header file found in session uploads.",
        )

    # 4. Generate run_id
    run_id = str(uuid.uuid4())

    # 5. Project output directory
    project_dir = str(_WORKSPACE / session_id / "projects" / run_id)
    Path(project_dir).mkdir(parents=True, exist_ok=True)

    # 6. Serialise test configs for codegen
    test_configs_raw = [tc.model_dump() for tc in body.test_configs]
    options_dict = body.options.model_dump()

    # 7. Run codegen synchronously (fast, no subprocess yet)
    try:
        codegen_service.run_codegen(
            parse_result=parse_result,
            test_configs=test_configs_raw,
            lib_path=str(lib_path),
            header_path=header_path,
            output_dir=project_dir,
            options=options_dict,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Code generation failed: {exc}") from exc

    # 8. Create asyncio queue for this run
    queue: asyncio.Queue = asyncio.Queue()
    ws_queues[run_id] = queue

    # 9. Schedule the pipeline as a background task
    asyncio.create_task(
        runner_service.run_pipeline(
            run_id=run_id,
            project_dir=project_dir,
            options=options_dict,
            ws_queue=queue,
            result_store=result_store,
        ),
        name=f"pipeline-{run_id}",
    )

    # 10. Record run metadata in session
    run_meta = {
        "run_id": run_id,
        "run_at": _now_iso(),
        "overall_status": "queued",
        "summary": {},
        "project_dir": project_dir,
    }
    session["runs"].append(run_meta)

    # 11. Return immediately
    return RunResponse(run_id=run_id, status="queued")


# ---------------------------------------------------------------------------
# WebSocket /ws/{run_id}
# ---------------------------------------------------------------------------

@router.websocket("/ws/{run_id}")
async def websocket_stream(websocket: WebSocket, run_id: str) -> None:
    await websocket.accept()

    # Wait up to 30 s for the queue to appear (in case the client connected
    # before the background task had a chance to register it).
    queue: asyncio.Queue | None = None
    for _ in range(60):  # 60 × 0.5 s = 30 s
        queue = ws_queues.get(run_id)
        if queue is not None:
            break
        await asyncio.sleep(0.5)

    if queue is None:
        await websocket.send_json(
            {"type": "error", "message": f"run_id '{run_id}' not found or timed out."}
        )
        await websocket.close()
        return

    try:
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=60.0)
            except asyncio.TimeoutError:
                # Send a keepalive ping so the browser doesn't time out
                await websocket.send_json({"type": "ping", "timestamp": _now_iso()})
                continue

            if msg is None:
                # Sentinel — pipeline finished
                break

            await websocket.send_json(msg)

            if msg.get("type") in ("done", "error"):
                break

    except WebSocketDisconnect:
        pass  # Client closed connection — nothing to do
    except Exception:
        pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# GET /run/{run_id}/result
# ---------------------------------------------------------------------------

@router.get("/run/{run_id}/result", status_code=200)
async def get_result(run_id: str) -> dict:
    result = result_store.get(run_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Result for run_id '{run_id}' is not available yet or the run_id is invalid."
            ),
        )
    return result
