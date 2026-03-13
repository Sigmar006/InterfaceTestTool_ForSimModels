"""
type_mapper.py — Map Phase-1 type descriptors to C++ declaration lines
                 and output-parameter print statements.

Public functions
----------------
get_param_decls(param_name, type_info, value, as_null) -> list[str]
    Returns the declaration line(s) that must appear before the function call.
    The call argument is always *param_name* itself.

get_output_print_stmts(param_name, type_info) -> list[str]
    Returns std::cout statement(s) that print an output parameter after the
    function call.
"""
from __future__ import annotations

import json

from value_encoder import (
    encode_bool,
    encode_float,
    encode_integer,
    escape_cpp_char,
    escape_cpp_string,
)


# ---------------------------------------------------------------------------
# Param declaration generation
# ---------------------------------------------------------------------------

def get_param_decls(
    param_name: str,
    type_info: dict,
    value: str,
    as_null: bool = False,
) -> list[str]:
    """
    Return the C++ declaration line(s) for one function parameter.

    The variable that should be passed to the function call is always
    *param_name* (never val_<name> — references / pointers bind via an alias
    declared with the original name).

    Args:
        param_name  - The C++ variable name (taken from the function signature).
        type_info   - The 'type' sub-dict from the Phase-1 parse result.
        value       - Raw string value provided by the user.
        as_null     - If True and kind is 'pointer', emit nullptr.

    Returns:
        A list of C++ source lines (without leading indentation).
    """
    kind     = type_info.get("kind", "unknown")
    raw      = type_info.get("raw", "auto").strip()
    base     = type_info.get("base_type", "auto").strip() or "auto"
    pointee  = type_info.get("pointee_type") or {}

    # ---- integer ----
    if kind == "integer":
        lit, warn = encode_integer(value, raw)
        lines = []
        if warn:
            lines.append(warn)
        lines.append(f"{raw} {param_name} = {lit};")
        return lines

    # ---- float / double ----
    if kind == "float":
        lit = encode_float(value, raw)
        return [f"{raw} {param_name} = {lit};"]

    # ---- bool ----
    if kind == "bool":
        return [f"bool {param_name} = {encode_bool(value)};"]

    # ---- char (single character) ----
    if kind == "char":
        return [f"char {param_name} = '{escape_cpp_char(value)}';"]

    # ---- pointer ----
    if kind == "pointer":
        if as_null:
            return [f"{base}* {param_name} = nullptr;"]
        # char* / const char* → string literal
        if pointee.get("kind") == "char":
            escaped = escape_cpp_string(value)
            return [f'const char* {param_name} = "{escaped}";']
        # Other pointer — declare value, then take address
        return [
            f"{base} val_{param_name} = {value};",
            f"{base}* {param_name} = &val_{param_name};",
        ]

    # ---- reference ----
    if kind == "reference":
        ref_base = (pointee.get("base_type") or base).strip()
        is_const = pointee.get("is_const", False)
        cv = "const " if is_const else ""
        return [
            f"{cv}{ref_base} val_{param_name} = {value};",
            f"{cv}{ref_base}& {param_name} = val_{param_name};",
        ]

    # ---- array ----
    if kind == "array":
        elem_base = (pointee.get("base_type") or base).strip()
        size = type_info.get("array_size")
        size_str = f"[{size}]" if size else "[]"
        return [f"{elem_base} {param_name}{size_str} = {{{value}}};"]

    # ---- struct / class ----
    if kind == "struct":
        return _struct_decls(param_name, base, type_info, value)

    # ---- enum ----
    if kind == "enum":
        return [f"{base} {param_name} = {value};"]

    # ---- function pointer (complex — emit a comment placeholder) ----
    if kind == "function_pointer":
        return [f"// TODO: set function pointer {raw} {param_name};"]

    # ---- unknown / fallback ----
    return [f"/* {raw} */ auto {param_name} = {value};"]


def _struct_decls(
    param_name: str,
    struct_type: str,
    type_info: dict,
    value: str,
) -> list[str]:
    """Generate zero-init struct + field assignments for a struct-valued param."""
    fields = type_info.get("fields", [])

    # Parse field values: user may supply JSON object or leave empty
    try:
        field_vals: dict = json.loads(value) if value and value.strip().startswith("{") else {}
    except (json.JSONDecodeError, ValueError):
        field_vals = {}

    lines: list[str] = [f"{struct_type} {param_name}{{}};"]
    for field in fields:
        fname    = field["name"]
        ftype    = field.get("type", {})
        fkind    = ftype.get("kind", "integer")
        fraw     = ftype.get("raw", "int")
        fval_raw = str(field_vals.get(fname, "0"))

        if fkind == "float":
            lit = encode_float(fval_raw, fraw)
            lines.append(f"{param_name}.{fname} = {lit};")
        elif fkind == "bool":
            lines.append(f"{param_name}.{fname} = {encode_bool(fval_raw)};")
        elif fkind == "integer":
            lit, _ = encode_integer(fval_raw, fraw)
            lines.append(f"{param_name}.{fname} = {lit};")
        else:
            lines.append(f"{param_name}.{fname} = {fval_raw};")

    return lines


# ---------------------------------------------------------------------------
# Output-parameter print statement generation
# ---------------------------------------------------------------------------

def get_output_print_stmts(param_name: str, type_info: dict) -> list[str]:
    """
    Return std::cout lines that print the value of an output parameter
    after the function has been called.
    """
    kind    = type_info.get("kind", "unknown")
    pointee = type_info.get("pointee_type") or {}

    if kind == "pointer":
        p_kind = pointee.get("kind", "")
        if p_kind == "char":
            # char* — print as string
            return [f'std::cout << "[out] {param_name} = " << {param_name} << std::endl;']
        if p_kind == "struct":
            # struct pointer — print each field
            stmts = []
            for field in pointee.get("fields", []):
                fn = field["name"]
                stmts.append(
                    f'std::cout << "[out] {param_name}->{fn} = " << {param_name}->{fn} << std::endl;'
                )
            return stmts or [f'std::cout << "[out] {param_name} = " << (void*){param_name} << std::endl;']
        # Generic pointer — dereference
        return [f'std::cout << "[out] {param_name} = " << *{param_name} << std::endl;']

    # Non-pointer (reference, basic type, etc.)
    return [f'std::cout << "[out] {param_name} = " << {param_name} << std::endl;']
