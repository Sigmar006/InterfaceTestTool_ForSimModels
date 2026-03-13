# Phase 3 — 编译执行模块（Build & Run Engine）

## 你是谁 / 任务背景

你是一名熟悉 CMake 构建系统和进程管理的 Python 后端工程师。我需要你实现一个 **独立的 Python 模块**，负责接收 Phase 2（代码生成模块）产出的 CMake 工程目录，自动完成 **cmake 配置 → 编译 → 运行测试 → 解析结果** 的全流程，并将结构化结果返回给调用者。

**本模块不涉及 UI，也不生成代码。输入是工程目录路径，输出是结构化的测试结果 JSON。**

---

## 前置依赖

本模块接收 Phase 2 产出的工程目录，结构如下：

```
{project_dir}/
├── CMakeLists.txt
├── test_main.cpp
└── lib/
    ├── mylib.so
    └── mylib.h
```

运行后，模块在工程目录内创建 `build/` 子目录，最终产出 `build/result.json`（GTest XML/JSON 格式）。

---

## 技术选型（必须遵守）

- **语言**：Python 3.10+
- **进程管理**：标准库 `subprocess`（`subprocess.Popen` + 实时读取 stdout/stderr）
- **结果解析**：解析 GTest 的 `--gtest_output=json` 输出
- **超时控制**：使用 `subprocess` 的 `timeout` 参数 + 主动 kill
- **日志**：标准库 `logging`，日志级别可配置
- **不得使用**：`os.system()`，`shell=True`（安全要求）

---

## 功能需求

### 1. 公开 API

```python
def build_and_run(
    project_dir: str,
    options: dict = {}
) -> dict:
    """
    对指定的 CMake 工程执行完整的构建和测试流程。

    参数：
        project_dir - Phase 2 生成的工程根目录绝对路径
        options     - 可选配置（见下文）

    返回：
        符合本文档 Output Schema 的结果字典
    """
```

`options` 支持的键：

| 键 | 默认值 | 说明 |
|---|---|---|
| `cmake_path` | `"cmake"` | cmake 可执行文件路径（支持绝对路径） |
| `build_type` | `"Debug"` | CMake 构建类型 |
| `jobs` | CPU 核数 | 并行编译线程数（`cmake --build . -j N`） |
| `test_timeout` | `30` | 单次测试运行超时秒数 |
| `build_timeout` | `300` | 编译超时秒数 |
| `cmake_extra_args` | `[]` | 传给 `cmake` 配置阶段的额外参数 |
| `env` | 当前环境变量 | 运行时环境变量字典（可用于注入 LD_LIBRARY_PATH 等） |
| `on_output` | `None` | 回调函数 `fn(line: str, stream: str)`，实时接收输出行 |

命令行入口：

```bash
python runner.py \
  --project-dir /tmp/gtest_project_001 \
  --cmake-path /usr/bin/cmake \
  --build-type Debug \
  --timeout 30 \
  --output result.json
```

### 2. 执行流程（严格按步骤顺序）

#### Step 1 — 环境检查

在开始构建前，检查以下条件，任一失败则立即返回错误结果，不继续执行：

- cmake 可执行文件存在且版本 ≥ 3.14（执行 `cmake --version` 解析）
- project_dir 存在且包含 `CMakeLists.txt`
- `lib/` 目录下的动态库文件存在
- （Linux）检查 C++ 编译器是否可用：`which g++ || which clang++`

#### Step 2 — CMake 配置

```python
cmd = [
    cmake_path,
    "-S", project_dir,
    "-B", build_dir,        # build_dir = project_dir/build
    f"-DCMAKE_BUILD_TYPE={build_type}",
    *cmake_extra_args
]
```

- 实时捕获 stdout 和 stderr，通过 `on_output` 回调逐行传出
- 超时：`build_timeout`
- 若退出码非 0，记录为 `cmake_configure` 阶段失败，返回结果

