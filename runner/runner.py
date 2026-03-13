"""
runner.py — Phase 3: Build & Run Engine.

Public API
----------
    build_and_run(project_dir, options) -> dict

CLI usage
---------
    python runner.py \\
      --project-dir /tmp/gtest_project_001 \\
      --cmake-path  cmake \\
      --build-type  Debug \\
      --timeout     30 \\
      --output      result.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import env_checker
import process_manager
import result_parser

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_and_run(
    project_dir: str,
    options: dict | None = None,
) -> dict:
    """
    Execute the full cmake configure → build → test pipeline.

    Args:
        project_dir - Phase-2 generated project root (absolute path).
        options     - Optional settings dict (keys listed in module docstring).

    Returns:
        A result dict matching the Phase-3 output schema (schema_version "1.0").
        Never raises — all errors are captured in the returned dict.
    """
    if options is None:
        options = {}

    cmake_path       = options.get("cmake_path",       "cmake")
    build_type       = options.get("build_type",       "Debug")
    jobs             = options.get("jobs",             os.cpu_count() or 4)
    test_timeout     = options.get("test_timeout",     30)
    build_timeout    = options.get("build_timeout",    300)
    cmake_extra_args = options.get("cmake_extra_args", [])
    env_override     = options.get("env",              None)
    on_output        = options.get("on_output",        None)

    project_dir = str(Path(project_dir).resolve())
    build_dir   = str(Path(project_dir) / "build")
    run_at      = _now_utc()
    errors: list[str] = []

    # Initialise all stages as "skipped"
    stages: dict = {
        "env_check"       : _skipped_stage(),
        "cmake_configure" : _skipped_stage(),
        "build"           : _skipped_stage(),
        "test_run"        : _skipped_stage(),
    }

    # Effective subprocess environment
    run_env = dict(env_override) if env_override else dict(os.environ)

    # =========================================================================
    # Step 1 — Environment check
    # =========================================================================
    logger.info("Step 1: environment check")
    t0 = time.monotonic()
    env_result = env_checker.check_env(project_dir, cmake_path)
    env_dur    = int((time.monotonic() - t0) * 1000)

    stages["env_check"] = {
        "status"        : "passed" if env_result["ok"] else "failed",
        "cmake_version" : env_result.get("cmake_version"),
        "compiler"      : env_result.get("compiler"),
        "duration_ms"   : env_dur,
    }

    if not env_result["ok"]:
        err = env_result.get("error", "Unknown env check failure")
        errors.append(err)
        logger.error("Env check failed: %s", err)
        return _make_result(project_dir, run_at, "env_error", stages,
                            [], errors, None)

    # =========================================================================
    # Step 2 — CMake configure
    # =========================================================================
    logger.info("Step 2: cmake configure")
    configure_cmd = [
        cmake_path,
        "-S", project_dir,
        "-B", build_dir,
        f"-DCMAKE_BUILD_TYPE={build_type}",
        *cmake_extra_args,
    ]

    t_cfg = time.monotonic()
    rc, cfg_out, cfg_err, timed_out = process_manager.run_process(
        configure_cmd,
        cwd=project_dir,
        env=run_env,
        timeout=build_timeout,
        on_output=on_output,
        stage="configure",
    )
    cfg_dur = int((time.monotonic() - t_cfg) * 1000)

    if timed_out:
        stages["cmake_configure"] = _stage("timeout", cfg_dur, cfg_out, cfg_err)
        return _make_result(project_dir, run_at, "configure_error",
                            stages, [], errors, None)

    stages["cmake_configure"] = _stage(
        "passed" if rc == 0 else "failed", cfg_dur, cfg_out, cfg_err
    )
    if rc != 0:
        errors.append(f"cmake configure exited with code {rc}")
        logger.error("cmake configure failed (exit %d)", rc)
        return _make_result(project_dir, run_at, "configure_error",
                            stages, [], errors, None)

    # =========================================================================
    # Step 3 — Build
    # =========================================================================
    logger.info("Step 3: cmake build")
    build_cmd = [
        cmake_path, "--build", build_dir,
        "--config", build_type,
        "-j", str(jobs),
    ]

    t_bld = time.monotonic()
    rc, bld_out, bld_err, timed_out = process_manager.run_process(
        build_cmd,
        cwd=project_dir,
        env=run_env,
        timeout=build_timeout,
        on_output=on_output,
        stage="build",
    )
    bld_dur = int((time.monotonic() - t_bld) * 1000)

    if timed_out:
        stages["build"] = _stage("timeout", bld_dur, bld_out, bld_err)
        return _make_result(project_dir, run_at, "build_error",
                            stages, [], errors, None)

    stages["build"] = _stage(
        "passed" if rc == 0 else "failed", bld_dur, bld_out, bld_err
    )
    if rc != 0:
        errors.append(f"cmake build exited with code {rc}")
        logger.error("Build failed (exit %d)", rc)
        return _make_result(project_dir, run_at, "build_error",
                            stages, [], errors, None)

    # =========================================================================
    # Step 4 — Run tests
    # =========================================================================
    logger.info("Step 4: run tests")
    test_exe = _find_test_executable(build_dir, build_type)
    if test_exe is None:
        err = "Test executable 'auto_test' not found in build directory"
        errors.append(err)
        stages["test_run"] = _stage("failed", 0, "", err)
        return _make_result(project_dir, run_at, "build_error",
                            stages, [], errors, None)

    result_json_path = str(Path(build_dir) / "result.json")

    # Inject library path
    test_env = dict(run_env)
    lib_dir  = str(Path(project_dir) / "lib")
    if sys.platform == "win32":
        test_env["PATH"] = lib_dir + os.pathsep + test_env.get("PATH", "")
    else:
        existing = test_env.get("LD_LIBRARY_PATH", "")
        test_env["LD_LIBRARY_PATH"] = (
            lib_dir + (":" + existing if existing else "")
        )

    test_cmd = [
        test_exe,
        f"--gtest_output=json:{result_json_path}",
        "--gtest_color=no",
    ]

    t_tst = time.monotonic()
    rc, tst_out, tst_err, timed_out = process_manager.run_process(
        test_cmd,
        cwd=build_dir,
        env=test_env,
        timeout=test_timeout,
        on_output=on_output,
        stage="test",
    )
    tst_dur = int((time.monotonic() - t_tst) * 1000)

    if timed_out:
        stages["test_run"] = _stage("timeout", tst_dur, tst_out, tst_err)
        return _make_result(project_dir, run_at, "timeout",
                            stages, [], errors, None)

    stages["test_run"] = _stage(
        "passed" if rc == 0 else "failed", tst_dur, tst_out, tst_err
    )

    # =========================================================================
    # Step 5 — Parse results
    # =========================================================================
    logger.info("Step 5: parse results")
    result_json = Path(result_json_path)
    if result_json.exists():
        logger.debug("Parsing GTest JSON: %s", result_json_path)
        test_cases, summary = result_parser.parse_gtest_json(
            str(result_json), tst_out
        )
    else:
        logger.warning("GTest JSON not found, falling back to text parsing")
        test_cases, summary = result_parser.parse_gtest_text(tst_out)

    overall = "passed" if summary["failed"] == 0 and summary["total"] > 0 else (
        "failed" if summary["total"] > 0 else
        ("passed" if rc == 0 else "failed")
    )

    return _make_result(project_dir, run_at, overall, stages,
                        test_cases, errors, summary)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _find_test_executable(build_dir: str, build_type: str) -> str | None:
    """Search common locations for the compiled test executable."""
    bd = Path(build_dir)
    candidates = [
        bd / "auto_test",
        bd / "auto_test.exe",
        bd / build_type / "auto_test.exe",
        bd / build_type / "auto_test",
        bd / "Debug"   / "auto_test.exe",
        bd / "Release" / "auto_test.exe",
        bd / "Debug"   / "auto_test",
    ]
    for c in candidates:
        if c.exists():
            logger.debug("Found test executable: %s", c)
            return str(c)
    return None


def _stage(status: str, duration_ms: int, stdout: str, stderr: str) -> dict:
    return {"status": status, "duration_ms": duration_ms,
            "stdout": stdout, "stderr": stderr}


def _skipped_stage() -> dict:
    return {"status": "skipped", "duration_ms": 0, "stdout": "", "stderr": ""}


def _make_result(
    project_dir: str,
    run_at: str,
    overall_status: str,
    stages: dict,
    test_cases: list[dict],
    errors: list[str],
    summary: dict | None,
) -> dict:
    if summary is None:
        n = len(test_cases)
        p = sum(1 for tc in test_cases if tc["status"] == "passed")
        f = n - p
        dur = stages.get("test_run", {}).get("duration_ms", 0)
        summary = {"total": n, "passed": p, "failed": f, "skipped": 0,
                   "duration_ms": dur}
    return {
        "schema_version" : "1.0",
        "project_dir"    : project_dir,
        "run_at"         : run_at,
        "overall_status" : overall_status,
        "stages"         : stages,
        "summary"        : summary,
        "test_cases"     : test_cases,
        "errors"         : errors,
    }


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    ap = argparse.ArgumentParser(
        description="Build and run a Phase-2 GTest project.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--project-dir", required=True, metavar="DIR",
                    help="Phase-2 generated project directory")
    ap.add_argument("--cmake-path", default="cmake", metavar="PATH",
                    help="cmake executable (default: cmake)")
    ap.add_argument("--build-type", default="Debug",
                    help="CMake build type (default: Debug)")
    ap.add_argument("--timeout", type=int, default=30,
                    help="Test run timeout in seconds (default: 30)")
    ap.add_argument("--build-timeout", type=int, default=300,
                    help="Build timeout in seconds (default: 300)")
    ap.add_argument("--jobs", type=int, default=None,
                    help="Parallel build jobs (default: CPU count)")
    ap.add_argument("--output", default=None, metavar="FILE",
                    help="Output JSON file (default: stdout)")
    ap.add_argument("--verbose", action="store_true",
                    help="Print each build line to stderr")

    args = ap.parse_args()

    def _print_output(line: str, stream: str, stage: str) -> None:
        if args.verbose:
            print(f"[{stage}][{stream}] {line}", file=sys.stderr)

    opts: dict = {
        "cmake_path"    : args.cmake_path,
        "build_type"    : args.build_type,
        "test_timeout"  : args.timeout,
        "build_timeout" : args.build_timeout,
        "on_output"     : _print_output,
    }
    if args.jobs is not None:
        opts["jobs"] = args.jobs

    result = build_and_run(args.project_dir, opts)
    json_str = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(json_str, encoding="utf-8")
        print(f"Result written to {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
