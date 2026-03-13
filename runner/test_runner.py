"""
test_runner.py — pytest tests for Phase-3 runner module.

Strategy
--------
* Unit-level tests mock process_manager / env_checker to avoid real cmake.
* Integration-style tests create a tiny fake test executable (a Python script
  that mimics GTest output) so the full pipeline can run without CMake or GTest.
"""
from __future__ import annotations

import json
import os
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import env_checker
import process_manager
import result_parser
import runner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(tmp_path: Path) -> Path:
    """Create a minimal project directory that passes env_check."""
    (tmp_path / "CMakeLists.txt").write_text("cmake_minimum_required(VERSION 3.14)\n")
    (tmp_path / "lib").mkdir(exist_ok=True)
    return tmp_path


def _passing_env_result():
    return {"ok": True, "cmake_version": "3.28.0", "compiler": "g++", "error": None, "duration_ms": 1}


def _run_ok(cmd, **kwargs):
    """Fake process_manager.run_process that always succeeds."""
    return 0, "fake stdout", "", False


def _run_fail(cmd, **kwargs):
    return 1, "", "error output", False


def _run_timeout(cmd, **kwargs):
    return -1, "", "", True


# ---------------------------------------------------------------------------
# env_checker tests
# ---------------------------------------------------------------------------

class TestEnvChecker:
    def test_missing_project_dir(self, tmp_path):
        result = env_checker.check_env(str(tmp_path / "nonexistent"), "cmake")
        assert result["ok"] is False
        assert "not found" in result["error"]

    def test_missing_cmake_lists(self, tmp_path):
        result = env_checker.check_env(str(tmp_path), "cmake")
        assert result["ok"] is False
        assert "CMakeLists.txt" in result["error"]

    def test_cmake_not_on_path(self, tmp_path):
        _make_project(tmp_path)
        result = env_checker.check_env(str(tmp_path), "cmake_does_not_exist_xyz")
        assert result["ok"] is False
        assert "not found" in result["error"].lower() or "cmake" in result["error"].lower()

    def test_cmake_found(self, tmp_path):
        _make_project(tmp_path)
        result = env_checker.check_env(str(tmp_path), "cmake")
        # On CI / developer machines cmake may or may not be present
        if result["ok"]:
            assert result["cmake_version"] is not None
        else:
            assert result["error"] is not None

    def test_result_has_required_keys(self, tmp_path):
        _make_project(tmp_path)
        result = env_checker.check_env(str(tmp_path))
        for key in ("ok", "cmake_version", "compiler", "error", "duration_ms"):
            assert key in result


# ---------------------------------------------------------------------------
# process_manager tests
# ---------------------------------------------------------------------------

class TestProcessManager:
    def test_successful_command(self):
        rc, out, err, timed_out = process_manager.run_process(
            [sys.executable, "-c", "print('hello')"]
        )
        assert rc == 0
        assert "hello" in out
        assert timed_out is False

    def test_nonzero_exit(self):
        rc, out, err, timed_out = process_manager.run_process(
            [sys.executable, "-c", "import sys; sys.exit(42)"]
        )
        assert rc == 42
        assert timed_out is False

    def test_stderr_captured(self):
        rc, out, err, timed_out = process_manager.run_process(
            [sys.executable, "-c", "import sys; sys.stderr.write('err_msg\\n')"]
        )
        assert "err_msg" in err

    def test_timeout(self):
        rc, out, err, timed_out = process_manager.run_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            timeout=0.5,
        )
        assert timed_out is True
        assert rc == -1

    def test_on_output_callback(self):
        lines_seen = []
        def cb(line, stream, stage):
            lines_seen.append((line, stream, stage))

        process_manager.run_process(
            [sys.executable, "-c", "print('a'); print('b')"],
            on_output=cb,
            stage="test_stage",
        )
        texts = [t for t, _, _ in lines_seen]
        assert "a" in texts
        assert "b" in texts
        for _, _, s in lines_seen:
            assert s == "test_stage"

    def test_on_output_exception_not_propagated(self):
        def bad_cb(line, stream, stage):
            raise RuntimeError("callback error")

        # Should not raise
        process_manager.run_process(
            [sys.executable, "-c", "print('x')"],
            on_output=bad_cb,
        )

    def test_env_passed_to_subprocess(self):
        env = {**os.environ, "MY_TEST_VAR": "hello_runner"}
        rc, out, err, _ = process_manager.run_process(
            [sys.executable, "-c", "import os; print(os.environ.get('MY_TEST_VAR', ''))"],
            env=env,
        )
        assert "hello_runner" in out


