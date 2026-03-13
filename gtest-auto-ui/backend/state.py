"""
Module-level singletons shared across all routers.

Import pattern in routers:
    from state import sessions, ws_queues, result_store
"""
from __future__ import annotations

# session_id -> {
#   "session_id": str,
#   "created_at": str (ISO-8601),
#   "uploads": list[dict],
#   "parses":  {parse_id: parse_result_dict},
#   "runs":    list[RunSummary-compatible dict],
# }
sessions: dict = {}

# run_id -> asyncio.Queue
ws_queues: dict = {}

# run_id -> full Phase-3 result dict (populated when pipeline finishes)
result_store: dict = {}
