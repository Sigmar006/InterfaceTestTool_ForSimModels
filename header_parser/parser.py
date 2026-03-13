"""
parser.py — Main header parsing module for the GTest Auto UI project.

Public API
----------
    parse_header(header_path, include_dirs, compiler_args, include_inline) -> dict

CLI usage
---------
    python parser.py --header /path/to/mylib.h \\
                     --include /path/to/deps/include \\
                     --args "-std=c++17" \\
                     --output result.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import clang.cindex as ci
except ImportError:
    raise ImportError(
        "libclang is not installed. Install it with:\n"
        "    pip install libclang"
    )

from type_resolver import resolve_type
from filters import get_namespace, is_system_file, should_include


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_header(
    header_path: str,
    include_dirs: list[str] | None = None,
    compiler_args: list[str] | None = None,
    include_inline: bool = False,
) -> dict:
    """
    Parse a single C/C++ header file and return a structured interface dict.

    Args:
        header_path   - Absolute (or resolvable) path to the header file.
        include_dirs  - Additional include search directories.
        compiler_args - Extra flags forwarded to clang (e.g. ["-std=c++17"]).
        include_inline - If True, inline function definitions are included.

    Returns:
        A dict matching the Phase 1 output schema (schema_version "1.0").

    Raises:
        FileNotFoundError - If header_path does not exist.
        ImportError       - If libclang is not installed (raised at import time).
    """
    if include_dirs is None:
        include_dirs = []
    if compiler_args is None:
        compiler_args = []

    path = Path(header_path)
    if not path.exists():
        raise FileNotFoundError(f"Header file not found: {header_path}")

    abs_path = str(path.resolve())

    # Build clang compile arguments
    args: list[str] = list(compiler_args)
    for inc in include_dirs:
        args.append(f"-I{inc}")

    index = ci.Index.create()
    tu = index.parse(
        abs_path,
        args=args,
        options=(
            ci.TranslationUnit.PARSE_DETAILED_PROCESSING_RECORD
            | ci.TranslationUnit.PARSE_SKIP_FUNCTION_BODIES
        ),
    )

    parse_errors: list[dict] = []

    # Collect clang diagnostics (errors and fatal errors only)
    for diag in tu.diagnostics:
        if diag.severity >= ci.Diagnostic.Error:
            parse_errors.append({
                "line": diag.location.line,
                "message": diag.spelling,
            })

    functions: list[dict] = []
    enums: list[dict] = []
    structs: list[dict] = []
    visited: set[str] = set()

    _walk_cursor(
        tu.cursor,
        abs_path,
        functions,
        enums,
        structs,
        parse_errors,
        include_inline,
        visited,
    )

    return {
        "schema_version": "1.0",
        "source_file": abs_path,
        "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "compiler_args": list(compiler_args),
        "functions": functions,
        "enums": enums,
        "structs": structs,
        "parse_errors": parse_errors,
    }


# ---------------------------------------------------------------------------
# AST traversal
# ---------------------------------------------------------------------------

def _walk_cursor(
    cursor: ci.Cursor,
    source_file: str,
    functions: list,
    enums: list,
    structs: list,
    parse_errors: list,
    include_inline: bool,
    visited: set,
) -> None:
    """Recursively walk the AST and collect relevant declarations."""
    for child in cursor.get_children():
        loc = child.location
        if loc.file is None:
            continue

        child_file = loc.file.name
        if is_system_file(child_file):
            continue

        kind = child.kind

        # ---- Function declarations ----
        if kind in (ci.CursorKind.FUNCTION_DECL, ci.CursorKind.CXX_METHOD):
            if should_include(child, include_inline):
                usr = child.get_usr()
                if usr and usr not in visited:
                    visited.add(usr)
                    info = _extract_function(child, parse_errors)
                    if info is not None:
                        functions.append(info)

        # ---- Recurse into containers ----
        elif kind in (
            ci.CursorKind.NAMESPACE,
            ci.CursorKind.LINKAGE_SPEC,     # extern "C" { ... }
            ci.CursorKind.CLASS_DECL,
            ci.CursorKind.STRUCT_DECL,
            ci.CursorKind.CLASS_TEMPLATE,
        ):
            _walk_cursor(
                child, source_file, functions, enums, structs,
                parse_errors, include_inline, visited,
            )

        # ---- Top-level enum declarations ----
        elif kind == ci.CursorKind.ENUM_DECL and child.is_definition():
            usr = child.get_usr()
            if usr and usr not in visited:
                visited.add(usr)
                enum_info = _extract_enum(child)
                if enum_info:
                    enums.append(enum_info)

        # ---- Top-level struct/class declarations ----
        elif kind in (
            ci.CursorKind.STRUCT_DECL, ci.CursorKind.CLASS_DECL
        ) and child.is_definition():
            usr = child.get_usr()
            if usr and usr not in visited:
                visited.add(usr)
                struct_info = _extract_struct(child, parse_errors)
                if struct_info:
                    structs.append(struct_info)


# ---------------------------------------------------------------------------
# Function extraction
# ---------------------------------------------------------------------------

def _extract_function(cursor: ci.Cursor, parse_errors: list) -> dict | None:
    """Extract a single function's metadata from a cursor."""
    try:
        name = cursor.spelling
        namespace = get_namespace(cursor)
        return_type = resolve_type(cursor.result_type, 0, parse_errors)

        params: list[dict] = []
        for idx, param in enumerate(cursor.get_arguments()):
            param_name = param.spelling or f"arg{idx}"
            param_type = resolve_type(param.type, 0, parse_errors)
            default_val = _get_default_value(param)
            params.append({
                "name": param_name,
                "type": param_type,
                "default_value": default_val,
            })

        # Variadic check — try cursor attribute first, fall back to type
        try:
            is_variadic: bool = cursor.type.is_function_variadic()
        except AttributeError:
            is_variadic = False

        loc = cursor.location
        source_file = loc.file.name if loc.file else ""
        source_line = loc.line
        comment = cursor.raw_comment or ""

        return {
            "name": name,
            "namespace": namespace,
            "return_type": return_type,
            "params": params,
            "is_variadic": is_variadic,
            "source_file": source_file,
            "source_line": source_line,
            "comment": comment,
        }
    except Exception as exc:
        parse_errors.append({
            "line": cursor.location.line,
            "message": f"Failed to extract function '{cursor.spelling}': {exc}",
        })
        return None