#### Step 3 — 编译

```python
cmd = [
    cmake_path,
    "--build", build_dir,
    "--config", build_type,
    "-j", str(jobs)
]
```

- 实时捕获输出，通过 `on_output` 回调传出
- 超时：`build_timeout`
- 若退出码非 0，记录为 `build` 阶段失败

#### Step 4 — 运行测试

定位编译产出的测试可执行文件（优先查找 `build/auto_test`，Windows 为 `build/Debug/auto_test.exe`）：

```python
cmd = [
    test_executable,
    "--gtest_output=json:result.json",
    "--gtest_color=no"
]
```

设置环境变量：
- Linux：在 `env` 中追加 `LD_LIBRARY_PATH={project_dir}/lib`
- Windows：追加 `PATH={project_dir}/lib`

- 超时：`test_timeout`
- 若超时，强制 kill 进程，记录为 `timeout` 状态

#### Step 5 — 解析结果

读取 `build/result.json`（GTest JSON 格式），解析为本模块的输出 Schema。

### 3. GTest JSON 输出解析规则

GTest `--gtest_output=json` 产出格式示例：

```json
{
  "tests": 2,
  "failures": 1,
  "time": "0.012s",
  "timestamp": "2025-01-01T12:00:00",
  "testsuites": [{
    "name": "AutoTest",
    "tests": 2,
    "failures": 1,
    "testsuite": [
      {
        "name": "my_add_test_001",
        "status": "RUN",
        "result": "COMPLETED",
        "time": "0.001s",
        "classname": "AutoTest",
        "failures": []
      },
      {
        "name": "my_add_test_002",
        "status": "RUN",
        "result": "COMPLETED",
        "time": "0.001s",
        "classname": "AutoTest",
        "failures": [
          { "failure": "test_main.cpp:25\nExpected: my_add(2, 3)\n  Which is: 4\nTo be equal to: 5" }
        ]
      }
    ]
  }]
}
```

解析时同时捕获测试进程的 stdout，提取每个测试用例打印的 `[out]` 和 return 信息，附加到对应用例结果中。

### 4. 输出 Schema

```json
{
  "schema_version": "1.0",
  "project_dir": "/tmp/gtest_project_001",
  "run_at": "2025-01-01T12:00:00Z",
  "overall_status": "passed",
  "stages": {
    "env_check": {
      "status": "passed",
      "cmake_version": "3.28.1",
      "compiler": "g++ 11.4.0",
      "duration_ms": 45
    },
    "cmake_configure": {
      "status": "passed",
      "duration_ms": 12000,
      "stdout": "...",
      "stderr": ""
    },
    "build": {
      "status": "passed",
      "duration_ms": 8500,
      "stdout": "...",
      "stderr": ""
    },
    "test_run": {
      "status": "passed",
      "duration_ms": 32,
      "stdout": "[my_add] return = 5\n",
      "stderr": ""
    }
  },
  "summary": {
    "total": 2,
    "passed": 1,
    "failed": 1,
    "skipped": 0,
    "duration_ms": 32
  },
  "test_cases": [
    {
      "id": "AutoTest.my_add_test_001",
      "function_name": "my_add",
      "test_id": "test_001",
      "status": "passed",
      "duration_ms": 1,
      "stdout_captured": "[my_add] return = 5",
      "failure_message": null
    },
    {
      "id": "AutoTest.my_add_test_002",
      "function_name": "my_add",
      "test_id": "test_002",
      "status": "failed",
      "duration_ms": 1,
      "stdout_captured": "[my_add] return = 4",
      "failure_message": "Expected: my_add(2, 3)\n  Which is: 4\nTo be equal to: 5"
    }
  ],
  "errors": []
}
```

`overall_status` 枚举：`"passed"` / `"failed"` / `"build_error"` / `"configure_error"` / `"timeout"` / `"env_error"`

