"""
type_resolver.py — Resolve libclang Type objects to our JSON type description format.
"""
from __future__ import annotations

import clang.cindex as ci

TypeKind = ci.TypeKind

# ---------------------------------------------------------------------------
# TypeKind sets
# ---------------------------------------------------------------------------

_CHAR_KINDS = frozenset({
    TypeKind.CHAR_U, TypeKind.UCHAR, TypeKind.CHAR_S, TypeKind.SCHAR,
    TypeKind.CHAR16, TypeKind.CHAR32, TypeKind.WCHAR,
})

_INTEGER_KINDS = frozenset({
    TypeKind.SHORT, TypeKind.INT, TypeKind.LONG, TypeKind.LONGLONG, TypeKind.INT128,
    TypeKind.USHORT, TypeKind.UINT, TypeKind.ULONG, TypeKind.ULONGLONG, TypeKind.UINT128,
})

_FLOAT_KINDS: set = {TypeKind.FLOAT, TypeKind.DOUBLE, TypeKind.LONGDOUBLE}
for _attr in ("FLOAT128", "HALF", "FLOAT16"):
    _v = getattr(TypeKind, _attr, None)
    if _v is not None:
        _FLOAT_KINDS.add(_v)
_FLOAT_KINDS = frozenset(_FLOAT_KINDS)

_ARRAY_KINDS = frozenset({
    TypeKind.CONSTANTARRAY, TypeKind.INCOMPLETEARRAY,
    TypeKind.VARIABLEARRAY, TypeKind.DEPENDENTSIZEDARRAY,
})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_type(
    clang_type: ci.Type,
    depth: int = 0,
    parse_errors: list | None = None,
) -> dict:
    """
    Convert a libclang Type to our JSON type description dict.

    Args:
        clang_type   - The libclang Type object.
        depth        - Current recursion depth (for pointer/struct nesting).
        parse_errors - List to append non-fatal error dicts to.

    Returns:
        A dict matching the type description schema.
    """
    if parse_errors is None:
        parse_errors = []

    if clang_type.kind == TypeKind.INVALID:
        return _unknown_type(clang_type.spelling or "invalid")

    raw = clang_type.spelling
    canonical_type = clang_type.get_canonical()
    canonical = canonical_type.spelling

    kind = _get_kind(clang_type, canonical_type)
    is_const = clang_type.is_const_qualified()

    result: dict = {
        "raw": raw,
        "canonical": canonical,
        "base_type": _get_base_type(canonical_type),
        "is_const": is_const,
        "is_pointer": False,
        "is_reference": False,
        "is_array": False,
        "array_size": None,
        "pointee_type": None,
        "kind": kind,
    }

    # ---- pointer / function pointer ----
    if kind in ("pointer", "function_pointer"):
        result["is_pointer"] = True
        if kind == "pointer" and depth < 3:
            # Use whichever type actually is a pointer
            ptr_type = (
                clang_type
                if clang_type.kind == TypeKind.POINTER
                else canonical_type
            )
            pointee = ptr_type.get_pointee()
            result["pointee_type"] = resolve_type(pointee, depth + 1, parse_errors)

    # ---- reference ----
    elif kind == "reference":
        result["is_reference"] = True
        if depth < 3:
            ref_type = (
                clang_type
                if clang_type.kind in (TypeKind.LVALUEREFERENCE, TypeKind.RVALUEREFERENCE)
                else canonical_type
            )
            pointee = ref_type.get_pointee()
            result["pointee_type"] = resolve_type(pointee, depth + 1, parse_errors)

    # ---- array ----
    elif kind == "array":
        result["is_array"] = True
        if canonical_type.kind == TypeKind.CONSTANTARRAY:
            result["array_size"] = canonical_type.get_array_size()
        elem_type = canonical_type.get_array_element_type()
        if elem_type.kind != TypeKind.INVALID:
            result["pointee_type"] = resolve_type(elem_type, depth + 1, parse_errors)

    # ---- enum ----
    elif kind == "enum":
        decl = clang_type.get_declaration()
        if decl is None or decl.kind != ci.CursorKind.ENUM_DECL:
            decl = canonical_type.get_declaration()
        if decl and decl.kind == ci.CursorKind.ENUM_DECL:
            result["enum_values"] = _get_enum_values(decl)

    # ---- struct / class ----
    elif kind == "struct":
        if depth >= 3:
            result["kind"] = "unknown"
        else:
            decl = clang_type.get_declaration()
            if decl is None or decl.kind not in (
                ci.CursorKind.STRUCT_DECL, ci.CursorKind.CLASS_DECL
            ):
                decl = canonical_type.get_declaration()
            if decl and decl.kind in (
                ci.CursorKind.STRUCT_DECL, ci.CursorKind.CLASS_DECL
            ):
                result["fields"] = _get_struct_fields(decl, depth + 1, parse_errors)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_kind(t: ci.Type, canonical: ci.Type) -> str:
    """Map a clang Type to our kind string, falling through to canonical."""
    for check in (t, canonical):
        k = check.kind
        if k == TypeKind.VOID:
            return "void"
        if k == TypeKind.BOOL:
            return "bool"
        if k in _CHAR_KINDS:
            return "char"
        if k in _INTEGER_KINDS:
            return "integer"
        if k in _FLOAT_KINDS:
            return "float"
        if k == TypeKind.POINTER:
            pointee = check.get_pointee()
            if pointee.kind in (TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO):
                return "function_pointer"
            return "pointer"
        if k in (TypeKind.LVALUEREFERENCE, TypeKind.RVALUEREFERENCE):
            return "reference"
        if k in _ARRAY_KINDS:
            return "array"
        if k == TypeKind.RECORD:
            return "struct"
        if k == TypeKind.ENUM:
            return "enum"
        if k in (TypeKind.FUNCTIONPROTO, TypeKind.FUNCTIONNOPROTO):
            return "function_pointer"
        # If we've already tried canonical, give up
        if check is canonical:
            break
    return "unknown"


