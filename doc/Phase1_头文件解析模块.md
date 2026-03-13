# Phase 1 — 头文件解析模块（Header Parser）

## 你是谁 / 任务背景

你是一名经验丰富的 C++ 工具链工程师。我需要你实现一个 **独立可运行的 Python 模块**，用于解析 C/C++ 头文件，提取其中所有可测试的函数接口信息，并输出为结构化 JSON。

这个模块是一个更大系统（动态库接口自动化测试工具）的第一步，后续模块会消费它的输出。**本阶段只需实现解析功能，不涉及 UI 或测试代码生成。**

---

## 技术选型（必须遵守）

- **语言**：Python 3.10+
- **解析库**：`libclang`（pip 包名：`libclang`），使用其 Python 绑定（`clang.cindex`）
- **不得使用**：正则表达式解析头文件、`pycparser`、`castxml`
- **输出格式**：JSON（符合本文档末尾的 Schema）
- **运行平台**：Linux（Ubuntu 20.04+），兼顾 Windows（可选）

---

## 功能需求

### 1. 入口接口

模块需提供以下 Python 函数作为公开 API：

```python
def parse_header(
    header_path: str,
    include_dirs: list[str] = [],
    compiler_args: list[str] = []
) -> dict:
    """
    解析单个头文件，返回结构化的接口描述字典。

    参数：
        header_path   - 头文件的绝对路径
        include_dirs  - 额外的头文件搜索路径列表
        compiler_args - 传递给 clang 的额外编译参数（如 -std=c++17）

    返回：
        符合本文档 Output Schema 的字典
    """
```

同时提供命令行入口：

```bash
python parser.py --header /path/to/mylib.h \
                 --include /path/to/deps/include \
                 --args "-std=c++17" \
                 --output result.json
```

### 2. 提取内容

对头文件中的每一个**函数声明**，提取以下信息：

| 字段 | 说明 |
|---|---|
| `name` | 函数名（字符串） |
| `return_type` | 返回值类型描述（见类型描述格式） |
| `params` | 参数列表（见参数格式） |
| `is_variadic` | 是否为可变参数函数（bool） |
| `namespace` | 所在命名空间（C++ 类/命名空间前缀，无则为空字符串） |
| `source_file` | 声明所在文件路径 |
| `source_line` | 声明所在行号 |
| `comment` | 紧邻的文档注释（Doxygen 风格，无则为空字符串） |

**参数格式**（每个参数为一个字典）：

| 字段 | 说明 |
|---|---|
| `name` | 参数名（匿名参数填 `"arg0"`, `"arg1"` 等） |
| `type` | 类型描述（见类型描述格式） |
| `default_value` | 默认值字符串（无则为 null） |

**类型描述格式**（嵌套字典）：

```json
{
  "raw": "const int *",
  "canonical": "int const *",
  "base_type": "int",
  "is_const": true,
  "is_pointer": true,
  "is_reference": false,
  "is_array": false,
  "array_size": null,
  "pointee_type": {
    "raw": "const int",
    "base_type": "int",
    "is_const": true,
    "is_pointer": false,
    "is_reference": false
  },
  "kind": "pointer"
}
```

`kind` 字段枚举值：`"void"` / `"bool"` / `"integer"` / `"float"` / `"char"` / `"pointer"` / `"reference"` / `"array"` / `"struct"` / `"enum"` / `"function_pointer"` / `"unknown"`

### 3. 过滤规则（以下内容必须排除）

- 以 `_` 或 `__` 开头的函数（内部符号）
- 函数模板（`is_template = true`，除非是已显式特化的版本）
- 纯虚函数（不可直接调用）
- 析构函数、构造函数（不作为独立接口测试）
- 定义在系统头文件中的函数（路径包含 `/usr/include` 或 `/usr/lib` 的跳过）
- `inline` 函数（可通过参数 `--include-inline` 选择性包含）

### 4. 枚举类型处理

对于参数类型为枚举的情况，额外提取枚举的所有可选值：

