"""
value_encoder.py — Convert user-supplied string values to C++ literal text.

All functions receive a raw string (from the UI / test config) and return
a string suitable for embedding directly in generated C++ source code.
Security: no shell-execution code is ever generated.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# String / char escaping
# ---------------------------------------------------------------------------

def escape_cpp_string(s: str) -> str:
    """Return s escaped for use inside a C++ double-quoted string literal."""
    return (
        s.replace("\\", "\\\\")
         .replace('"',  '\\"')
         .replace("\n", "\\n")
         .replace("\r", "\\r")
         .replace("\t", "\\t")
         .replace("\0", "\\0")
    )


def escape_cpp_char(s: str) -> str:
    """Return the first character of s escaped for a C++ char literal."""
    if not s:
        return "\\0"
    c = s[0]
    mapping = {"'": "\\'", "\\": "\\\\", "\n": "\\n",
               "\r": "\\r", "\t": "\\t", "\0": "\\0"}
    return mapping.get(c, c)


# ---------------------------------------------------------------------------
# Scalar literal helpers
# ---------------------------------------------------------------------------

def encode_integer(value: str, raw_type: str = "int") -> tuple[str, str | None]:
    """
    Return (literal, warning_or_None).

    Validates that *value* is parseable as an integer; returns a warning
    comment if not, but always returns the original string as the literal
    so compilation proceeds.
    """
    v = value.strip()
    warning = None
    try:
        int(v, 0)  # accepts 0x / 0b prefixes
    except (ValueError, TypeError):
        warning = f"/* WARNING: '{v}' may not be a valid {raw_type} literal */"
    return v, warning


def encode_float(value: str, raw_type: str = "float") -> str:
    """
    Return a C++ float/double/long-double literal string.

    - float        → append 'f'  if missing
    - double       → no suffix
    - long double  → append 'L'  if missing
    """
    v = value.strip()
    rt_lower = raw_type.lower().replace("const ", "").replace("volatile ", "").strip()

    if "long double" in rt_lower:
        if not v.endswith(("L", "l")):
            v = v.rstrip("fF") + "L"
    elif "double" in rt_lower:
        # Remove any trailing f/F that the user may have typed
        v = v.rstrip("fF")
    else:
        # float
        if not v.endswith(("f", "F")):
            v = v.rstrip("fF") + "f"
    return v


def encode_bool(value: str) -> str:
    """Return 'true' or 'false'."""
    return "true" if value.strip().lower() in ("true", "1", "yes") else "false"