def _get_base_type(canonical_type: ci.Type) -> str:
    """Extract the innermost named type from a canonical type."""
    k = canonical_type.kind
    if k == TypeKind.POINTER:
        return _get_base_type(canonical_type.get_pointee().get_canonical())
    if k in (TypeKind.LVALUEREFERENCE, TypeKind.RVALUEREFERENCE):
        return _get_base_type(canonical_type.get_pointee().get_canonical())
    if k in _ARRAY_KINDS:
        elem = canonical_type.get_array_element_type()
        if elem.kind != TypeKind.INVALID:
            return _get_base_type(elem.get_canonical())
    # Strip qualifiers from the spelling
    spelling = canonical_type.spelling
    for qual in ("const ", "volatile ", "restrict "):
        spelling = spelling.replace(qual, "")
    return spelling.rstrip("*& ").strip() or canonical_type.spelling


def _unknown_type(raw: str) -> dict:
    return {
        "raw": raw,
        "canonical": raw,
        "base_type": raw,
        "is_const": False,
        "is_pointer": False,
        "is_reference": False,
        "is_array": False,
        "array_size": None,
        "pointee_type": None,
        "kind": "unknown",
    }


def _get_enum_values(enum_decl: ci.Cursor) -> list[dict]:
    values = []
    for child in enum_decl.get_children():
        if child.kind == ci.CursorKind.ENUM_CONSTANT_DECL:
            values.append({"name": child.spelling, "value": child.enum_value})
    return values


def _get_struct_fields(
    struct_decl: ci.Cursor,
    depth: int,
    parse_errors: list,
) -> list[dict]:
    fields = []
    for child in struct_decl.get_children():
        if child.kind == ci.CursorKind.FIELD_DECL:
            fields.append({
                "name": child.spelling,
                "type": resolve_type(child.type, depth, parse_errors),
            })
    return fields