`stages[*].status` 枚举：`"passed"` / `"failed"` / `"skipped"` / `"timeout"`

### 5. 实时输出回调接口

`on_output` 回调用于 UI 层实时显示构建日志，接口规范：

```python
def on_output(line: str, stream: str, stage: str):
    """
    line  - 输出的单行文本（不含换行符）
    stream - "stdout" 或 "stderr"
    stage  - "configure" / "build" / "test"
    """
```

调用方示例：

```python
def my_callback(line, stream, stage):
    print(f"[{stage}][{stream}] {line}")

result = build_and_run(
    project_dir="/tmp/gtest_project_001",
    options={"on_output": my_callback}
)
```

### 6. 错误处理要求

| 错误情况 | 处理方式 | overall_status |
|---|---|---|
| cmake 不存在 | 环境检查失败，立即返回 | `"env_error"` |
| CMakeLists.txt 不存在 | 环境检查失败 | `"env_error"` |
| cmake configure 失败 | 记录 stderr，返回结果 | `"configure_error"` |
| 编译失败 | 记录 stderr，返回结果 | `"build_error"` |
| 测试运行超时 | kill 进程，返回结果 | `"timeout"` |
| result.json 不存在 | 解析 stdout 中的 GTest 文本输出作为降级方案 | `"failed"` 或 `"passed"` |
| 测试有失败用例 | 正常返回，overall_status 为 `"failed"` | `"failed"` |

### 7. 降级结果解析

当 `build/result.json` 不存在时（网络问题导致 GTest 版本异常等），解析 GTest 的文本输出：

```
[ RUN      ] AutoTest.my_add_test_001
[       OK ] AutoTest.my_add_test_001 (0 ms)
[ RUN      ] AutoTest.my_add_test_002
[  FAILED  ] AutoTest.my_add_test_002 (1 ms)
```

使用正则表达式提取用例名称和状态，填充 `test_cases` 列表，`failure_message` 提取 `FAILED` 行之后直到下一个 `RUN` 行之间的内容。

---

## 必须提供的测试用例

**`test_runner.py`**，使用 pytest 覆盖：

1. **成功路径测试**：给定一个实际可编译的工程（测试文件中预置一个最简 gtest 工程），能完整跑通并返回 `overall_status: "passed"`
2. **cmake 不存在**：`cmake_path` 指向不存在的路径，返回 `overall_status: "env_error"`
3. **编译失败**：给定包含语法错误的 `test_main.cpp`，返回 `overall_status: "build_error"` 且 `stages.build.stderr` 非空
4. **超时**：给定一个包含无限循环的测试（使用 mock 或 sleep），超时后返回 `overall_status: "timeout"`
5. **回调测试**：验证 `on_output` 回调在构建过程中确实被多次调用
6. **结果解析完整性**：`test_cases` 列表数量与 GTest 运行的用例数量一致

测试中可以使用 pytest 的 `tmp_path` fixture 创建临时工程目录，预置最简 CMakeLists.txt 和测试代码。

---

## 交付物清单

```
runner/
├── runner.py             # 主模块（含命令行入口）
├── env_checker.py        # 环境检查子模块
├── process_manager.py    # 子进程管理（封装 Popen）
├── result_parser.py      # GTest 结果解析（JSON + 文本降级）
├── requirements.txt      # 无额外依赖（纯标准库）
├── README.md
└── test_runner.py        # pytest 测试
```

---

## 验收标准

1. 对 Phase 2 生成的真实工程目录，`build_and_run()` 能返回包含正确 `overall_status` 和 `test_cases` 的字典
2. `pytest test_runner.py` 全部通过
3. 构建过程中每一行输出都通过 `on_output` 回调实时传出（不缓冲到结束才一次性返回）
4. 超时场景下，子进程被正确 kill（无僵尸进程）
5. 任何错误情况均不抛出未捕获异常，统一通过返回值传递错误信息
