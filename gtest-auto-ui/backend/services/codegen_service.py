"""
Codegen service — thin wrapper around codegen/codegen.py.

After code generation, if running on Windows and dlltool is available in the
MinGW toolchain, this service also:
  1. Runs gendef on the DLL to create a .def file.
  2. Runs dlltool to create a .dll.a import library in project/lib/.
  3. Patches the generated CMakeLists.txt to add IMPORTED_IMPLIB next to
     IMPORTED_LOCATION so that MinGW linkers can find the import library.

Path layout:
    __file__  = .../InterfaceTestTool/gtest-auto-ui/backend/services/codegen_service.py
    ROOT      = parent x4  →  .../InterfaceTestTool/
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: make codegen importable
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent.parent.parent  # InterfaceTestTool/
_CODEGEN_DIR = str(ROOT / "codegen")
if _CODEGEN_DIR not in sys.path:
    sys.path.insert(0, _CODEGEN_DIR)

from codegen import generate_test_project  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MINGW_BIN = Path(r"C:\msys64\mingw64\bin")


def _build_env_with_mingw() -> dict[str, str]:
    """Return os.environ copy with MinGW bin prepended to PATH (if present)."""
    env = os.environ.copy()
    if _MINGW_BIN.is_dir():
        env["PATH"] = str(_MINGW_BIN) + os.pathsep + env.get("PATH", "")
    return env


def _tool_available(name: str, env: dict[str, str]) -> bool:
    """Check whether *name* is resolvable with the given PATH env."""
    return shutil.which(name, path=env.get("PATH")) is not None


def _create_import_library(dll_path: str, project_dir: str) -> str | None:
    """
    Run gendef + dlltool to produce a .dll.a import library.

    Returns the path to the created .dll.a on success, or None on failure.
    """
    env = _build_env_with_mingw()

    if not (_tool_available("gendef", env) and _tool_available("dlltool", env)):
        return None

    dll = Path(dll_path)
    lib_dir = Path(project_dir) / "lib"
    lib_dir.mkdir(parents=True, exist_ok=True)

    def_file = lib_dir / (dll.stem + ".def")
    implib_file = lib_dir / (dll.name + ".a")

    try:
        # Step 1: generate .def
        subprocess.run(
            ["gendef", "-", str(dll)],
            stdout=def_file.open("w"),
            stderr=subprocess.PIPE,
            env=env,
            check=True,
        )

        # Step 2: create import library
        subprocess.run(
            [
                "dlltool",
                "--dllname", dll.name,
                "--def", str(def_file),
                "--output-lib", str(implib_file),
            ],
            stderr=subprocess.PIPE,
            env=env,
            check=True,
        )

        return str(implib_file)

    except subprocess.CalledProcessError:
        return None


def _patch_cmake_implib(cmake_path: str, implib_path: str) -> None:
    """
    Insert an IMPORTED_IMPLIB property line immediately after the
    IMPORTED_LOCATION line in the generated CMakeLists.txt.
    """
    cmake_file = Path(cmake_path)
    if not cmake_file.is_file():
        return

    text = cmake_file.read_text(encoding="utf-8")
    implib_cmake = implib_path.replace("\\", "/")

    # Only patch if IMPORTED_IMPLIB is not already present
    if "IMPORTED_IMPLIB" in text:
        return

    # Match the IMPORTED_LOCATION line (with optional surrounding whitespace)
    pattern = re.compile(
        r'([ \t]*IMPORTED_LOCATION[ \t]+[^\n]+\n)',
        re.MULTILINE,
    )

    def replacer(m: re.Match) -> str:
        original = m.group(1)
        # Preserve leading indentation
        indent = re.match(r'^([ \t]*)', original).group(1)
        implib_line = f'{indent}IMPORTED_IMPLIB "{implib_cmake}"\n'
        return original + implib_line

    patched, count = pattern.subn(replacer, text)
    if count:
        cmake_file.write_text(patched, encoding="utf-8")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_codegen(
    parse_result: dict,
    test_configs: list,
    lib_path: str,
    header_path: str,
    output_dir: str,
    options: dict,
) -> str:
    """
    Generate a CMake/GTest project from parse_result + test_configs.

    On Windows, also attempts to create a .dll.a import library and patch
    CMakeLists.txt with IMPORTED_IMPLIB when dlltool is available.

    Returns output_dir on success. Raises RuntimeError on failure.
    """
    try:
        generate_test_project(
            parse_result,
            test_configs,
            lib_path,
            header_path,
            output_dir,
            options,
        )
    except Exception as exc:
        raise RuntimeError(
            f"generate_test_project failed for output_dir='{output_dir}': {exc}"
        ) from exc

    # Windows-only: create import library for MinGW linkers
    if os.name == "nt" and lib_path.lower().endswith(".dll"):
        implib = _create_import_library(lib_path, output_dir)
        if implib:
            cmake_file = str(Path(output_dir) / "CMakeLists.txt")
            _patch_cmake_implib(cmake_file, implib)

    return output_dir
