# Phase 4 — 可视化界面层（UI Layer）

## 你是谁 / 任务背景

你是一名全栈工程师，熟悉 Python FastAPI 后端和 React 前端开发。我需要你将前三个阶段（头文件解析、代码生成、编译执行）整合为一个完整的 **可视化 Web 应用**，让用户通过浏览器完成动态库接口的全流程自动化测试，无需手写任何代码。

---

## 系统整体架构

```
用户浏览器 (React)
      ↕ HTTP / WebSocket
后端服务 (FastAPI, Python)
      ↓ 调用
Phase 1: header_parser/parser.py
Phase 2: codegen/codegen.py
Phase 3: runner/runner.py
```

**后端**负责：文件管理、调用三个子模块、管理任务状态、通过 WebSocket 推送实时日志。

**前端**负责：文件上传、接口列表展示、动态表单渲染、实时日志显示、结果可视化。

---

## 技术选型（必须遵守）

| 层 | 技术 | 版本要求 |
|---|---|---|
| 后端框架 | FastAPI | ≥ 0.110 |
| 实时通信 | WebSocket（FastAPI 内置） | — |
| 任务管理 | Python `asyncio` + `concurrent.futures` | — |
| 前端框架 | React | 18+ |
| UI 组件库 | Ant Design (antd) | 5.x |
| 状态管理 | React `useState` + `useContext`（不使用 Redux） | — |
| 构建工具 | Vite | — |
| HTTP 客户端 | `axios` | — |
| 代码高亮 | `react-syntax-highlighter` | — |
| 不得使用 | Next.js、TypeScript（保持 JS） | — |

---

## 后端 API 规范

### 基础配置

- 所有 API 前缀：`/api/v1`
- 文件上传目录：`./workspace/{session_id}/uploads/`
- 生成工程目录：`./workspace/{session_id}/projects/{project_id}/`
- CORS：开发环境允许所有来源

### API 列表

#### 1. 创建会话

```
POST /api/v1/session
Response: { "session_id": "uuid-xxx" }
```

每次用户打开应用创建一个会话，所有后续操作挂载在 session_id 下。

#### 2. 上传文件

```
POST /api/v1/session/{session_id}/upload
Content-Type: multipart/form-data
Body: files[]  （支持同时上传多个文件）

Response:
{
  "uploaded": [
    { "filename": "mylib.so",  "type": "library", "path": "..." },
    { "filename": "mylib.h",   "type": "header",  "path": "..." }
  ]
}
```

文件类型自动识别：`.so`/`.dll` → `library`，`.h`/`.hpp` → `header`。

#### 3. 解析头文件

```
POST /api/v1/session/{session_id}/parse
Body:
{
  "header_filename": "mylib.h",
  "include_dirs": [],
  "compiler_args": ["-std=c++17"]
}

Response:
{
  "parse_id": "uuid-yyy",
  "status": "success",
  "functions": [ ... ],   // Phase 1 输出的 functions 列表
  "parse_errors": []
}
```

该接口**同步**返回（解析通常很快），若失败返回 HTTP 422 + 错误详情。

#### 4. 提交测试配置并执行

```
POST /api/v1/session/{session_id}/run
Body:
{
  "parse_id": "uuid-yyy",
  "library_filename": "mylib.so",
  "test_configs": [
    {
      "test_id": "test_001",
      "function_name": "my_add",
      "params": [
        { "name": "a", "value": "2", "as_null": false },
        { "name": "b", "value": "3", "as_null": false }
      ],
      "expected_return": { "enabled": true, "comparator": "EXPECT_EQ", "value": "5" },
      "output_params": []
    }
  ],
  "options": {
    "cmake_path": "cmake",
    "build_type": "Debug",
    "test_timeout": 30
  }
}

Response:
{
  "run_id": "uuid-zzz",
  "status": "queued"
}
```

该接口**异步**，立即返回 `run_id`，实际执行通过后台任务完成，进度通过 WebSocket 推送。

#### 5. WebSocket 实时日志

```
WS /api/v1/ws/{run_id}
```

服务端推送的消息格式：

```json
// 阶段开始
{ "type": "stage_start", "stage": "build", "timestamp": "..." }

// 日志行
{ "type": "log", "stage": "build", "stream": "stdout", "line": "...", "timestamp": "..." }

// 阶段完成
{ "type": "stage_done", "stage": "build", "status": "passed", "duration_ms": 8500 }

// 全部完成
{ "type": "done", "result": { ... } }  // result 为 Phase 3 的完整输出 Schema

// 错误
{ "type": "error", "message": "..." }
```

#### 6. 查询运行结果