# ---------------------------------------------------------------------------
# result_parser tests
# ---------------------------------------------------------------------------

SAMPLE_GTEST_TEXT = """\
[==========] Running 2 tests from 1 test suite.
[----------] 2 tests from AutoTest
[ RUN      ] AutoTest.my_add_test_001
[       OK ] AutoTest.my_add_test_001 (1 ms)
[ RUN      ] AutoTest.my_add_test_002
user output line
Expected: value1
[  FAILED  ] AutoTest.my_add_test_002 (2 ms)
[----------] 2 tests from AutoTest
[==========] 2 tests ran.
"""

SAMPLE_GTEST_JSON = {
    "tests": 2,
    "failures": 1,
    "time": "0.003s",
    "testsuites": [
        {
            "name": "AutoTest",
            "tests": 2,
            "failures": 1,
            "time": "0.003s",
            "testsuite": [
                {
                    "name": "my_add_test_001",
                    "status": "RUN",
                    "time": "0.001s",
                    "classname": "AutoTest",
                    "failures": [],
                },
                {
                    "name": "my_add_test_002",
                    "status": "RUN",
                    "time": "0.002s",
                    "classname": "AutoTest",
                    "failures": [{"failure": "Expected: 5\nWhich is: 6", "type": ""}],
                },
            ],
        }
    ],
}


class TestResultParser:
    def test_parse_gtest_text_counts(self):
        cases, summary = result_parser.parse_gtest_text(SAMPLE_GTEST_TEXT)
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1

    def test_parse_gtest_text_statuses(self):
        cases, _ = result_parser.parse_gtest_text(SAMPLE_GTEST_TEXT)
        by_id = {c["id"]: c for c in cases}
        assert by_id["AutoTest.my_add_test_001"]["status"] == "passed"
        assert by_id["AutoTest.my_add_test_002"]["status"] == "failed"

    def test_parse_gtest_text_failure_message(self):
        cases, _ = result_parser.parse_gtest_text(SAMPLE_GTEST_TEXT)
        failed = next(c for c in cases if c["status"] == "failed")
        assert failed["failure_message"] is not None
        assert "Expected" in failed["failure_message"]

    def test_parse_gtest_text_function_and_id(self):
        cases, _ = result_parser.parse_gtest_text(SAMPLE_GTEST_TEXT)
        passed = next(c for c in cases if c["status"] == "passed")
        assert passed["function_name"] == "my_add"
        assert passed["test_id"] == "test_001"

    def test_parse_gtest_json(self, tmp_path):
        json_path = tmp_path / "result.json"
        json_path.write_text(json.dumps(SAMPLE_GTEST_JSON), encoding="utf-8")
        cases, summary = result_parser.parse_gtest_json(str(json_path), SAMPLE_GTEST_TEXT)
        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1

    def test_parse_gtest_json_failure_message(self, tmp_path):
        json_path = tmp_path / "result.json"
        json_path.write_text(json.dumps(SAMPLE_GTEST_JSON), encoding="utf-8")
        cases, _ = result_parser.parse_gtest_json(str(json_path), "")
        failed = next(c for c in cases if c["status"] == "failed")
        assert "Expected" in (failed["failure_message"] or "")

    def test_parse_time_ms(self):
        assert result_parser._parse_time_ms("0.001s") == 1
        assert result_parser._parse_time_ms("12ms") == 12
        assert result_parser._parse_time_ms("1") == 1000
        assert result_parser._parse_time_ms("bad") == 0

    def test_split_test_name_numeric(self):
        fn, tid = result_parser._split_test_name("my_add_test_001")
        assert fn == "my_add"
        assert tid == "test_001"

    def test_split_test_name_plain(self):
        fn, tid = result_parser._split_test_name("myfunction_case")
        assert fn == "myfunction"
        assert tid == "case"

    def test_empty_output(self):
        cases, summary = result_parser.parse_gtest_text("")
        assert summary["total"] == 0
        assert cases == []


