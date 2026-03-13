"""
env_checker.py — Pre-flight environment validation for the build & run pipeline.

Checks performed (in order):
  1. project_dir exists and contains CMakeLists.txt
  2. cmake is available and version >= 3.14
  3. (Linux/macOS) A C++ compiler (g++ or clang++) is reachable
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import time
from pathlib import Path


def check_env(project_dir: str, cmake_path: str = "cmake") -> dict:
    """
    Perform all pre-flight checks.

    Returns a dict:
        {
            "ok"           : bool,
            "cmake_version": str | None,
            "compiler"     : str | None,
            "error"        : str | None,
            "duration_ms"  : int,
        }
    """
    t0 = time.monotonic()
    result: dict = {
        "ok": True,
        "cmake_version": None,
        "compiler": None,
        "error": None,
        "duration_ms": 0,
    }

    # ---- 1. Project directory ----
    proj = Path(project_dir)
    if not proj.exists():
        return _fail(result, t0, f"Project directory not found: {project_dir}")
    if not (proj / "CMakeLists.txt").exists():
        return _fail(result, t0, f"CMakeLists.txt not found in: {project_dir}")

    # ---- 2. cmake executable ----
    cmake_check = _check_cmake(cmake_path)
    if cmake_check.get("error"):
        return _fail(result, t0, cmake_check["error"])
    result["cmake_version"] = cmake_check["version"]

    # ---- 3. C++ compiler (non-Windows only) ----
    if sys.platform != "win32":
        compiler_check = _check_compiler()
        if compiler_check.get("error"):
            return _fail(result, t0, compiler_check["error"])
        result["compiler"] = compiler_check["compiler"]
    else:
        result["compiler"] = "MSVC / MinGW (Windows)"

    result["duration_ms"] = int((time.monotonic() - t0) * 1000)
    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fail(result: dict, t0: float, error: str) -> dict:
    result["ok"] = False
    result["error"] = error
    result["duration_ms"] = int((time.monotonic() - t0) * 1000)
    return result


def _check_cmake(cmake_path: str) -> dict:
    """Return {"version": str} or {"error": str}."""
    # Resolve via PATH if not absolute
    resolved = shutil.which(cmake_path) if not Path(cmake_path).is_absolute() else cmake_path
    if resolved is None:
        return {"error": f"cmake not found on PATH: {cmake_path}"}

    try:
        proc = subprocess.run(
            [resolved, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        return {"error": f"cmake executable not found: {cmake_path}"}
    except subprocess.TimeoutExpired:
        return {"error": "cmake --version timed out"}

    if proc.returncode != 0:
        return {"error": f"cmake --version returned {proc.returncode}"}

    match = re.search(r"cmake version (\d+\.\d+(?:\.\d+)?)", proc.stdout, re.IGNORECASE)
    if not match:
        return {"error": f"Could not parse cmake version from: {proc.stdout[:120]}"}

    version_str = match.group(1)
    parts = [int(x) for x in version_str.split(".")]
    major, minor = parts[0], parts[1] if len(parts) > 1 else 0
    if major < 3 or (major == 3 and minor < 14):
        return {"error": f"cmake {version_str} is below required 3.14"}

    return {"version": version_str}


def _check_compiler() -> dict:
    """Return {"compiler": str} or {"error": str} (Linux/macOS only)."""
    for exe in ("g++", "clang++"):
        path = shutil.which(exe)
        if path:
            try:
                proc = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                first_line = (proc.stdout or proc.stderr).split("\n")[0].strip()
                return {"compiler": first_line or path}
            except Exception:
                return {"compiler": path}
    return {"error": "No C++ compiler found (tried g++, clang++)"}
