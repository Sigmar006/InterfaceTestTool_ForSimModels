"""
result_parser.py — Parse GTest output into the Phase-3 result schema.

Two parsing modes
-----------------
1. parse_gtest_json(json_path, stdout_text)
   Primary: reads the ``--gtest_output=json:<path>`` file produced by GTest.

2. parse_gtest_text(stdout_text)
   Fallback: parses the human-readable GTest console output when the JSON
   file is absent.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


# ---------------------------------------------------------------------------
# Primary parser — GTest JSON
# ---------------------------------------------------------------------------

def parse_gtest_json(
    json_path: str,
    stdout_text: str,
) -> tuple[list[dict], dict]:
    """
    Parse a GTest JSON result file.

    Returns:
        (test_cases, summary)
    """
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))

    # Map test-name → captured stdout lines
    stdout_map = _extract_per_test_stdout(stdout_text)

    test_cases: list[dict] = []
    total = passed = failed = 0

    for suite in data.get("testsuites", []):
        suite_name = suite.get("name", "")
        for tc in suite.get("testsuite", []):
            name        = tc.get("name", "")
            full_id     = f"{suite_name}.{name}"
            duration_ms = _parse_time_ms(tc.get("time", "0s"))
            failures    = tc.get("failures", [])

            failure_msg: str | None = None
            if failures:
                failure_msg = "\n".join(
                    f.get("failure", "") for f in failures
                ).strip() or None

            status = "failed" if failures else "passed"
            total += 1
            if status == "passed":
                passed += 1
            else:
                failed += 1

            func_name, test_id = _split_test_name(name)
            test_cases.append({
                "id"              : full_id,
                "function_name"   : func_name,
                "test_id"         : test_id,
                "status"          : status,
                "duration_ms"     : duration_ms,
                "stdout_captured" : stdout_map.get(name, ""),
                "failure_message" : failure_msg,
            })

    overall_ms = _parse_time_ms(data.get("time", "0s"))
    summary = {
        "total"      : total,
        "passed"     : passed,
        "failed"     : failed,
        "skipped"    : 0,
        "duration_ms": overall_ms,
    }
    return test_cases, summary


# ---------------------------------------------------------------------------
# Fallback parser — GTest text output
# ---------------------------------------------------------------------------

_RE_RUN    = re.compile(r"\[\s+RUN\s+\]\s+(\S+)")
_RE_OK     = re.compile(r"\[\s+OK\s+\]\s+(\S+)(?:\s+\((\d+)\s+ms\))?")
_RE_FAILED = re.compile(r"\[\s+FAILED\s+\]\s+(\S+)(?:\s+\((\d+)\s+ms\))?")
_RE_GTEST  = re.compile(r"^\[[-= ]+\]")  # GTest banner lines


def parse_gtest_text(stdout_text: str) -> tuple[list[dict], dict]:
    """
    Fallback: parse GTest plain-text console output.

    Returns:
        (test_cases, summary)
    """
    test_cases: list[dict] = []
    total = passed = failed = 0

    current_name: str | None = None
    user_lines:   list[str]  = []
    fail_lines:   list[str]  = []

    for line in stdout_text.splitlines():
        run_m  = _RE_RUN.match(line)
        ok_m   = _RE_OK.match(line)
        fail_m = _RE_FAILED.match(line)

        if run_m:
            current_name = run_m.group(1)
            user_lines   = []
            fail_lines   = []

        elif ok_m:
            full_id     = ok_m.group(1)
            duration_ms = int(ok_m.group(2) or 0)
            _, name     = _split_suite_test(full_id)
            func_name, test_id = _split_test_name(name)
            test_cases.append({
                "id"              : full_id,
                "function_name"   : func_name,
                "test_id"         : test_id,
                "status"          : "passed",
                "duration_ms"     : duration_ms,
                "stdout_captured" : "\n".join(user_lines).strip(),
                "failure_message" : None,
            })
            total += 1; passed += 1
            current_name = None

        elif fail_m:
            full_id     = fail_m.group(1)
            duration_ms = int(fail_m.group(2) or 0)
            _, name     = _split_suite_test(full_id)
            func_name, test_id = _split_test_name(name)
            test_cases.append({
                "id"              : full_id,
                "function_name"   : func_name,
                "test_id"         : test_id,
                "status"          : "failed",
                "duration_ms"     : duration_ms,
                "stdout_captured" : "\n".join(user_lines).strip(),
                "failure_message" : "\n".join(fail_lines).strip() or None,
            })
            total += 1; failed += 1
            current_name = None

        elif current_name:
            if _RE_GTEST.match(line):
                pass  # skip GTest banner lines
            elif any(kw in line for kw in ("Expected:", "Which is:", "To be equal")):
                fail_lines.append(line)
            else:
                user_lines.append(line)

    summary = {
        "total"      : total,
        "passed"     : passed,
        "failed"     : failed,
        "skipped"    : 0,
        "duration_ms": 0,
    }
    return test_cases, summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_per_test_stdout(stdout_text: str) -> dict[str, str]:
    """
    Map test case name → user output lines between [ RUN ] and [ OK ]/[ FAILED ].
    """
    result: dict[str, str] = {}
    current_name: str | None  = None
    lines: list[str] = []

    for line in stdout_text.splitlines():
        run_m = _RE_RUN.match(line)
        end_m = _RE_OK.match(line) or _RE_FAILED.match(line)

        if run_m:
            _, name      = _split_suite_test(run_m.group(1))
            current_name = name
            lines        = []
        elif end_m:
            if current_name:
                result[current_name] = "\n".join(lines).strip()
            current_name = None
            lines        = []
        elif current_name and not _RE_GTEST.match(line):
            lines.append(line)

    return result


def _split_suite_test(full_id: str) -> tuple[str, str]:
    """'AutoTest.my_func_test_001' → ('AutoTest', 'my_func_test_001')"""
    parts = full_id.split(".", 1)
    return (parts[0], parts[1]) if len(parts) == 2 else ("", full_id)


def _split_test_name(test_name: str) -> tuple[str, str]:
    """
    Split a GTest test name like 'my_add_test_001' into
    (function_name='my_add', test_id='test_001').

    Strategy: if the last two underscore-separated tokens look like
    ``<word>_<digits>`` (common test ID pattern), treat that as the test_id.
    Otherwise split at the last underscore.
    """
    parts = test_name.rsplit("_", 2)
    if len(parts) == 3:
        try:
            int(parts[2])           # last part is numeric → "test_001" style
            return parts[0], f"{parts[1]}_{parts[2]}"
        except ValueError:
            pass
    parts2 = test_name.rsplit("_", 1)
    if len(parts2) == 2:
        return parts2[0], parts2[1]
    return test_name, test_name


def _parse_time_ms(time_str: str) -> int:
    """Convert GTest time strings ('0.001s', '12ms', '1') to milliseconds."""
    s = str(time_str).strip()
    try:
        if s.endswith("ms"):
            return max(0, int(float(s[:-2])))
        if s.endswith("s"):
            return max(0, int(float(s[:-1]) * 1000))
        return max(0, int(float(s) * 1000))
    except (ValueError, TypeError):
        return 0
