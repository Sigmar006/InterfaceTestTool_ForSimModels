# Phase 2 — 代码生成模块（Code Generator）

## 你是谁 / 任务背景

你是一名熟悉 CMake 和 Google Test 的 C++ 构建系统工程师。我需要你实现一个 **独立的 Python 代码生成模块**，它接收来自 Phase 1（头文件解析模块）产出的函数描述 JSON 和用户填写的测试参数，生成一个完整可编译的 CMake + GTest 测试工程。

**本模块不涉及 UI，也不负责执行编译。输入是 JSON 数据，输出是磁盘上的工程文件目录。**

---

## 前置依赖（本模块的输入来源）

本模块消费 Phase 1 产出的函数描述 JSON，格式参考如下（简化版）：

```json
{
  "functions": [
    {
      "name": "my_add",
      "namespace": "",
      "return_type": { "raw": "int", "kind": "integer", "is_pointer": false },
      "params": [
        { "name": "a", "type": { "raw": "int", "kind": "integer", "is_pointer": false }, "default_value": null },
        { "name": "b", "type": { "raw": "int", "kind": "integer", "is_pointer": false }, "default_value": null }
      ],
      "is_variadic": false
    }
  ]
}
```

用户通过 UI（或命令行）额外提供的测试配置（**TestConfig**）格式如下：

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
  "output_params": ["result_buf"],
  "timeout_ms": 5000
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `params[].value` | 用户填写的参数值（字符串形式，生成时转换为对应类型） |
| `params[].as_null` | 若为 true，指针参数传 nullptr |
| `expected_return.enabled` | 是否对返回值做断言 |
| `expected_return.comparator` | 断言宏：`EXPECT_EQ` / `EXPECT_NE` / `EXPECT_GT` / `EXPECT_LT` / `EXPECT_NEAR` |
| `expected_return.value` | 期望返回值（字符串形式） |
| `output_params` | 输出参数名列表，调用后 cout 打印其值 |

---

## 技术选型（必须遵守）

- **语言**：Python 3.10+
- **模板引擎**：`Jinja2`（pip install jinja2）
- **GTest 版本**：通过 CMake FetchContent 自动拉取，版本固定为 `v1.14.0`
- **CMake 最低版本**：3.14
- **C++ 标准**：默认 C++17，可配置
- **不得使用**：字符串拼接生成代码（必须全部用 Jinja2 模板）

---

## 功能需求

### 1. 公开 API

```python
def generate_test_project(
    parse_result: dict,          # Phase 1 输出的完整解析结果
    test_configs: list[dict],    # 用户的测试配置列表（可多个）
    lib_path: str,               # 动态库文件的绝对路径（.so 或 .dll）
    header_path: str,            # 头文件绝对路径
    output_dir: str,             # 生成的工程输出目录
    options: dict = {}           # 可选配置，见下文
) -> str:
    """
    生成完整的 CMake + GTest 工程到 output_dir。
    返回工程根目录的绝对路径。
    """
```

`options` 支持的键：

| 键 | 默认值 | 说明 |
|---|---|---|
| `cpp_standard` | `17` | C++ 标准版本 |
| `cmake_build_type` | `"Debug"` | 编译类型 |
| `extra_cmake_flags` | `[]` | 附加 CMake 参数 |
| `gtest_version` | `"v1.14.0"` | GTest 版本 tag |
| `gtest_fetch_url` | GitHub ZIP URL | 可替换为私有镜像 |
| `use_local_gtest` | `null` | 若指定本地 GTest 路径，跳过 FetchContent |

命令行入口：

```bash
python codegen.py \
  --parse-result parse_output.json \
  --test-config test_config.json \
  --lib /path/to/mylib.so \
  --header /path/to/mylib.h \
  --output /tmp/gtest_project_001
```

### 2. 生成的工程目录结构

```
{output_dir}/
├── CMakeLists.txt
├── test_main.cpp
└── lib/
    ├── mylib.so       （从 lib_path 复制）
    └── mylib.h        （从 header_path 复制）
```

### 3. CMakeLists.txt 生成规则

生成内容必须包含：

```cmake
cmake_minimum_required(VERSION 3.14)
project(AutoGTestProject CXX)

set(CMAKE_CXX_STANDARD {{ cpp_standard }})
set(CMAKE_BUILD_TYPE {{ build_type }})

# GTest 依赖（FetchContent 或本地路径二选一）
include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/{{ gtest_version }}.zip
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

# 被测动态库
add_library(target_lib SHARED IMPORTED)
set_target_properties(target_lib PROPERTIES
  IMPORTED_LOCATION "${CMAKE_CURRENT_SOURCE_DIR}/lib/{{ lib_filename }}"
)

# 测试可执行文件
add_executable(auto_test test_main.cpp)
target_include_directories(auto_test PRIVATE lib/)
target_link_libraries(auto_test PRIVATE target_lib GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(auto_test)
```

### 4. test_main.cpp 生成规则

#### 4.1 文件结构

```cpp
// 自动生成 — 请勿手动编辑
// 生成时间: {{ generated_at }}
// 被测函数: {{ function_names | join(", ") }}

#include <gtest/gtest.h>
#include <iostream>
#include <string>
#include "{{ header_filename }}"

// ===== 测试用例 =====
{% for test in tests %}
{{ test.body }}
{% endfor %}
```

