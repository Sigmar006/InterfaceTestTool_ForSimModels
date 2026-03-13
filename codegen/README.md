# codegen — Phase 2: CMake + GTest Project Generator

Consumes the Phase-1 header-parse JSON and user-supplied test configurations to
emit a complete, compilable CMake + GTest project.

---

## Requirements

| Item | Minimum version |
|---|---|
| Python | 3.10+ |
| Jinja2 | 3.1 |
| pytest (tests) | 7.0 |
| CMake (build) | 3.14 |

```bash
pip install -r requirements.txt
```

---

## Quick start

```bash
cd codegen

# Generate a project
python codegen.py \
  --parse-result ../header_parser/out.json \
  --test-config  my_tests.json \
  --lib          /path/to/mylib.so \
  --header       /path/to/mylib.h \
  --output       /tmp/gtest_proj_001

# Build and run (Linux)
cd /tmp/gtest_proj_001
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build
./build/auto_test
```

---

## Python API

```python
from codegen import generate_test_project

out_path = generate_test_project(
    parse_result  = parse_json_dict,   # Phase-1 output
    test_configs  = [test_cfg_dict],   # list of TestConfig dicts
    lib_path      = "/abs/path/mylib.so",
    header_path   = "/abs/path/mylib.h",
    output_dir    = "/tmp/gtest_project",
    options       = {
        "cpp_standard"    : 17,
        "cmake_build_type": "Debug",
        "gtest_version"   : "v1.14.0",
        # "use_local_gtest": "/opt/googletest",  # skip FetchContent
    },
)
```

---

## TestConfig format

```json
{
  "test_id": "test_001",
  "function_name": "my_add",
  "params": [
    { "name": "a", "value": "2", "as_null": false },
    { "name": "b", "value": "3", "as_null": false }
  ],
  "expected_return": {
    "enabled": true,
    "comparator": "EXPECT_EQ",
    "value": "5"
  },
  "output_params": []
}
```

### Supported comparators
`EXPECT_EQ` · `EXPECT_NE` · `EXPECT_GT` · `EXPECT_LT` · `EXPECT_NEAR`

---

## Generated project layout

```
output_dir/
├── CMakeLists.txt    ← fully configured CMake project
├── test_main.cpp     ← GTest source with all TEST() cases
└── lib/
    ├── mylib.so      ← copied from lib_path
    └── mylib.h       ← copied from header_path
```

---

## Running tests

```bash
cd codegen
pytest test_codegen.py -v
```

---

## File layout

```
codegen/
├── codegen.py         ← main module + CLI
├── type_mapper.py     ← param declaration & print-stmt generation
├── value_encoder.py   ← C++ literal encoding helpers
├── templates/
│   ├── CMakeLists.txt.j2
│   ├── test_main.cpp.j2
│   └── test_case.cpp.j2
├── requirements.txt
├── README.md
└── test_codegen.py
```
