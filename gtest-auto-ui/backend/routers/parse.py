"""
Parse router — /api/v1/session/{session_id}/parse endpoint.

Calls the header_parser service and stores the result in session state.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException

# Ensure backend/ is importable as a package root
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from models.schemas import ParseRequest, ParseResponse  # noqa: E402
from services import parser_service  # noqa: E402
from state import sessions  # noqa: E402

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
router = APIRouter(prefix="/api/v1", tags=["parse"])

_WORKSPACE = Path(__file__).resolve().parent.parent / "workspace"


# ---------------------------------------------------------------------------
# POST /session/{session_id}/parse
# ---------------------------------------------------------------------------

@router.post(
    "/session/{session_id}/parse",
    response_model=ParseResponse,
    status_code=200,
)
async def parse_header(
    session_id: str,
    body: ParseRequest,
) -> ParseResponse:
    # 1. Validate session
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    # 2. Resolve header path from the upload directory
    upload_dir = _WORKSPACE / session_id / "uploads"
    header_path = upload_dir / body.header_filename

    if not header_path.is_file():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Header file '{body.header_filename}' not found in session uploads. "
                "Please upload it first."
            ),
        )

    # 3. Call parser service
    try:
        parse_result: dict = parser_service.run_parse(
            header_path=str(header_path),
            include_dirs=body.include_dirs,
            compiler_args=body.compiler_args,
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # 4. Generate parse_id and persist result
    parse_id = str(uuid.uuid4())
    sessions[session_id]["parses"][parse_id] = parse_result

    # 5. Build response
    functions: list[dict] = parse_result.get("functions", [])
    parse_errors: list[str] = parse_result.get("errors", [])
    status = "error" if parse_errors else "ok"

    return ParseResponse(
        parse_id=parse_id,
        status=status,
        functions=functions,
        parse_errors=parse_errors,
    )
