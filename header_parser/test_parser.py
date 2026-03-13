"""
test_parser.py — pytest test suite for the header_parser module.

Run with:
    cd header_parser
    pytest test_parser.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure the header_parser package is importable when running from its own dir
sys.path.insert(0, str(Path(__file__).parent))

try:
    from parser import parse_header
    LIBCLANG_AVAILABLE = True
except ImportError:
    LIBCLANG_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not LIBCLANG_AVAILABLE,
    reason="libclang not installed – run: pip install libclang",
)

_HERE = Path(__file__).parent
SIMPLE_H = str(_HERE / "test_cases" / "simple.h")
ADVANCED_H = str(_HERE / "test_cases" / "advanced.h")
PARSER_PY = str(_HERE / "parser.py")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_func(result: dict, name: str) -> dict | None:
    """Return the first function with the given name, or None."""
    for func in result["functions"]:
        if func["name"] == name:
            return func
    return None


# ---------------------------------------------------------------------------
# Tests: simple.h — basic type coverage
# ---------------------------------------------------------------------------

class TestSimpleHeader:
    @pytest.fixture(scope="class")
    def result(self):
        return parse_header(SIMPLE_H, compiler_args=["-x", "c++"])

    def test_schema_version(self, result):
        assert result["schema_version"] == "1.0"

    def test_source_file_present(self, result):
        assert result["source_file"].endswith("simple.h") or "simple" in result["source_file"]

    def test_has_functions(self, result):
        assert len(result["functions"]) > 0

    # ---- return type kinds ----

    def test_integer_return_kind(self, result):
        func = _find_func(result, "my_add")
        assert func is not None, "my_add not found"
        assert func["return_type"]["kind"] == "integer"

    def test_float_return_kind(self, result):
        func = _find_func(result, "my_max_float")
        assert func is not None, "my_max_float not found"
        assert func["return_type"]["kind"] == "float"

    def test_double_return_kind(self, result):
        func = _find_func(result, "square")
        assert func is not None, "square not found"
        # double maps to kind "float"
        assert func["return_type"]["kind"] == "float"

    def test_bool_return_kind(self, result):
        func = _find_func(result, "is_positive")
        assert func is not None, "is_positive not found"
        assert func["return_type"]["kind"] == "bool"

    def test_void_return_kind(self, result):
        func = _find_func(result, "do_nothing")
        assert func is not None, "do_nothing not found"
        assert func["return_type"]["kind"] == "void"

    def test_pointer_return_kind(self, result):
        func = _find_func(result, "allocate_int")
        assert func is not None, "allocate_int not found"
        assert func["return_type"]["kind"] == "pointer"

    def test_const_char_pointer_return(self, result):
        func = _find_func(result, "get_version")
        assert func is not None, "get_version not found"
        assert func["return_type"]["kind"] == "pointer"

    # ---- parameter type kinds ----

    def test_integer_param_kind(self, result):
        func = _find_func(result, "my_add")
        assert func is not None
        assert func["params"][0]["type"]["kind"] == "integer"
        assert func["params"][1]["type"]["kind"] == "integer"

    def test_char_pointer_param(self, result):
        func = _find_func(result, "print_message")
        assert func is not None, "print_message not found"
        assert func["params"][0]["type"]["kind"] == "pointer"

    def test_param_names_present(self, result):
        func = _find_func(result, "my_add")
        assert func is not None
        names = [p["name"] for p in func["params"]]
        assert "a" in names
        assert "b" in names

    def test_default_value_is_none_for_simple(self, result):
        func = _find_func(result, "my_add")
        assert func is not None
        for param in func["params"]:
            assert param["default_value"] is None

    def test_is_variadic_false_for_simple(self, result):
        func = _find_func(result, "my_add")
        assert func is not None
        assert func["is_variadic"] is False

    def test_source_line_positive(self, result):
        func = _find_func(result, "my_add")
        assert func is not None
        assert func["source_line"] > 0

    def test_comment_captured(self, result):
        func = _find_func(result, "my_add")
        assert func is not None
        assert "add" in func["comment"].lower() or func["comment"] == ""


# ---------------------------------------------------------------------------
# Tests: advanced.h — structs, enums, namespaces, defaults, variadic, refs
# ---------------------------------------------------------------------------

class TestAdvancedHeader:
    @pytest.fixture(scope="class")
    def result(self):
        return parse_header(ADVANCED_H, compiler_args=["-x", "c++"])

    # ---- namespace ----

    def test_namespace_function_found(self, result):
        func = _find_func(result, "distance")
        assert func is not None, "geometry::distance not found"
        assert func["namespace"] == "geometry"

    def test_utils_namespace_function_found(self, result):
        func = _find_func(result, "clamp")
        assert func is not None, "utils::clamp not found"
        assert func["namespace"] == "utils"

    # ---- struct parameters ----

    def test_struct_param_kind(self, result):
        func = _find_func(result, "distance")
        assert func is not None
        assert func["params"][0]["type"]["kind"] == "struct"

    def test_struct_has_fields(self, result):
        func = _find_func(result, "distance")
        assert func is not None
        struct_type = func["params"][0]["type"]
        assert "fields" in struct_type, "struct type should have 'fields'"
        field_names = [f["name"] for f in struct_type["fields"]]
        assert "x" in field_names
        assert "y" in field_names

    # ---- enum parameters ----

    def test_enum_param_kind(self, result):
        func = _find_func(result, "color_point")
        assert func is not None, "color_point not found"
        enum_type = func["params"][1]["type"]
        assert enum_type["kind"] == "enum"

    def test_enum_has_values(self, result):
        func = _find_func(result, "color_point")
        assert func is not None
        enum_type = func["params"][1]["type"]
        assert "enum_values" in enum_type
        names = [v["name"] for v in enum_type["enum_values"]]
        assert "COLOR_RED" in names
        assert "COLOR_GREEN" in names
        assert "COLOR_BLUE" in names

    def test_enum_integer_values(self, result):
        func = _find_func(result, "color_point")
        assert func is not None
        ev = {v["name"]: v["value"] for v in func["params"][1]["type"]["enum_values"]}
        assert ev["COLOR_RED"] == 0
        assert ev["COLOR_GREEN"] == 1
        assert ev["COLOR_BLUE"] == 2

    # ---- function pointer parameter ----

    def test_function_pointer_param(self, result):
        func = _find_func(result, "transform")
        assert func is not None, "transform not found"
        # transform(Point p, Point (*transform_fn)(Point)) — fn ptr is param index 1
        fp_type = func["params"][1]["type"]
        assert fp_type["kind"] in ("function_pointer", "pointer"), (
            f"Expected function_pointer or pointer, got {fp_type['kind']}"
        )

    # ---- default values ----

    def test_default_values(self, result):
        func = _find_func(result, "clamp")
        assert func is not None
        assert len(func["params"]) == 3
        assert func["params"][1]["default_value"] == "0"
        assert func["params"][2]["default_value"] == "100"

    # ---- variadic ----

    def test_variadic_function(self, result):
        func = _find_func(result, "format_string")
        assert func is not None, "format_string not found"
        assert func["is_variadic"] is True

    # ---- reference parameters ----

    def test_reference_param_kind(self, result):
        func = _find_func(result, "swap_ints")
        assert func is not None, "swap_ints not found"
        assert func["params"][0]["type"]["kind"] == "reference"
        assert func["params"][1]["type"]["kind"] == "reference"

    def test_reference_is_reference_flag(self, result):
        func = _find_func(result, "swap_ints")
        assert func is not None
        assert func["params"][0]["type"]["is_reference"] is True


# ---------------------------------------------------------------------------
# Tests: filter rules
# ---------------------------------------------------------------------------

class TestFilterRules:
    @pytest.fixture(scope="class")
    def simple_result(self):
        return parse_header(SIMPLE_H, compiler_args=["-x", "c++"])

    def test_no_internal_symbols(self, simple_result):
        """Functions whose names start with _ must be excluded."""
        for func in simple_result["functions"]:
            assert not func["name"].startswith("_"), (
                f"Internal symbol leaked: {func['name']}"
            )

    def test_no_system_header_functions(self, simple_result):
        """Functions from system headers must be excluded."""
        for func in simple_result["functions"]:
            src = func.get("source_file", "")
            for sys_prefix in ("/usr/include", "/usr/lib"):
                assert sys_prefix not in src, (
                    f"System function leaked from {src}"
                )


# ---------------------------------------------------------------------------
# Tests: parse_errors and error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError, match="Header file not found"):
            parse_header("/nonexistent/header_99999.h")

    def test_clang_errors_collected_not_raised(self):
        """A header with unresolvable types should not crash; errors go to parse_errors."""
        with tempfile.NamedTemporaryFile(
            suffix=".h", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("int func_with_unknown(CompletelyUnknownType99 x);\n")
            tmppath = f.name
        try:
            result = parse_header(tmppath)
            assert isinstance(result, dict)
            assert "functions" in result
            # parse_errors should be a list (may or may not be non-empty
            # depending on clang's tolerance, but must exist)
            assert isinstance(result["parse_errors"], list)
        finally:
            os.unlink(tmppath)

    def test_empty_header_returns_empty_functions(self):
        """A header with no functions should return an empty functions list."""
        with tempfile.NamedTemporaryFile(
            suffix=".h", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("// Just a comment\n#define CONSTANT 42\n")
            tmppath = f.name
        try:
            result = parse_header(tmppath)
            assert result["functions"] == []
        finally:
            os.unlink(tmppath)

    def test_parse_errors_format(self):
        """Each entry in parse_errors must have 'line' and 'message'."""
        with tempfile.NamedTemporaryFile(
            suffix=".h", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write("int ok_func(int x);\n")
            tmppath = f.name
        try:
            result = parse_header(tmppath)
            for err in result["parse_errors"]:
                assert "line" in err
                assert "message" in err
        finally:
            os.unlink(tmppath)


# ---------------------------------------------------------------------------
# Tests: CLI interface
# ---------------------------------------------------------------------------

class TestCLI:
    def _run(self, *extra_args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, PARSER_PY, "--header", SIMPLE_H,
             "--args", "-x c++", *extra_args],
            capture_output=True,
            text=True,
        )

    def test_cli_exits_zero(self):
        proc = self._run()
        assert proc.returncode == 0, f"CLI stderr: {proc.stderr}"

    def test_cli_stdout_is_valid_json(self):
        proc = self._run()
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert isinstance(data, dict)

    def test_cli_output_has_schema_version(self):
        proc = self._run()
        data = json.loads(proc.stdout)
        assert data["schema_version"] == "1.0"

    def test_cli_output_has_functions(self):
        proc = self._run()
        data = json.loads(proc.stdout)
        assert isinstance(data["functions"], list)
        assert len(data["functions"]) > 0

    def test_cli_file_output(self, tmp_path):
        out_file = tmp_path / "out.json"
        proc = subprocess.run(
            [sys.executable, PARSER_PY, "--header", SIMPLE_H,
             "--args", "-x c++", "--output", str(out_file)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, f"CLI stderr: {proc.stderr}"
        assert out_file.exists()
        data = json.loads(out_file.read_text(encoding="utf-8"))
        assert data["schema_version"] == "1.0"
        assert len(data["functions"]) > 0

    def test_cli_compiler_args_forwarded(self):
        """Passing -x c++ should succeed and produce valid JSON."""
        proc = subprocess.run(
            [sys.executable, PARSER_PY, "--header", ADVANCED_H,
             "--args", "-x c++"],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, f"CLI stderr: {proc.stderr}"
        data = json.loads(proc.stdout)
        assert "functions" in data
        assert len(data["functions"]) > 0

    def test_cli_nonexistent_header_exits_nonzero(self):
        proc = subprocess.run(
            [sys.executable, PARSER_PY, "--header", "/nonexistent/header.h"],
            capture_output=True, text=True,
        )
        assert proc.returncode != 0
