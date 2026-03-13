"""
test_codegen.py — pytest suite for the Phase-2 code-generation module.

Run with:
    cd codegen
    pytest test_codegen.py -v
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from codegen import generate_test_project

# ---------------------------------------------------------------------------
# Fixture helpers — minimal Phase-1 parse result and test configs
# ---------------------------------------------------------------------------

def _make_parse_result(functions: list[dict]) -> dict:
    return {
        "schema_version": "1.0",
        "source_file": "/tmp/mylib.h",
        "parsed_at": "2025-01-01T00:00:00Z",
        "compiler_args": [],
        "functions": functions,
        "enums": [],
        "structs": [],
        "parse_errors": [],
    }


def _int_type(raw: str = "int") -> dict:
    return {"raw": raw, "canonical": raw, "base_type": raw,
            "kind": "integer", "is_const": False, "is_pointer": False,
            "is_reference": False, "is_array": False, "array_size": None,
            "pointee_type": None}


def _float_type(raw: str = "float") -> dict:
    return {"raw": raw, "canonical": raw, "base_type": raw,
            "kind": "float", "is_const": False, "is_pointer": False,
            "is_reference": False, "is_array": False, "array_size": None,
            "pointee_type": None}


def _bool_type() -> dict:
    return {"raw": "bool", "canonical": "bool", "base_type": "bool",
            "kind": "bool", "is_const": False, "is_pointer": False,
            "is_reference": False, "is_array": False, "array_size": None,
            "pointee_type": None}


def _ptr_type(base: str = "int", pointee_kind: str = "integer") -> dict:
    pointee = {"raw": base, "canonical": base, "base_type": base,
               "kind": pointee_kind, "is_const": False, "is_pointer": False,
               "is_reference": False}
    return {"raw": f"{base}*", "canonical": f"{base}*", "base_type": base,
            "kind": "pointer", "is_const": False, "is_pointer": True,
            "is_reference": False, "is_array": False, "array_size": None,
            "pointee_type": pointee}


def _char_ptr_type() -> dict:
    pointee = {"raw": "char", "canonical": "char", "base_type": "char",
               "kind": "char", "is_const": False, "is_pointer": False,
               "is_reference": False}
    return {"raw": "const char*", "canonical": "const char*", "base_type": "char",
            "kind": "pointer", "is_const": False, "is_pointer": True,
            "is_reference": False, "is_array": False, "array_size": None,
            "pointee_type": pointee}


def _ref_type(base: str = "int") -> dict:
    pointee = {"raw": base, "canonical": base, "base_type": base,
               "kind": "integer", "is_const": False, "is_pointer": False,
               "is_reference": False}
    return {"raw": f"{base}&", "canonical": f"{base}&", "base_type": base,
            "kind": "reference", "is_const": False, "is_pointer": False,
            "is_reference": True, "is_array": False, "array_size": None,
            "pointee_type": pointee}


def _enum_type(name: str = "Color", values: list | None = None) -> dict:
    ev = values or [
        {"name": "COLOR_RED", "value": 0},
        {"name": "COLOR_GREEN", "value": 1},
    ]
    return {"raw": name, "canonical": name, "base_type": name,
            "kind": "enum", "is_const": False, "is_pointer": False,
            "is_reference": False, "is_array": False, "array_size": None,
            "pointee_type": None, "enum_values": ev}


def _struct_type(name: str = "Point") -> dict:
    fields = [
        {"name": "x", "type": _float_type("float")},
        {"name": "y", "type": _float_type("float")},
    ]
    return {"raw": name, "canonical": name, "base_type": name,
            "kind": "struct", "is_const": False, "is_pointer": False,
            "is_reference": False, "is_array": False, "array_size": None,
            "pointee_type": None, "fields": fields}


# Pre-built parse results
_MY_ADD_FUNC = {
    "name": "my_add", "namespace": "", "is_variadic": False,
    "source_file": "/tmp/mylib.h", "source_line": 5, "comment": "",
    "return_type": _int_type(),
    "params": [
        {"name": "a", "type": _int_type(), "default_value": None},
        {"name": "b", "type": _int_type(), "default_value": None},
    ],
}

_VOID_FUNC = {
    "name": "do_work", "namespace": "", "is_variadic": False,
    "source_file": "/tmp/mylib.h", "source_line": 10, "comment": "",
    "return_type": {"raw": "void", "canonical": "void", "base_type": "void",
                    "kind": "void", "is_const": False, "is_pointer": False,
                    "is_reference": False, "is_array": False, "array_size": None,
                    "pointee_type": None},
    "params": [],
}

_NS_FUNC = {
    "name": "distance", "namespace": "geometry", "is_variadic": False,
    "source_file": "/tmp/mylib.h", "source_line": 20, "comment": "",
    "return_type": _float_type("double"),
    "params": [
        {"name": "x", "type": _float_type("double"), "default_value": None},
        {"name": "y", "type": _float_type("double"), "default_value": None},
    ],
}


# ---------------------------------------------------------------------------
# Tests: 1 — basic integer function → correct TEST() name
# ---------------------------------------------------------------------------

class TestBasicIntFunction:
    @pytest.fixture(scope="class")
    def out_dir(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("basic_int")
        generate_test_project(
            parse_result=_make_parse_result([_MY_ADD_FUNC]),
            test_configs=[{
                "test_id": "test_001",
                "function_name": "my_add",
                "params": [
                    {"name": "a", "value": "2", "as_null": False},
                    {"name": "b", "value": "3", "as_null": False},
                ],
                "expected_return": {"enabled": True, "comparator": "EXPECT_EQ", "value": "5"},
                "output_params": [],
            }],
            lib_path="",
            header_path="",
            output_dir=str(tmp),
        )
        return tmp

    def test_test_main_cpp_exists(self, out_dir):
        assert (out_dir / "test_main.cpp").exists()

    def test_cmake_exists(self, out_dir):
        assert (out_dir / "CMakeLists.txt").exists()

    def test_lib_dir_exists(self, out_dir):
        assert (out_dir / "lib").is_dir()

    def test_correct_test_name(self, out_dir):
        cpp = (out_dir / "test_main.cpp").read_text(encoding="utf-8")
        assert "TEST(AutoTest, my_add_test_001)" in cpp

    def test_param_declarations(self, out_dir):
        cpp = (out_dir / "test_main.cpp").read_text(encoding="utf-8")
        assert "int a = 2;" in cpp
        assert "int b = 3;" in cpp

    def test_function_call_present(self, out_dir):
        cpp = (out_dir / "test_main.cpp").read_text(encoding="utf-8")
        assert "my_add(a, b)" in cpp

    def test_assertion_present(self, out_dir):
        cpp = (out_dir / "test_main.cpp").read_text(encoding="utf-8")
        assert "EXPECT_EQ(result, 5)" in cpp

    def test_gtest_include(self, out_dir):
        cpp = (out_dir / "test_main.cpp").read_text(encoding="utf-8")
        assert "#include <gtest/gtest.h>" in cpp


# ---------------------------------------------------------------------------
# Tests: 2 — pointer parameter generates address-of code
# ---------------------------------------------------------------------------

class TestPointerParam:
    @pytest.fixture(scope="class")
    def cpp(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("ptr")
        func = {
            "name": "set_value", "namespace": "", "is_variadic": False,
            "source_file": "/tmp/mylib.h", "source_line": 1, "comment": "",
            "return_type": {"raw": "void", "canonical": "void", "base_type": "void",
                            "kind": "void", "is_const": False, "is_pointer": False,
                            "is_reference": False, "is_array": False,
                            "array_size": None, "pointee_type": None},
            "params": [{"name": "p", "type": _ptr_type("int", "integer"),
                        "default_value": None}],
        }
        generate_test_project(
            parse_result=_make_parse_result([func]),
            test_configs=[{
                "test_id": "test_ptr",
                "function_name": "set_value",
                "params": [{"name": "p", "value": "42", "as_null": False}],
                "expected_return": {"enabled": False},
                "output_params": [],
            }],
            lib_path="", header_path="", output_dir=str(tmp),
        )
        return (tmp / "test_main.cpp").read_text(encoding="utf-8")

    def test_val_variable_declared(self, cpp):
        assert "val_p = 42" in cpp

    def test_address_of_taken(self, cpp):
        assert "&val_p" in cpp

    def test_pointer_variable_name(self, cpp):
        assert "int* p =" in cpp


# ---------------------------------------------------------------------------
# Tests: 3 — as_null=True pointer generates nullptr
# ---------------------------------------------------------------------------

class TestNullPointerParam:
    @pytest.fixture(scope="class")
    def cpp(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("null_ptr")
        func = {
            "name": "nullable", "namespace": "", "is_variadic": False,
            "source_file": "/tmp/mylib.h", "source_line": 1, "comment": "",
            "return_type": {"raw": "void", "canonical": "void", "base_type": "void",
                            "kind": "void", "is_const": False, "is_pointer": False,
                            "is_reference": False, "is_array": False,
                            "array_size": None, "pointee_type": None},
            "params": [{"name": "buf", "type": _ptr_type("char", "char"),
                        "default_value": None}],
        }
        generate_test_project(
            parse_result=_make_parse_result([func]),
            test_configs=[{
                "test_id": "test_null",
                "function_name": "nullable",
                "params": [{"name": "buf", "value": "", "as_null": True}],
                "expected_return": {"enabled": False},
                "output_params": [],
            }],
            lib_path="", header_path="", output_dir=str(tmp),
        )
        return (tmp / "test_main.cpp").read_text(encoding="utf-8")

    def test_nullptr_generated(self, cpp):
        assert "nullptr" in cpp

    def test_no_address_of(self, cpp):
        assert "&val_buf" not in cpp


# ---------------------------------------------------------------------------
# Tests: 4 — enum parameter generates correct enum reference
# ---------------------------------------------------------------------------

class TestEnumParam:
    @pytest.fixture(scope="class")
    def cpp(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("enum")
        func = {
            "name": "paint", "namespace": "", "is_variadic": False,
            "source_file": "/tmp/mylib.h", "source_line": 1, "comment": "",
            "return_type": {"raw": "void", "canonical": "void", "base_type": "void",
                            "kind": "void", "is_const": False, "is_pointer": False,
                            "is_reference": False, "is_array": False,
                            "array_size": None, "pointee_type": None},
            "params": [{"name": "c", "type": _enum_type("Color"),
                        "default_value": None}],
        }
        generate_test_project(
            parse_result=_make_parse_result([func]),
            test_configs=[{
                "test_id": "test_enum",
                "function_name": "paint",
                "params": [{"name": "c", "value": "COLOR_RED", "as_null": False}],
                "expected_return": {"enabled": False},
                "output_params": [],
            }],
            lib_path="", header_path="", output_dir=str(tmp),
        )
        return (tmp / "test_main.cpp").read_text(encoding="utf-8")

    def test_enum_type_declared(self, cpp):
        assert "Color c = COLOR_RED;" in cpp


# ---------------------------------------------------------------------------
# Tests: 5 — assertion macros
# ---------------------------------------------------------------------------

class TestAssertionMacros:
    def _gen(self, comparator: str, exp_val: str, tmp_path) -> str:
        generate_test_project(
            parse_result=_make_parse_result([_MY_ADD_FUNC]),
            test_configs=[{
                "test_id": "assert_test",
                "function_name": "my_add",
                "params": [
                    {"name": "a", "value": "1", "as_null": False},
                    {"name": "b", "value": "2", "as_null": False},
                ],
                "expected_return": {"enabled": True,
                                    "comparator": comparator,
                                    "value": exp_val},
                "output_params": [],
            }],
            lib_path="", header_path="", output_dir=str(tmp_path),
        )
        return (tmp_path / "test_main.cpp").read_text(encoding="utf-8")

    def test_expect_eq(self, tmp_path):
        cpp = self._gen("EXPECT_EQ", "3", tmp_path)
        assert "EXPECT_EQ(result, 3)" in cpp

    def test_expect_ne(self, tmp_path):
        cpp = self._gen("EXPECT_NE", "0", tmp_path)
        assert "EXPECT_NE(result, 0)" in cpp

    def test_expect_gt(self, tmp_path):
        cpp = self._gen("EXPECT_GT", "0", tmp_path)
        assert "EXPECT_GT(result, 0)" in cpp

    def test_expect_lt(self, tmp_path):
        cpp = self._gen("EXPECT_LT", "100", tmp_path)
        assert "EXPECT_LT(result, 100)" in cpp

    def test_expect_near(self, tmp_path):
        cpp = self._gen("EXPECT_NEAR", "3.0", tmp_path)
        assert "EXPECT_NEAR(result, 3.0, 1e-6)" in cpp


# ---------------------------------------------------------------------------
# Tests: 6 — directory structure is correct
# ---------------------------------------------------------------------------

class TestDirectoryStructure:
    @pytest.fixture(scope="class")
    def out_dir(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("dirtest")
        generate_test_project(
            parse_result=_make_parse_result([_MY_ADD_FUNC]),
            test_configs=[{
                "test_id": "dir_test",
                "function_name": "my_add",
                "params": [
                    {"name": "a", "value": "0", "as_null": False},
                    {"name": "b", "value": "0", "as_null": False},
                ],
                "expected_return": {"enabled": False},
                "output_params": [],
            }],
            lib_path="", header_path="", output_dir=str(tmp),
        )
        return tmp

    def test_cmake_lists_exists(self, out_dir):
        assert (out_dir / "CMakeLists.txt").exists()

    def test_test_main_cpp_exists(self, out_dir):
        assert (out_dir / "test_main.cpp").exists()

    def test_lib_dir_exists(self, out_dir):
        assert (out_dir / "lib").is_dir()

    def test_return_value_is_absolute_path(self, tmp_path):
        out = generate_test_project(
            parse_result=_make_parse_result([_MY_ADD_FUNC]),
            test_configs=[{
                "test_id": "abs_test",
                "function_name": "my_add",
                "params": [
                    {"name": "a", "value": "0", "as_null": False},
                    {"name": "b", "value": "0", "as_null": False},
                ],
                "expected_return": {"enabled": False},
                "output_params": [],
            }],
            lib_path="", header_path="", output_dir=str(tmp_path),
        )
        assert Path(out).is_absolute()


# ---------------------------------------------------------------------------
# Tests: 7 — CMakeLists.txt contains correct lib filename
# ---------------------------------------------------------------------------

class TestCMakeContents:
    @pytest.fixture(scope="class")
    def cmake(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("cmake")
        generate_test_project(
            parse_result=_make_parse_result([_MY_ADD_FUNC]),
            test_configs=[{
                "test_id": "cmake_test",
                "function_name": "my_add",
                "params": [
                    {"name": "a", "value": "1", "as_null": False},
                    {"name": "b", "value": "2", "as_null": False},
                ],
                "expected_return": {"enabled": False},
                "output_params": [],
            }],
            lib_path="/some/dir/libmylib.so",
            header_path="/some/dir/mylib.h",
            output_dir=str(tmp),
        )
        return (tmp / "CMakeLists.txt").read_text(encoding="utf-8")

    def test_lib_filename_in_cmake(self, cmake):
        assert "libmylib.so" in cmake

    def test_minimum_cmake_version(self, cmake):
        assert "cmake_minimum_required(VERSION 3.14)" in cmake

    def test_fetchcontent_present_by_default(self, cmake):
        assert "FetchContent" in cmake

    def test_gtest_link(self, cmake):
        assert "GTest::gtest_main" in cmake

    def test_local_gtest_replaces_fetch(self, tmp_path):
        generate_test_project(
            parse_result=_make_parse_result([_MY_ADD_FUNC]),
            test_configs=[{
                "test_id": "local_gtest",
                "function_name": "my_add",
                "params": [
                    {"name": "a", "value": "0", "as_null": False},
                    {"name": "b", "value": "0", "as_null": False},
                ],
                "expected_return": {"enabled": False},
                "output_params": [],
            }],
            lib_path="", header_path="",
            output_dir=str(tmp_path),
            options={"use_local_gtest": "/opt/googletest"},
        )
        cmake = (tmp_path / "CMakeLists.txt").read_text(encoding="utf-8")
        assert "add_subdirectory" in cmake
        assert "/opt/googletest" in cmake
        assert "FetchContent_Declare" not in cmake


# ---------------------------------------------------------------------------
# Tests: 8 — namespace prefix is added to function call
# ---------------------------------------------------------------------------

class TestNamespaceCall:
    @pytest.fixture(scope="class")
    def cpp(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("ns")
        generate_test_project(
            parse_result=_make_parse_result([_NS_FUNC]),
            test_configs=[{
                "test_id": "ns_test",
                "function_name": "distance",
                "params": [
                    {"name": "x", "value": "1.0", "as_null": False},
                    {"name": "y", "value": "2.0", "as_null": False},
                ],
                "expected_return": {"enabled": False},
                "output_params": [],
            }],
            lib_path="", header_path="", output_dir=str(tmp),
        )
        return (tmp / "test_main.cpp").read_text(encoding="utf-8")

    def test_namespace_prefix_in_call(self, cpp):
        assert "geometry::distance" in cpp


# ---------------------------------------------------------------------------
# Tests: 9 — void function has no result variable, no assertion
# ---------------------------------------------------------------------------

class TestVoidFunction:
    @pytest.fixture(scope="class")
    def cpp(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("void_func")
        generate_test_project(
            parse_result=_make_parse_result([_VOID_FUNC]),
            test_configs=[{
                "test_id": "void_test",
                "function_name": "do_work",
                "params": [],
                "expected_return": {"enabled": False},
                "output_params": [],
            }],
            lib_path="", header_path="", output_dir=str(tmp),
        )
        return (tmp / "test_main.cpp").read_text(encoding="utf-8")

    def test_no_result_variable(self, cpp):
        assert "auto result" not in cpp

    def test_called_successfully_message(self, cpp):
        assert "called successfully" in cpp

    def test_no_assert(self, cpp):
        assert "EXPECT_" not in cpp


# ---------------------------------------------------------------------------
# Tests: 10 — multiple test cases in one file
# ---------------------------------------------------------------------------

class TestMultipleTestCases:
    @pytest.fixture(scope="class")
    def cpp(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("multi")
        generate_test_project(
            parse_result=_make_parse_result([_MY_ADD_FUNC]),
            test_configs=[
                {
                    "test_id": "tc_001",
                    "function_name": "my_add",
                    "params": [
                        {"name": "a", "value": "1", "as_null": False},
                        {"name": "b", "value": "2", "as_null": False},
                    ],
                    "expected_return": {"enabled": True, "comparator": "EXPECT_EQ", "value": "3"},
                    "output_params": [],
                },
                {
                    "test_id": "tc_002",
                    "function_name": "my_add",
                    "params": [
                        {"name": "a", "value": "0", "as_null": False},
                        {"name": "b", "value": "0", "as_null": False},
                    ],
                    "expected_return": {"enabled": True, "comparator": "EXPECT_EQ", "value": "0"},
                    "output_params": [],
                },
            ],
            lib_path="", header_path="", output_dir=str(tmp),
        )
        return (tmp / "test_main.cpp").read_text(encoding="utf-8")

    def test_first_test_case(self, cpp):
        assert "TEST(AutoTest, my_add_tc_001)" in cpp

    def test_second_test_case(self, cpp):
        assert "TEST(AutoTest, my_add_tc_002)" in cpp

    def test_both_assertions(self, cpp):
        assert "EXPECT_EQ(result, 3)" in cpp
        assert "EXPECT_EQ(result, 0)" in cpp


# ---------------------------------------------------------------------------
# Tests: 11 — struct parameter
# ---------------------------------------------------------------------------

class TestStructParam:
    @pytest.fixture(scope="class")
    def cpp(self, tmp_path_factory):
        tmp = tmp_path_factory.mktemp("struct")
        func = {
            "name": "area", "namespace": "", "is_variadic": False,
            "source_file": "/tmp/mylib.h", "source_line": 1, "comment": "",
            "return_type": _float_type("float"),
            "params": [{"name": "rect", "type": _struct_type("Rect"), "default_value": None}],
        }
        generate_test_project(
            parse_result=_make_parse_result([func]),
            test_configs=[{
                "test_id": "struct_test",
                "function_name": "area",
                "params": [{"name": "rect",
                            "value": '{"x": "1.0", "y": "2.0"}',
                            "as_null": False}],
                "expected_return": {"enabled": False},
                "output_params": [],
            }],
            lib_path="", header_path="", output_dir=str(tmp),
        )
        return (tmp / "test_main.cpp").read_text(encoding="utf-8")

    def test_struct_type_declared(self, cpp):
        assert "Rect rect" in cpp

    def test_field_x_assigned(self, cpp):
        assert "rect.x = 1.0f" in cpp

    def test_field_y_assigned(self, cpp):
        assert "rect.y = 2.0f" in cpp