```json
{
  "kind": "enum",
  "base_type": "MyEnum",
  "enum_values": [
    {"name": "VALUE_A", "value": 0},
    {"name": "VALUE_B", "value": 1}
  ]
}
```

### 5. 结构体类型处理

对于参数类型为结构体的情况，递归提取其字段信息：

```json
{
  "kind": "struct",
  "base_type": "MyStruct",
  "fields": [
    {"name": "x", "type": { "base_type": "int", "kind": "integer", ... }},
    {"name": "y", "type": { "base_type": "float", "kind": "float", ... }}
  ]
}
```

结构体嵌套深度最多递归 3 层，超过则用 `"kind": "unknown"` 表示。

---

## 完整 Output Schema

```json
{
  "schema_version": "1.0",
  "source_file": "/abs/path/to/mylib.h",
  "parsed_at": "2025-01-01T12:00:00Z",
  "compiler_args": ["-std=c++17"],
  "functions": [
    {
      "name": "my_add",
      "namespace": "",
      "return_type": {
        "raw": "int",
        "base_type": "int",
        "kind": "integer",
        "is_const": false,
        "is_pointer": false,
        "is_reference": false,
        "is_array": false,
        "array_size": null,
        "pointee_type": null
      },
      "params": [
        {
          "name": "a",
          "type": {
            "raw": "int",
            "base_type": "int",
            "kind": "integer",
            "is_const": false,
            "is_pointer": false,
            "is_reference": false,
            "is_array": false,
            "array_size": null,
            "pointee_type": null
          },
          "default_value": null
        }
      ],
      "is_variadic": false,
      "source_file": "/abs/path/to/mylib.h",
      "source_line": 12,
      "comment": "/// Adds two integers."
    }
  ],
  "enums": [],
  "structs": [],
  "parse_errors": []
}
```

`parse_errors` 字段收集解析过程中遇到的非致命错误，格式为：
```json
[{"line": 42, "message": "Cannot resolve type 'UnknownType'"}]
```

---

## 错误处理要求

| 情况 | 处理方式 |
|---|---|
| 头文件不存在 | 抛出 `FileNotFoundError`，附带路径信息 |
| libclang 未安装 | 抛出 `ImportError`，提示安装命令 |
| 解析时出现 clang 诊断错误 | 收集到 `parse_errors`，继续解析其余内容 |
| 无法解析某个类型 | 该类型 `kind` 设为 `"unknown"`，记录到 `parse_errors` |
| 头文件中没有任何可提取函数 | 正常返回，`functions` 为空列表 |

---

## 必须提供的测试用例

用以验证解析器正确性，请随代码一并生成以下测试文件：

**`test_cases/simple.h`** — 包含：
- 基本类型参数函数（int, float, double, bool）
- char* 参数函数
- 返回指针的函数
- void 返回值函数

**`test_cases/advanced.h`** — 包含：
- 结构体参数
- 枚举参数
- 函数指针参数
- 默认参数值
- 命名空间内的函数
- C++ 引用参数

**`test_parser.py`** — 使用 `pytest`，覆盖：
- 每种参数类型能否正确识别 `kind`
- 过滤规则是否生效（内部符号、模板函数）
- `parse_errors` 是否正确填充
- 命令行入口是否输出合法 JSON

---

## 交付物清单

```
header_parser/
├── parser.py          # 主模块（含命令行入口）
├── type_resolver.py   # 类型解析子模块
├── filters.py         # 过滤规则子模块
├── requirements.txt   # 依赖（libclang 版本锁定）
├── README.md          # 安装和使用说明
├── test_cases/
│   ├── simple.h
│   └── advanced.h
└── test_parser.py     # pytest 测试
```

---

## 验收标准

1. `python parser.py --header test_cases/simple.h --output out.json` 能成功运行并输出合法 JSON
2. `pytest test_parser.py` 全部通过
3. 对 `advanced.h` 的解析结果中，枚举类型包含 `enum_values`，结构体类型包含 `fields`
4. 解析含 clang 错误的头文件时不崩溃，错误收集在 `parse_errors` 中
