"""
filters.py — Filter rules for deciding which cursors to include in output.
"""
from __future__ import annotations

import sys
import clang.cindex as ci

# ---------------------------------------------------------------------------
# System header detection
# ---------------------------------------------------------------------------

_SYSTEM_PREFIXES: list[str] = [
    "/usr/include",
    "/usr/lib",
    "/usr/local/include",
]

if sys.platform == "win32":
    import os
    for _env in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)"):
        _val = os.environ.get(_env)
        if _val:
            _SYSTEM_PREFIXES.append(_val.replace("\\", "/"))


def is_system_file(filepath: str) -> bool:
    """Return True if the given file path belongs to a system header."""
    if not filepath:
        return True
    norm = filepath.replace("\\", "/")
    for prefix in _SYSTEM_PREFIXES:
        if norm.startswith(prefix):
            return True
    return False


# ---------------------------------------------------------------------------
# Namespace extraction
# ---------------------------------------------------------------------------

def get_namespace(cursor: ci.Cursor) -> str:
    """
    Return the fully qualified enclosing namespace/class prefix for a cursor.

    Example: a function inside ``namespace geometry { class Shapes { ... } }``
    returns ``"geometry::Shapes"``.
    """
    parts: list[str] = []
    parent = cursor.semantic_parent
    while parent is not None and parent.kind != ci.CursorKind.TRANSLATION_UNIT:
        if parent.kind in (
            ci.CursorKind.NAMESPACE,
            ci.CursorKind.CLASS_DECL,
            ci.CursorKind.STRUCT_DECL,
            ci.CursorKind.CLASS_TEMPLATE,
        ):
            parts.append(parent.spelling)
        parent = parent.semantic_parent
    return "::".join(reversed(parts))


# ---------------------------------------------------------------------------
# Function inclusion filter
# ---------------------------------------------------------------------------

def should_include(cursor: ci.Cursor, include_inline: bool = False) -> bool:
    """
    Return True if the function cursor should be included in the parsed output.

    Exclusion rules (all must pass):
    - Must be FUNCTION_DECL or CXX_METHOD
    - Must have a valid source location
    - Must not be from a system header
    - Name must not start with ``_`` or ``__``
    - Must not be a constructor or destructor
    - Must not be a pure virtual method
    - Must not be a non-static class method (only static methods are testable)
    - Must not be a function template
    - Must not be an inline definition (unless ``include_inline=True``)
    """
    # Only process function-like cursors
    if cursor.kind not in (ci.CursorKind.FUNCTION_DECL, ci.CursorKind.CXX_METHOD):
        return False

    # Valid source location required
    loc = cursor.location
    if loc.file is None:
        return False

    # Skip system headers
    if is_system_file(loc.file.name):
        return False

    name = cursor.spelling

    # Skip internal / compiler-reserved symbols
    if name.startswith("_"):
        return False

    # Constructors and destructors have their own cursor kinds, but guard anyway
    if cursor.kind in (ci.CursorKind.CONSTRUCTOR, ci.CursorKind.DESTRUCTOR):
        return False

    # Pure virtual methods are not directly callable
    if cursor.is_pure_virtual_method():
        return False

    # Non-static class methods require an object instance — skip them
    if cursor.kind == ci.CursorKind.CXX_METHOD and not cursor.is_static_method():
        return False

    # Skip inline functions (definitions present in the header) unless opted in
    if not include_inline and cursor.is_definition():
        return False

    return True