```
GET /api/v1/run/{run_id}/result

Response: Phase 3 的完整输出 Schema（run 完成后可用）
```

#### 7. 查询历史运行记录

```
GET /api/v1/session/{session_id}/history

Response:
{
  "runs": [
    { "run_id": "...", "run_at": "...", "overall_status": "passed", "summary": {...} }
  ]
}
```

---

## 前端页面与交互规范

### 页面整体布局

采用三栏布局：

```
┌─────────────────────────────────────────────────────────┐
│  顶部导航栏：Logo + 项目名 + 全局设置按钮                    │
├──────────────┬──────────────────────┬────────────────────┤
│  左栏        │  中央主区域           │  右栏              │
│  接口列表    │  入参配置表单         │  测试结果 / 日志    │
│  (240px)    │  (flex grow)         │  (360px)           │
└──────────────┴──────────────────────┴────────────────────┘
```

### 工作流步骤指示器

页面顶部显示步骤进度条：

```
[1. 上传文件] → [2. 解析接口] → [3. 配置参数] → [4. 运行测试] → [5. 查看结果]
```

当前步骤高亮，已完成步骤显示勾选图标。

### 左栏 — 接口列表

- 顶部有搜索框，支持按函数名模糊搜索
- 每个函数显示为卡片，包含：函数名（加粗）、返回值类型标签、参数数量标签
- 点击函数卡片后高亮选中，中央区域更新为该函数的入参表单
- 支持多选（Ctrl+点击），多选时中央区域显示批量配置提示

### 中央栏 — 入参配置表单

根据所选函数的参数类型，动态渲染输入控件：

| 参数类型 | 渲染控件 | 校验规则 |
|---|---|---|
| `integer` (int/long/short) | 数字输入框（`<InputNumber>`） | 整数，显示类型范围提示 |
| `float` / `double` | 数字输入框（允许小数） | 浮点数 |
| `bool` | Switch 开关 | — |
| `char*` | 文本输入框 | 无限制 |
| `pointer`（非 char*） | 分组控件：单选（传值 / 传 nullptr）+ 值输入框 | — |
| `array` | 动态列表：可添加/删除行，每行一个输入框 | 数量 ≥ 1 |
| `struct` | 折叠面板（Collapse），展开后逐字段渲染子控件 | — |
| `enum` | 下拉选择框（Select），选项从枚举值自动生成 | — |
| `reference` | 与对应基础类型相同的控件 | — |

每个输入控件旁显示：
- 参数名（加粗）
- 类型标签（`int`、`const char*` 等，灰色小字）
- 若有默认值，显示"默认: {value}"提示

表单底部区域：

```
┌─────────────────────────────────────┐
│  期望返回值（可选）                    │
│  [启用断言 Switch]                   │
│  断言类型: [EXPECT_EQ ▼]  期望值: [  ]│
├─────────────────────────────────────┤
│  输出参数标记（勾选后运行时打印其值）    │
│  □ param_a  □ param_b               │
├─────────────────────────────────────┤
│  [保存为测试用例]  [▶ 立即运行]        │
└─────────────────────────────────────┘
```

点击「立即运行」时：
1. 前端校验表单（必填项检查、类型范围检查）
2. 调用 `POST /api/v1/session/{sid}/run`
3. 右栏切换到"运行日志"视图
4. 建立 WebSocket 连接，实时展示日志

### 右栏 — 结果与日志

**日志视图**（运行中）：

- 按阶段分组展示日志：`配置 CMake` / `编译` / `运行测试`
- 每个阶段有折叠功能（默认展开当前阶段，已完成阶段自动折叠）
- 日志行用等宽字体（monospace）显示
- `stderr` 行用浅红色背景标注
- 底部显示当前阶段进度（旋转加载图标 + 阶段名称）

**结果视图**（运行完成后自动切换）：

顶部摘要卡片：

```
✓ 通过  2/3 用例      ✗ 失败  1/3 用例      耗时 1.23s
```

用例列表：

每个用例一行，包含：
- 状态图标（绿勾 / 红叉）
- 用例 ID 和函数名
- 耗时
- 展开按钮（点击后显示：实际调用语句、返回值、失败详情）

失败用例展开后显示：

```
调用:  my_add(2, 3)
返回值: 4
期望:  EXPECT_EQ(result, 5)
失败信息:
  Expected: my_add(2, 3)
    Which is: 4
  To be equal to: 5
```

### 文件上传区域

页面初始状态（未上传文件时）显示上传区域，支持：

- 拖拽上传（Dragger 组件）
- 点击选择文件
- 同时选择 `.so`/`.dll` 和 `.h`/`.hpp` 文件
- 上传后显示文件列表，标注文件类型标签