# ---------------------------------------------------------------------------
# runner.build_and_run — mocked tests
# ---------------------------------------------------------------------------

class TestBuildAndRunMocked:
    def test_env_error_returns_env_error_status(self, tmp_path):
        proj = _make_project(tmp_path)
        with patch.object(env_checker, "check_env", return_value={
            "ok": False, "error": "cmake not found", "cmake_version": None,
            "compiler": None, "duration_ms": 1,
        }):
            result = runner.build_and_run(str(proj))
        assert result["overall_status"] == "env_error"
        assert result["errors"]
        assert result["stages"]["env_check"]["status"] == "failed"

    def test_configure_failure(self, tmp_path):
        proj = _make_project(tmp_path)
        with patch.object(env_checker, "check_env", return_value=_passing_env_result()), \
             patch.object(process_manager, "run_process", return_value=(1, "", "cfg error", False)):
            result = runner.build_and_run(str(proj))
        assert result["overall_status"] == "configure_error"
        assert result["stages"]["cmake_configure"]["status"] == "failed"

    def test_configure_timeout(self, tmp_path):
        proj = _make_project(tmp_path)
        with patch.object(env_checker, "check_env", return_value=_passing_env_result()), \
             patch.object(process_manager, "run_process", return_value=(-1, "", "", True)):
            result = runner.build_and_run(str(proj))
        assert result["overall_status"] == "configure_error"
        assert result["stages"]["cmake_configure"]["status"] == "timeout"

    def test_build_failure(self, tmp_path):
        proj = _make_project(tmp_path)
        call_count = 0

        def _mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:   # configure succeeds
                return 0, "", "", False
            return 1, "", "build error", False  # build fails

        with patch.object(env_checker, "check_env", return_value=_passing_env_result()), \
             patch.object(process_manager, "run_process", side_effect=_mock_run):
            result = runner.build_and_run(str(proj))
        assert result["overall_status"] == "build_error"
        assert result["stages"]["build"]["status"] == "failed"

    def test_build_timeout(self, tmp_path):
        proj = _make_project(tmp_path)
        call_count = 0

        def _mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return 0, "", "", False
            return -1, "", "", True

        with patch.object(env_checker, "check_env", return_value=_passing_env_result()), \
             patch.object(process_manager, "run_process", side_effect=_mock_run):
            result = runner.build_and_run(str(proj))
        assert result["overall_status"] == "build_error"
        assert result["stages"]["build"]["status"] == "timeout"

    def test_test_exe_not_found(self, tmp_path):
        proj = _make_project(tmp_path)
        with patch.object(env_checker, "check_env", return_value=_passing_env_result()), \
             patch.object(process_manager, "run_process", return_value=(0, "", "", False)):
            result = runner.build_and_run(str(proj))
        assert result["overall_status"] == "build_error"
        assert any("auto_test" in e for e in result["errors"])

    def test_test_timeout(self, tmp_path):
        proj = _make_project(tmp_path)
        # Create a fake test executable so _find_test_executable succeeds
        build_dir = proj / "build"
        build_dir.mkdir()
        exe_name = "auto_test.exe" if sys.platform == "win32" else "auto_test"
        fake_exe = build_dir / exe_name
        fake_exe.write_text("placeholder")

        call_count = 0

        def _mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:   # configure + build succeed
                return 0, "", "", False
            return -1, "", "", True  # test run times out

        with patch.object(env_checker, "check_env", return_value=_passing_env_result()), \
             patch.object(process_manager, "run_process", side_effect=_mock_run):
            result = runner.build_and_run(str(proj))
        assert result["overall_status"] == "timeout"
        assert result["stages"]["test_run"]["status"] == "timeout"

    def test_full_pass(self, tmp_path):
        proj = _make_project(tmp_path)
        build_dir = proj / "build"
        build_dir.mkdir()
        exe_name = "auto_test.exe" if sys.platform == "win32" else "auto_test"
        fake_exe = build_dir / exe_name
        fake_exe.write_text("placeholder")

        gtest_out = textwrap.dedent("""\
            [==========] Running 1 test
            [ RUN      ] AutoTest.my_func_test_001
            [       OK ] AutoTest.my_func_test_001 (0 ms)
            [==========] 1 test ran.
        """)

        call_count = 0

        def _mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return 0, "", "", False
            return 0, gtest_out, "", False

        with patch.object(env_checker, "check_env", return_value=_passing_env_result()), \
             patch.object(process_manager, "run_process", side_effect=_mock_run):
            result = runner.build_and_run(str(proj))

        assert result["overall_status"] == "passed"
        assert result["summary"]["total"] == 1
        assert result["summary"]["passed"] == 1
        assert result["summary"]["failed"] == 0

    def test_full_fail_one_test(self, tmp_path):
        proj = _make_project(tmp_path)
        build_dir = proj / "build"
        build_dir.mkdir()
        exe_name = "auto_test.exe" if sys.platform == "win32" else "auto_test"
        (build_dir / exe_name).write_text("placeholder")

        gtest_out = textwrap.dedent("""\
            [ RUN      ] AutoTest.my_func_test_001
            [  FAILED  ] AutoTest.my_func_test_001 (0 ms)
        """)

        call_count = 0

        def _mock_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return 0, "", "", False
            return 1, gtest_out, "", False

        with patch.object(env_checker, "check_env", return_value=_passing_env_result()), \
             patch.object(process_manager, "run_process", side_effect=_mock_run):
            result = runner.build_and_run(str(proj))

        assert result["overall_status"] == "failed"
        assert result["summary"]["failed"] == 1

    def test_result_schema(self, tmp_path):
        proj = _make_project(tmp_path)
        with patch.object(env_checker, "check_env", return_value={
            "ok": False, "error": "x", "cmake_version": None,
            "compiler": None, "duration_ms": 0,
        }):
            result = runner.build_and_run(str(proj))

        required_keys = {"schema_version", "project_dir", "run_at", "overall_status",
                         "stages", "summary", "test_cases", "errors"}
        assert required_keys.issubset(result.keys())
        assert result["schema_version"] == "1.0"

    def test_on_output_callback_invoked(self, tmp_path):
        proj = _make_project(tmp_path)
        received = []

        def cb(line, stream, stage):
            received.append((line, stream, stage))

        # Patch process_manager so that the callback is called via a real run_process
        # call with a trivial python command
        def _mock_pm(cmd, on_output=None, stage="", **kwargs):
            if on_output:
                on_output("fake line", "stdout", stage)
            return 0, "fake line", "", False

        with patch.object(env_checker, "check_env", return_value=_passing_env_result()), \
             patch.object(process_manager, "run_process", side_effect=_mock_pm):
            runner.build_and_run(str(proj), {"on_output": cb})

        # At least configure and build callbacks should have fired
        assert len(received) >= 2


# ---------------------------------------------------------------------------
# _find_test_executable
# ---------------------------------------------------------------------------

class TestFindTestExecutable:
    def test_finds_debug_exe(self, tmp_path):
        debug_dir = tmp_path / "Debug"
        debug_dir.mkdir()
        exe = debug_dir / "auto_test.exe"
        exe.write_text("")
        result = runner._find_test_executable(str(tmp_path), "Debug")
        assert result == str(exe)

    def test_finds_root_exe(self, tmp_path):
        exe = tmp_path / "auto_test"
        exe.write_text("")
        result = runner._find_test_executable(str(tmp_path), "Debug")
        assert result == str(exe)

    def test_returns_none_when_missing(self, tmp_path):
        result = runner._find_test_executable(str(tmp_path), "Debug")
        assert result is None
