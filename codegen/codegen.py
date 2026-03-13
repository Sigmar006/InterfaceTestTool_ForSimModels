"""
codegen.py — Phase 2: CMake + GTest project generator.

Public API
----------
    generate_test_project(parse_result, test_configs, lib_path, header_path,
                          output_dir, options) -> str

CLI usage
---------
    python codegen.py \\
      --parse-result parse_output.json \\
      --test-config  test_config.json  \\
      --lib          /path/to/mylib.so \\
      --header       /path/to/mylib.h  \\
      --output       /tmp/gtest_project_001
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import jinja2
except ImportError:
    raise ImportError(
        "jinja2 is not installed. Install with: pip install jinja2"
    )

import type_mapper

# ---------------------------------------------------------------------------
# Jinja2 environment (lazy-initialised to allow import without templates dir)
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _get_env() -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        keep_trailing_newline=True,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_test_project(
    parse_result: dict,
    test_configs: list[dict],
    lib_path: str,
    header_path: str,
    output_dir: str,
    options: dict | None = None,
) -> str:
    """
    Generate a complete CMake + GTest test project to *output_dir*.

    Args:
        parse_result  - Phase-1 parse output dict (schema_version "1.0").
        test_configs  - List of TestConfig dicts (one per test case).
        lib_path      - Absolute path to the target dynamic library (.so/.dll).
        header_path   - Absolute path to the target header file.
        output_dir    - Destination directory (created if absent).
        options       - Optional settings dict (see module docstring).

    Returns:
        Absolute path to the generated project root.
    """
    if options is None:
        options = {}

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    lib_dir = out_path / "lib"
    lib_dir.mkdir(exist_ok=True)

    # ---- Filenames ----
    lib_filename    = Path(lib_path).name    if lib_path    else "libtest.so"
    header_filename = Path(header_path).name if header_path else "test.h"

    # ---- Copy library and header ----
    if lib_path and Path(lib_path).exists():
        shutil.copy2(lib_path, lib_dir / lib_filename)
    if header_path and Path(header_path).exists():
        shutil.copy2(header_path, lib_dir / header_filename)

    env = _get_env()

    # ---- Render each test case fragment ----
    test_case_tmpl = env.get_template("test_case.cpp.j2")
    test_bodies: list[str] = []

    for tc in test_configs:
        func_name = tc["function_name"]
        func_info = _find_function(parse_result, func_name)
        if func_info is None:
            raise ValueError(
                f"Function '{func_name}' not found in parse_result. "
                f"Available: {[f['name'] for f in parse_result.get('functions', [])]}"
            )
        ctx = _build_test_case_context(func_info, tc)
        test_bodies.append(test_case_tmpl.render(**ctx))

    # ---- Render test_main.cpp ----
    main_tmpl = env.get_template("test_main.cpp.j2")
    func_names = list(dict.fromkeys(tc["function_name"] for tc in test_configs))
    main_cpp = main_tmpl.render(
        generated_at=_now_utc(),
        function_names=func_names,
        header_filename=header_filename,
        test_bodies=test_bodies,
    )
    (out_path / "test_main.cpp").write_text(main_cpp, encoding="utf-8")

    # ---- Render CMakeLists.txt ----
    cmake_tmpl = env.get_template("CMakeLists.txt.j2")
    gtest_version   = options.get("gtest_version", "v1.14.0")
    gtest_fetch_url = options.get(
        "gtest_fetch_url",
        f"https://github.com/google/googletest/archive/refs/tags/{gtest_version}.zip",
    )
    cmake_txt = cmake_tmpl.render(
        cpp_standard    = options.get("cpp_standard", 17),
        build_type      = options.get("cmake_build_type", "Debug"),
        gtest_fetch_url = gtest_fetch_url,
        use_local_gtest = options.get("use_local_gtest"),
        lib_filename    = lib_filename,
    )
    (out_path / "CMakeLists.txt").write_text(cmake_txt, encoding="utf-8")

    return str(out_path.resolve())


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_function(parse_result: dict, func_name: str) -> dict | None:
    """Return the first function entry with the given name, or None."""
    for func in parse_result.get("functions", []):
        if func.get("name") == func_name:
            return func
    return None


def _build_test_case_context(func_info: dict, test_config: dict) -> dict:
    """Build the template rendering context for a single test case."""
    func_name   = func_info["name"]
    namespace   = func_info.get("namespace", "")
    return_type = func_info.get("return_type", {})
    return_kind = return_type.get("kind", "void")
    test_id     = test_config.get("test_id", "test_001")

    # Map param name → (value, as_null)
    param_values: dict[str, tuple[str, bool]] = {
        p["name"]: (str(p.get("value", "0")), bool(p.get("as_null", False)))
        for p in test_config.get("params", [])
    }

    # Build declaration lines for each parameter
    decl_lines: list[str] = []
    for param in func_info.get("params", []):
        p_name = param["name"]
        p_type = param["type"]
        value, as_null = param_values.get(p_name, ("0", False))
        decl_lines.extend(type_mapper.get_param_decls(p_name, p_type, value, as_null))

    # Build function call expression
    call_args = [p["name"] for p in func_info.get("params", [])]
    if namespace:
        qualified_func = f"{namespace}::{func_name}"
    else:
        qualified_func = func_name
    qualified_call = f"{qualified_func}({', '.join(call_args)})"

    # Output parameter print statements
    output_params      = test_config.get("output_params", [])
    output_print_stmts: list[str] = []
    for op_name in output_params:
        for param in func_info.get("params", []):
            if param["name"] == op_name:
                output_print_stmts.extend(
                    type_mapper.get_output_print_stmts(op_name, param["type"])
                )
                break

    # Assertion
    expected  = test_config.get("expected_return") or {}
    assertion: str | None = None
    if expected.get("enabled") and return_kind != "void":
        comparator = expected.get("comparator", "EXPECT_EQ")
        exp_val    = expected.get("value", "0")
        if comparator == "EXPECT_NEAR":
            assertion = f"EXPECT_NEAR(result, {exp_val}, 1e-6);"
        else:
            assertion = f"{comparator}(result, {exp_val});"

    # Is the return type directly streamable with <<  ?
    _streamable_kinds = {"integer", "float", "bool", "char", "pointer",
                         "reference", "enum"}
    return_printable = return_kind in _streamable_kinds

    return {
        "func_name"          : func_name,
        "test_id"            : test_id,
        "decl_lines"         : decl_lines,
        "qualified_call"     : qualified_call,
        "return_kind"        : return_kind,
        "return_printable"   : return_printable,
        "output_print_stmts" : output_print_stmts,
        "assertion"          : assertion,
    }


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Generate a CMake + GTest project from a Phase-1 parse result.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python codegen.py \\
    --parse-result out.json \\
    --test-config  tests.json \\
    --lib          mylib.so \\
    --header       mylib.h \\
    --output       /tmp/gtest_proj
""",
    )
    ap.add_argument("--parse-result", required=True, metavar="JSON",
                    help="Path to Phase-1 parse result JSON")
    ap.add_argument("--test-config", required=True, metavar="JSON",
                    help="Path to test config JSON (list or single object)")
    ap.add_argument("--lib", default="", metavar="PATH",
                    help="Path to the target dynamic library (.so/.dll)")
    ap.add_argument("--header", default="", metavar="PATH",
                    help="Path to the target header file")
    ap.add_argument("--output", required=True, metavar="DIR",
                    help="Output directory for the generated project")
    ap.add_argument("--cpp-standard", type=int, default=17,
                    help="C++ standard version (default: 17)")
    ap.add_argument("--build-type", default="Debug",
                    help="CMake build type (default: Debug)")
    ap.add_argument("--gtest-version", default="v1.14.0",
                    help="GTest version tag (default: v1.14.0)")
    ap.add_argument("--use-local-gtest", default=None, metavar="PATH",
                    help="Path to local GTest source (skips FetchContent)")

    args = ap.parse_args()

    parse_result = json.loads(Path(args.parse_result).read_text(encoding="utf-8"))

    raw_tc = json.loads(Path(args.test_config).read_text(encoding="utf-8"))
    test_configs = raw_tc if isinstance(raw_tc, list) else [raw_tc]

    options = {
        "cpp_standard"   : args.cpp_standard,
        "cmake_build_type": args.build_type,
        "gtest_version"  : args.gtest_version,
        "use_local_gtest": args.use_local_gtest,
    }

    out = generate_test_project(
        parse_result = parse_result,
        test_configs = test_configs,
        lib_path     = args.lib,
        header_path  = args.header,
        output_dir   = args.output,
        options      = options,
    )
    print(f"Project generated at: {out}", file=sys.stderr)
    print(out)


if __name__ == "__main__":
    main()
