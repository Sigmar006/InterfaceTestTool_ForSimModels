# header_parser — Phase 1: Header File Parsing Module

Parses C/C++ header files using **libclang** and emits structured JSON describing all publicly testable function interfaces.

---

## Requirements

| Item | Minimum version |
|---|---|
| Python | 3.10+ |
| libclang | 16.0 |
| pytest (for tests) | 7.0 |

Install dependencies:

```bash
pip install -r requirements.txt
```

On Linux you may also need the system LLVM/Clang shared library:

```bash
# Ubuntu / Debian
sudo apt install libclang-dev
# or a specific version:
sudo apt install libclang-16-dev
```

If libclang cannot find `stddef.h` or other built-in headers, pass the Clang
resource directory via `--include`:

```bash
python parser.py --header mylib.h \
                 --include /usr/lib/llvm-16/lib/clang/16/include
```

---

## Quick start

```bash
cd header_parser

# Parse a header, print JSON to stdout
python parser.py --header test_cases/simple.h

# Parse with C++17 mode and save to file
python parser.py --header test_cases/advanced.h \
                 --args "-std=c++17" \
                 --output result.json

# Include inline functions (excluded by default)
python parser.py --header mylib.h --include-inline
```

---

## Python API

```python
from header_parser.parser import parse_header

result = parse_header(
    header_path="/abs/path/to/mylib.h",
    include_dirs=["/path/to/deps/include"],
    compiler_args=["-std=c++17"],
    include_inline=False,   # optional
)
```

The returned dict matches the `schema_version: "1.0"` schema (see below).

---

## Output schema summary

```json
{
  "schema_version": "1.0",
  "source_file": "/abs/path/to/mylib.h",
  "parsed_at": "2025-01-01T12:00:00Z",
  "compiler_args": ["-std=c++17"],
  "functions": [ ... ],
  "enums":     [ ... ],
  "structs":   [ ... ],
  "parse_errors": [ {"line": 42, "message": "..."} ]
}
```

Each function entry:

```json
{
  "name": "my_add",
  "namespace": "",
  "return_type": { "raw": "int", "kind": "integer", ... },
  "params": [
    { "name": "a", "type": { "raw": "int", "kind": "integer", ... }, "default_value": null }
  ],
  "is_variadic": false,
  "source_file": "/abs/path/to/mylib.h",
  "source_line": 12,
  "comment": "/// Adds two integers."
}
```

### `kind` values

`void` · `bool` · `integer` · `float` · `char` · `pointer` · `reference` ·
`array` · `struct` · `enum` · `function_pointer` · `unknown`

---

## Running tests

```bash
cd header_parser
pytest test_parser.py -v
```

---

## Filtering rules (what is excluded)

| Rule | Reason |
|---|---|
| Names starting with `_` | Internal / compiler-reserved symbols |
| Function templates | Not directly callable |
| Pure virtual methods | Cannot be invoked without override |
| Constructors / destructors | Not independent testable interfaces |
| Non-static class methods | Require an object instance |
| Definitions in headers (inline) | Excluded by default; use `--include-inline` to include |
| Functions from system headers | `/usr/include`, `/usr/lib`, Windows SDK paths |

---

## File layout

```
header_parser/
├── parser.py          ← main module + CLI entry point
├── type_resolver.py   ← libclang Type → JSON type dict
├── filters.py         ← inclusion / exclusion rules
├── requirements.txt
├── README.md
├── test_cases/
│   ├── simple.h       ← basic types (int, float, bool, char*, pointer, void)
│   └── advanced.h     ← structs, enums, namespaces, defaults, refs, variadic
└── test_parser.py     ← pytest test suite
```
