# CodeGraph 结构化代码检索

## 问题背景

传统代码检索依赖 `grep` + `read` 循环：
- 多次文件读取消耗上下文
- 无法追踪动态跳转（回调、React 渲染、JSX children）
- 需要人工拼接调用链

CodeGraph 基于 tree-sitter AST 解析，将代码转为可查询的知识图谱。实测收益：
- **35% 成本降低**
- **57% token 减少**
- **46% 更快响应**
- **71% 更少工具调用**

## 安装与初始化

### 安装 CLI

```bash
npx @colbymchenry/codegraph
# 或 curl -fsSL https://colbymchenry.github.io/codegraph/install.sh | sh
```

支持 Windows/macOS/Linux (x64/arm64)。安装后自动配置 agent 权限。

### MCP 配置

手动配置需添加到 `~/.claude.json`：

```json
{
  "mcpServers": {
    "codegraph": {
      "command": "codegraph",
      "args": ["serve", "--mcp"]
    }
  }
}
```

支持的 Agent：Claude Code、Cursor、Kiro。

### 初始化项目索引

```bash
# 项目根目录运行
codegraph init -i

# 生成 .codegraph/codegraph.db（SQLite 知识图谱）
```

### 验证

```bash
codegraph status
# MCP tool: codegraph_status
```

## MCP 工具（共 10 个）

| 工具 | 意图 | 说明 |
|------|------|------|
| `codegraph_search` | 查符号定义 | 按名称搜索，返回位置+签名 |
| `codegraph_callers` | 谁调用了这个 | 上游依赖，所有调用位置 |
| `codegraph_callees` | 这个调用了什么 | 下游依赖，所有被调用符号 |
| `codegraph_impact` | 改这个会破坏什么 | 变更影响分析 |
| `codegraph_node` | 看符号源码/签名 | 单个符号详情 |
| `codegraph_explore` | 看多个相关符号源码 | 批量获取，一次 capped call |
| `codegraph_files` | 目录下有什么文件 | 目录内容列表 |
| `codegraph_status` | 索引状态/大小 | 健康检查 |
| `codegraph_context` | 任务上下文 | **PRIMARY** — 组合搜索+调用者+被调用者 |
| `codegraph_trace` | X 如何到达 Y | 完整调用路径（含动态跳转） |

> ℹ️ 说明：`codegraph_context` 同时是 CLI 命令和 MCP 工具；`codegraph_trace` 仅作为 MCP 工具提供。

## CLI 命令

```bash
# 初始化
codegraph init -i           # 建立索引 (-v: 详细输出)
codegraph uninit            # 移除索引

# 维护
codegraph sync              # 增量同步（文件变化后）
codegraph index --force     # 强制完整重建
codegraph status            # 状态检查
codegraph unlock            # 移除阻塞索引的锁文件

# 安装/卸载 MCP
codegraph install           # 安装 MCP 到 agents (Claude Code/Cursor/Codex/opencode/Hermes)
codegraph uninstall         # 从 agents 移除 codegraph

# 查询
codegraph query <name>      # 搜索符号 (-k: 按类型过滤, -l: 结果数限制, 默认10)
codegraph callers <symbol>  # 调用者 (-l: 结果数限制, 默认20)
codegraph callees <symbol>  # 被调用者
codegraph impact <symbol>   # 影响分析 (-d: 深度, 默认2)
codegraph files [path]      # 文件列表
codegraph context <task>    # 任务上下文 (-n: 最大节点数, -c: 最大代码块, --no-code)

# CI 集成
codegraph affected --stdin  # 从 git diff 读取 (-d: 深度, -f: 过滤, -j: JSON输出)
```

### CLI 选项详解

| 命令 | 选项 | 说明 |
|------|------|------|
| `init` | `-v, --verbose` | 详细输出（worker 生命周期、内存信息） |
| `query` | `-k, --kind <kind>` | 按节点类型过滤（function/class 等） |
| `query` | `-l, --limit <n>` | 最大结果数（默认 10） |
| `callers` | `-l, --limit <n>` | 最大结果数（默认 20） |
| `impact` | `-d, --depth <n>` | 遍历深度（默认 2） |
| `affected` | `-d, --depth <n>` | 遍历深度（默认 5） |
| `affected` | `-f, --filter <glob>` | 自定义测试文件过滤（如 `e2e/*.spec.ts`） |
| `affected` | `-j, --json` | JSON 输出 |
| `context` | `-n, --max-nodes <n>` | 最大节点数（默认 50） |
| `context` | `-c, --max-code <n>` | 最大代码块数（默认 10） |
| `context` | `--no-code` | 不包含代码块 |
| `context` | `-f, --format <fmt>` | 输出格式（markdown/json） |

## 使用原则

1. **直接回答** — 2-3 个 MCP 调用回答结构问题，不派发文件读取子任务
2. **信任结果** — AST 解析，无需 grep 再验证
3. **批量获取** — 多符号源码用 `codegraph_explore`，不循环 `codegraph_node`
4. **增量同步** — 文件变化后 `codegraph sync`，或等待 OS 文件事件自动触发

## 知识图谱结构

### 节点类型

file, module, class, struct, interface, trait, protocol, function, method, property, field, variable, constant, enum, enum_member, type_alias, namespace, parameter, import, export, **route**, component

### 边类型

contains, calls, imports, exports, extends, implements, references, type_of, returns, instantiates, overrides, decorates

### 动态边界

callback、React re-render、JSX child 等动态跳转通过 **启发式边** 桥接，标记 `provenance: 'heuristic'`。

## 支持的语言

26 种语言全支持，自动检测（无需配置）：

TypeScript, JavaScript, Python, Go, Rust, Java, C#, PHP, Ruby, C, C++, Swift, Kotlin, Scala, Dart, Svelte, Vue, Liquid, Pascal/Delphi, Lua, Luau

**特色支持：**
- Scala: classes, traits, methods, type aliases, Scala 3 enums
- Svelte: script extraction, Svelte 5 runes, SvelteKit routes
- Vue: script + script-setup, Nuxt page/API/middleware routes
- Lua/Luau: typed signatures, type aliases, Roblox require

## Framework Routes

自动检测路由文件，链接 route 节点到 handler：

- Django, Flask, **FastAPI**
- Express, NestJS
- Laravel, Rails

无需配置，从文件扩展名自动识别。

## CI 集成

在 CI 中只运行受影响的测试：

```bash
git diff --name-only HEAD~1 | codegraph affected --stdin
# 返回需要运行的测试文件列表
```

## 配置

**零配置** — 无配置文件，行为如下：

- 自动跳过: deps 目录、build 目录、>1MB 文件、.gitignore 条目
- 通过 `.gitignore` 否定模式控制包含：`!vendor/`
- 数据本地存储：`.codegraph/codegraph.db`

## 常见问题

### "CodeGraph not initialized"

项目未初始化：
```bash
codegraph init -i
```

### 找不到新符号

等待 OS 文件事件自动同步，或：
```bash
codegraph sync
```

### 索引缓慢 / database locked

SQLite 锁冲突，通常并发写入导致。等待或：
```bash
codegraph index --force
```

### 缺失符号

检查 .gitignore 是否意外排除，用否定模式包含：
```gitignore
!important_file.ts
```

## 设计理念

- **本地优先** — 数据不出本机，SQLite 存储
- **确定性索引** — 同一代码产生同一图谱
- **启发式桥接** — 动态跳转通过 heuristic edges 连接
- **框架感知** — 自动检测路由，链接到 handler