上传成功后自动触发解析，显示解析进度（loading）。

### 全局设置面板（右上角齿轮图标）

点击后弹出 Drawer，包含：

- cmake 路径（文本输入，带"检测"按钮，点击后验证 cmake 是否可用）
- 编译类型（Debug / Release，单选）
- C++ 标准（14 / 17 / 20，单选）
- 测试超时时间（数字输入，单位秒）
- GTest 版本（文本输入）
- 设置保存到 `localStorage`，跨刷新保留

### 历史记录面板

左栏底部"历史记录"按钮，点击展开列表，显示当前 session 内的历史运行记录，点击可重放查看结果。

---

## 前端项目结构

```
frontend/
├── index.html
├── vite.config.js
├── package.json
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── api/
    │   ├── session.js      # 会话相关 API
    │   ├── parse.js        # 解析相关 API
    │   └── run.js          # 运行相关 API
    ├── components/
    │   ├── FileUploader.jsx
    │   ├── FunctionList.jsx
    │   ├── ParamForm/
    │   │   ├── index.jsx
    │   │   ├── IntegerInput.jsx
    │   │   ├── PointerInput.jsx
    │   │   ├── ArrayInput.jsx
    │   │   ├── StructInput.jsx
    │   │   └── EnumSelect.jsx
    │   ├── ResultPanel/
    │   │   ├── index.jsx
    │   │   ├── LogView.jsx
    │   │   └── ResultSummary.jsx
    │   └── Settings.jsx
    ├── context/
    │   └── AppContext.jsx   # 全局状态（session_id, 解析结果, 运行状态）
    └── hooks/
        └── useWebSocket.js  # WebSocket 封装
```

---

## 后端项目结构

```
backend/
├── main.py               # FastAPI 应用入口
├── routers/
│   ├── session.py        # 会话路由
│   ├── parse.py          # 解析路由
│   └── run.py            # 运行路由（含 WebSocket）
├── services/
│   ├── parser_service.py  # 调用 Phase 1
│   ├── codegen_service.py # 调用 Phase 2
│   └── runner_service.py  # 调用 Phase 3
├── models/
│   └── schemas.py         # Pydantic 数据模型
├── workspace/             # 运行时生成，gitignore
├── requirements.txt
└── README.md
```

---

## 一键启动脚本

提供 `start.sh`（Linux/macOS）：

```bash
#!/bin/bash
# 启动后端
cd backend && pip install -r requirements.txt -q
uvicorn main:app --host 0.0.0.0 --port 8000 --reload &

# 启动前端
cd ../frontend && npm install && npm run dev &

echo "前端: http://localhost:5173"
echo "后端: http://localhost:8000"
echo "API文档: http://localhost:8000/docs"
```

---

## 必须提供的演示素材

代码中需包含一个 `demo/` 目录，用于演示和测试：

```
demo/
├── demo_lib.c          # 演示用 C 源码（含 3-5 个不同参数类型的函数）
├── demo_lib.h          # 对应头文件
├── build_demo.sh       # 编译 demo_lib.so 的脚本
└── README.md           # 说明如何运行演示
```

演示库至少包含：
- `int add(int a, int b)` — 最简整数函数
- `double compute(double x, double y, int mode)` — 混合类型
- `int process_string(const char* input, char* output, int max_len)` — 字符串 + 输出参数
- `int get_status(void)` — 无参函数

---

## 交付物清单

```
gtest-auto-ui/
├── backend/              # FastAPI 后端
├── frontend/             # React 前端
├── demo/                 # 演示动态库
├── header_parser/        # Phase 1（直接复用）
├── codegen/              # Phase 2（直接复用）
├── runner/               # Phase 3（直接复用）
├── start.sh              # 一键启动
└── README.md             # 完整安装使用文档
```

---

## 验收标准

1. 运行 `start.sh` 后，访问 `http://localhost:5173` 能看到完整界面
2. 上传 `demo/demo_lib.so` 和 `demo/demo_lib.h`，能正确显示 4 个函数的接口列表
3. 选择 `add` 函数，填写 a=2、b=3、期望返回 5，点击运行，右栏实时显示日志并最终显示"通过"
4. 选择 `process_string`，填写字符串参数，勾选 `output` 为输出参数，运行后右栏展开显示 output 的打印值
5. 全局设置中修改 cmake 路径，点击"检测"按钮能显示 cmake 版本信息
6. 刷新页面后全局设置保留（来自 localStorage）
7. 历史记录列表显示已完成的运行，点击可查看详细结果
