"""
Parser service — thin wrapper around header_parser/parser.py.

Path layout:
    __file__  = .../InterfaceTestTool/gtest-auto-ui/backend/services/parser_service.py
    ROOT      = parent x4  →  .../InterfaceTestTool/
"""
from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: make header_parser importable
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent.parent  # InterfaceTestTool/
_HEADER_PARSER_DIR = str(ROOT / "header_parser")
if _HEADER_PARSER_DIR not in sys.path:
    sys.path.insert(0, _HEADER_PARSER_DIR)

from parser import parse_header  # noqa: E402  (imported after sys.path patch)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_parse(
    header_path: str,
    include_dirs: list[str],
    compiler_args: list[str],
) -> dict:
    """
    Call parse_header() and return the full result dict.

    Raises RuntimeError with a descriptive message on failure.
    """
    try:
        result = parse_header(
            header_path,
            include_dirs=include_dirs,
            compiler_args=compiler_args,
        )
        return result
    except Exception as exc:
        raise RuntimeError(
            f"parse_header failed for '{header_path}': {exc}"
        ) from exc