def _get_default_value(param_cursor: ci.Cursor) -> str | None:
    """
    Attempt to extract a default value expression from a parameter cursor.

    libclang does not expose default values via a dedicated API; we detect
    them by looking for non-type child cursors (the default value expression)
    and reconstructing the text from tokens.
    """
    _skip_kinds = frozenset({
        ci.CursorKind.TYPE_REF,
        ci.CursorKind.TEMPLATE_REF,
        ci.CursorKind.NAMESPACE_REF,
        ci.CursorKind.PARM_DECL,
    })
    for child in param_cursor.get_children():
        if child.kind not in _skip_kinds:
            tokens = list(child.get_tokens())
            if tokens:
                return "".join(t.spelling for t in tokens)
    return None


# ---------------------------------------------------------------------------
# Top-level enum / struct extraction
# ---------------------------------------------------------------------------

def _extract_enum(cursor: ci.Cursor) -> dict | None:
    """Extract a top-level enum declaration."""
    values = []
    for child in cursor.get_children():
        if child.kind == ci.CursorKind.ENUM_CONSTANT_DECL:
            values.append({"name": child.spelling, "value": child.enum_value})
    return {
        "name": cursor.spelling,
        "source_line": cursor.location.line,
        "values": values,
    }


def _extract_struct(cursor: ci.Cursor, parse_errors: list) -> dict | None:
    """Extract a top-level struct/class declaration (fields only, depth=1)."""
    from type_resolver import _get_struct_fields  # avoid circular at module level
    fields = _get_struct_fields(cursor, 1, parse_errors)
    return {
        "name": cursor.spelling,
        "source_line": cursor.location.line,
        "fields": fields,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Parse a C/C++ header file and emit structured JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python parser.py --header mylib.h --output result.json
  python parser.py --header mylib.h --include /path/to/deps --args "-std=c++17"
""",
    )
    ap.add_argument("--header", required=True, metavar="FILE",
                    help="Path to the header file to parse")
    ap.add_argument("--include", action="append", default=[], metavar="DIR",
                    help="Extra include directory (repeatable)")
    ap.add_argument("--args", action="append", default=[], metavar="ARG",
                    help="Extra compiler flag (repeatable, may contain spaces)")
    ap.add_argument("--output", default=None, metavar="FILE",
                    help="Output JSON file (default: stdout)")
    ap.add_argument("--include-inline", action="store_true",
                    help="Include inline function definitions")

    args = ap.parse_args()

    # Each --args value may be a space-separated string like "-std=c++17 -DDEBUG"
    compiler_args: list[str] = []
    for arg in args.args:
        compiler_args.extend(arg.split())

    try:
        result = parse_header(
            header_path=args.header,
            include_dirs=args.include,
            compiler_args=compiler_args,
            include_inline=args.include_inline,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    json_str = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(json_str, encoding="utf-8")
        print(f"Output written to {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
