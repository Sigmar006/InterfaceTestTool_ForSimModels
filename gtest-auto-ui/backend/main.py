"""
GTest Auto UI — FastAPI backend entry point.

Run with:
    uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure backend/ itself is on sys.path so all relative imports resolve
# regardless of how uvicorn / pytest launches the process.
_BACKEND_DIR = str(Path(__file__).resolve().parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import parse as parse_router
from routers import run as run_router
from routers import session as session_router

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="GTest Auto UI Backend",
    version="1.0",
    description=(
        "REST + WebSocket API that orchestrates C/C++ header parsing, "
        "GTest project code-generation, and CMake build/run."
    ),
)

# ---------------------------------------------------------------------------
# CORS — allow all origins in development; tighten for production
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(session_router.router)
app.include_router(parse_router.router)
app.include_router(run_router.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}