#### 4.2 单个测试用例生成规则

对每个 TestConfig 生成一个 `TEST()` 宏块，命名格式：`TEST(AutoTest, {{ function_name }}_{{ test_id }})`

生成示例（针对 `my_add(int a, int b)` + 用户填参 a=2, b=3, expected=5）：

```cpp
TEST(AutoTest, my_add_test_001) {
    // 参数声明
    int a = 2;
    int b = 3;

    // 调用被测函数
    int result = my_add(a, b);

    // 打印返回值（始终打印，便于调试）
    std::cout << "[my_add] return = " << result << std::endl;

    // 用户断言
    EXPECT_EQ(result, 5);
}
```

#### 4.3 各参数类型的代码生成规则

| 参数 kind | 生成的变量声明 | 说明 |
|---|---|---|
| `integer` | `int a = {value};` | 直接赋值 |
| `float` | `float a = {value}f;` | 加 f 后缀 |
| `double` | `double a = {value};` | 直接赋值 |
| `bool` | `bool a = {true\|false};` | 转换 "true"/"false" 字符串 |
| `char*` / `pointer to char` | `const char* a = "{value}";` | 加引号 |
| `pointer`（非 char*，as_null=false） | `{base_type} val_a = {value}; {base_type}* a = &val_a;` | 声明值变量，取地址 |
| `pointer`（as_null=true） | `{base_type}* a = nullptr;` | 传空指针 |
| `reference` | `{base_type} val_a = {value}; {base_type}& a = val_a;` | 声明引用 |
| `array` | `{base_type} a[] = { {values} };` | 逗号分隔值列表 |
| `struct` | 逐字段声明 + 初始化列表 | 见下方结构体规则 |
| `enum` | `{enum_type} a = {enum_type}::{value};` | 使用枚举值名称 |

**结构体生成规则**：

```cpp
MyStruct val_a;
val_a.x = 1;
val_a.y = 2.5f;
MyStruct* a = &val_a;   // 若参数类型为指针
// 或
MyStruct& a = val_a;    // 若参数类型为引用
```

#### 4.4 输出参数打印

对于 `output_params` 列表中的参数，在函数调用后插入打印语句：

- 若为基础类型指针：`std::cout << "[out] param_name = " << *param_name << std::endl;`
- 若为 char*：`std::cout << "[out] param_name = " << param_name << std::endl;`
- 若为结构体指针：逐字段打印

#### 4.5 无返回值（void）函数

不声明 result 变量，无断言，仅打印"调用完成"：

```cpp
my_func(a, b);
std::cout << "[my_func] called successfully" << std::endl;
```

#### 4.6 命名空间函数

在调用时加上命名空间前缀：

```cpp
int result = MyNamespace::my_func(a, b);
```

### 5. 代码安全性要求

- 用户输入的字符串值必须做 C++ 字符串转义（`\n` → `\\n`，`"` → `\"`）
- 数值类型做范围校验：若用户输入的值超出类型范围，生成注释警告但仍生成代码
- 不得生成任何形式的 `system()` 调用或 shell 命令执行

---

## Jinja2 模板文件结构

所有代码生成必须通过模板文件，不得在 Python 代码中直接拼接 C++ 字符串。

```
codegen/
├── templates/
│   ├── CMakeLists.txt.j2    # CMake 模板
│   ├── test_main.cpp.j2     # 主测试文件模板
│   └── test_case.cpp.j2     # 单个测试用例片段模板
```

---

## 必须提供的测试用例

**`test_codegen.py`**，使用 pytest 覆盖：

1. 给定简单 int 参数函数的 parse_result + test_config，生成的 `test_main.cpp` 包含正确的 `TEST()` 名称
2. 指针参数生成正确的取地址代码
3. `as_null=true` 的指针参数生成 `nullptr`
4. 枚举参数生成正确的枚举值引用
5. 期望断言宏正确（`EXPECT_EQ`/`EXPECT_NEAR` 等）
6. 生成的目录结构正确（CMakeLists.txt、test_main.cpp、lib/ 目录存在）
7. 生成的 CMakeLists.txt 包含正确的库文件名

---

## 交付物清单

```
codegen/
├── codegen.py              # 主模块（含命令行入口）
├── type_mapper.py          # 类型 → 代码生成规则映射
├── value_encoder.py        # 用户输入值 → C++ 字面量转换
├── templates/
│   ├── CMakeLists.txt.j2
│   ├── test_main.cpp.j2
│   └── test_case.cpp.j2
├── requirements.txt        # jinja2 等依赖
├── README.md
└── test_codegen.py         # pytest 测试
```

---

## 验收标准

1. 对一个包含 `int my_add(int a, int b)` 的 parse_result，生成工程后，手动运行 `cmake -B build && cmake --build build && ./build/auto_test` 能编译通过并输出 GTest 结果
2. `pytest test_codegen.py` 全部通过
3. 生成的 `test_main.cpp` 通过 `clang-format` 格式检查（无语法错误）
4. 模板文件与 Python 逻辑完全分离，Python 文件中不含任何 C++ 代码字符串
