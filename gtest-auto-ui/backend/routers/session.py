"""
Session router — /api/v1/session endpoints.

Handles session creation, file uploads, and per-session run history.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

# Make sure backend/ is on the path so sibling imports work when the
# router is loaded outside of the package (e.g. during testing).
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from models.schemas import (  # noqa: E402
    HistoryResponse,
    RunSummary,
    SessionResponse,
    UploadedFile,
    UploadResponse,
)
from state import sessions  # noqa: E402

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/v1", tags=["session"])

# Workspace root — two levels above this file: backend/workspace/
_WORKSPACE = Path(__file__).resolve().parent.parent / "workspace"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _detect_file_type(filename: str) -> str:
    """Return 'library' for .dll/.so/.lib/.a, 'header' for .h/.hpp, else 'unknown'."""
    suffix = Path(filename).suffix.lower()
    if suffix in {".dll", ".so", ".lib", ".a", ".dylib"}:
        return "library"
    if suffix in {".h", ".hpp", ".hxx", ".h++"}:
        return "header"
    return "unknown"


# ---------------------------------------------------------------------------
# POST /session
# ---------------------------------------------------------------------------

@router.post("/session", response_model=SessionResponse, status_code=201)
async def create_session() -> SessionResponse:
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "session_id": session_id,
        "created_at": _now_iso(),
        "uploads": [],
        "parses": {},
        "runs": [],
    }
    # Ensure workspace directory exists
    (_WORKSPACE / session_id / "uploads").mkdir(parents=True, exist_ok=True)
    return SessionResponse(session_id=session_id)


# ---------------------------------------------------------------------------
# POST /session/{session_id}/upload
# ---------------------------------------------------------------------------

@router.post(
    "/session/{session_id}/upload",
    response_model=UploadResponse,
    status_code=200,
)
async def upload_files(
    session_id: str,
    files: list[UploadFile],
) -> UploadResponse:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    upload_dir = _WORKSPACE / session_id / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    uploaded: list[UploadedFile] = []

    for upload in files:
        filename = upload.filename or f"file_{uuid.uuid4()}"
        dest = upload_dir / filename
        content = await upload.read()
        dest.write_bytes(content)

        file_type = _detect_file_type(filename)
        file_record = UploadedFile(
            filename=filename,
            type=file_type,
            path=str(dest),
        )
        uploaded.append(file_record)

        # Keep a serialisable record in session state
        sessions[session_id]["uploads"].append(
            {"filename": filename, "type": file_type, "path": str(dest)}
        )

    return UploadResponse(uploaded=uploaded)


# ---------------------------------------------------------------------------
# GET /session/{session_id}/history
# ---------------------------------------------------------------------------

@router.get(
    "/session/{session_id}/history",
    response_model=HistoryResponse,
    status_code=200,
)
async def get_history(session_id: str) -> HistoryResponse:
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    raw_runs: list[dict] = sessions[session_id].get("runs", [])
    summaries = [
        RunSummary(
            run_id=r["run_id"],
            run_at=r.get("run_at", ""),
            overall_status=r.get("overall_status", "unknown"),
            summary=r.get("summary", {}),
        )
        for r in raw_runs
    ]
    return HistoryResponse(runs=summaries)
