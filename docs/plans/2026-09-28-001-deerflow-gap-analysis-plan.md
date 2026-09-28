---
artifact_contract: ce-unified-plan/v1
artifact_readiness: requirements-only
product_contract_source: ce-brainstorm
date: 2026-09-28
topic: deerflow-gap-analysis
---

# DeerFlow 集成差距分析 - Plan

## Goal Capsule

**Objective**: 对比 Numina 当前 DeerFlow 集成（pin `6556d09d`, 2026-08-07）与上游 HEAD（`712a11c0`, 2026-09-28）的能力差异，识别值得引入增强的上游新能力。

**Product authority**: 分析型交付 — 不涉及产品行为变更，仅为后续决策提供依据。

**Upstream gap**: 693 commits, ~7 weeks of development (Aug 7 → Sep 28).

---

## 1. 当前 Numina 已使用的 DeerFlow 能力

| 能力 | 上游路径 | Numina 用法 |
|------|----------|-------------|
| DeerFlowClient | `client.py` | 同步 generator stream()，ThreadPoolExecutor 桥接 |
| StreamBridge | `runtime/stream_bridge/` | Redis-only 跨进程事件分发 |
| RunManager | `runtime/runs/manager.py` | Run 生命周期管理 |
| make_lead_agent() | `agents/lead_agent/agent.py` | 构建 LangGraph agent 图 |
| create_chat_model() | `models/factory.py` | 多供应商模型路由 |
| Checkpoint (SQLite) | `runtime/checkpointer/` | Supabase PostgreSQL 持久化 |
| ExtensionsConfig | `config/extensions_config.py` | Skill enable/disable |
| Skill Storage | `skills/storage.py` | LocalSkillStorage scanner |
| MultiServerMCPClient | `mcp/` | MCP server 连接管理 |
| Sandbox | `sandbox/` | write_file / read_file / str_replace |

**Numina 自建层**（不在上游、属于项目独有）：

| 自建模块 | 职责 |
|----------|------|
| FamilyAdapterCache + EffectiveConfigBuilder | 按家庭多租户隔离 |
| PolicyGuard | 角色/能力权限门控 |
| sync_tool_patch.py (5 patches) | ContextVar 传播、MCP 代理、工具过滤 |
| 19 个 Builtin Skills | 领域专属 (asset-report, finance-coach, etc.) |
| 8 个 Dispatch Apps | numina, asset-report, import-parse, finance-coach, etc. |
| 三态熔断器 | FSM + 4 adapters cascade retry |
| SSE Gateway | R1 allowlist + 鉴权 |
| Patched Reasoning | Qwen/Anthropic extended thinking 统一 |
| RunContext | ContextVar facade |

---

## 2. 上游新能力差距分析（按优先级分级）

### Tier 1 — 高价值，建议优先引入

#### 2.1 Subagent 委托系统 ⭐⭐⭐
- **上游**: `subagents/` — 完整 subagent 委托框架
  - Batch runtime (`batch_runtime.py`, `batch_service.py`)
  - Token collector + turn budget 控制
  - Capacity management + acceptance checks
  - Built-in subagents (`builtins/`)
  - Context snapshot preservation
  - Step events + report contract
- **Numina**: `runtime/subagent_registry.py` 存在但功能有限；无 batch/turn budget/capacity
- **引入价值**: 让 finance-coach、deep-research 等复杂 skill 可将子任务委托给专用 subagent，减少 lead agent 上下文膨胀
- **适配工作量**: 中 — 需要通过 adapter 层集成，与多租户隔离对齐

#### 2.2 声明式推理能力契约 (Reasoning Contract) ⭐⭐⭐
- **上游**: `models/` — 模型可声明 `reasoning:` 块
  - `thinking: unsupported|optional|required`
  - `effort: {values, default, aliases, path}`
  - `create_chat_model` 统一强制规范化策略
  - 前端按模型声明生成 effort 菜单
- **Numina**: 自建 `patched_reasoning_chat.py` + `patched_anthropic.py` 做 thinking 补丁，模型 reasoning 能力靠手动配置
- **引入价值**: 取代手写 reasoning 补丁，新模型只需声明契约即可自动适配；GLM/Qwen/Anthropic 统一路径
- **适配工作量**: 中 — 需迁移现有 thinking 配置到契约格式

#### 2.3 Operator Prompt Overlay ⭐⭐⭐
- **上游**: `lead_prompt_overlay.prepend/append` — 无需改源码即可叠加系统提示词
  - Lead agent prompt prepend/append
  - Subagent prompt overlay (`subagents.agents.<name>.prompt_overlay`)
  - DeerMem memory prompt prepend/append
- **Numina**: 系统提示词硬编码在 skill SKILL.md 或 adapter 代码中
- **引入价值**: 运维可热更新提示词（加家族特定指令、合规要求），无需修改 SKILL.md 或重新部署
- **适配工作量**: 低 — 纯配置项，向后兼容

#### 2.4 PII 脱敏中间件 ⭐⭐⭐
- **上游**: `pii_redaction_middleware.py` — 确定性 PII 脱敏
  - 正则检测: email, API keys, credit card (Luhn), phone, ID card (CN/US/BR)
  - 不可逆占位符 `[EMAIL_1]`，编号跨回合稳定
  - 子 agent 自动继承
  - 我们已有自建 `services/pii_redactor.py`
- **Numina**: `services/pii_redactor.py` 是自建版本
- **引入价值**: 上游版本更完整（覆盖更多 PII 类型、跨回合编号稳定、中间件链自动传播），可替换自建版本
- **适配工作量**: 低-中 — 对比两版本，合并或替换

#### 2.5 记忆增强 ⭐⭐⭐
- **上游**: 多项记忆改进
  - **认知风格** (`user.cognitiveStyle`): 沉淀协作偏好（响应结构、详略程度）
  - **相关性排序** (`retrieval_relevance_enabled`): IDF 加权查询覆盖率 + 置信度混合打分，CJK 二元组
  - **容错存储** (`MarkdownMemoryStorage`): 损坏文件不崩溃，尽力恢复
  - **Jev 预筛选**: 记忆更新前的 TypeSafe 信号分类
- **Numina**: 通过 `memory_config_bridge.py` 使用基础 DeerMem，无高级特性
- **引入价值**: 相关性排序直接提升记忆注入质量；认知风格让 AI 回复更贴合用户偏好
- **适配工作量**: 低 — 配置驱动，`retrieval_relevance_enabled: true` 即可

---

### Tier 2 — 中等价值，可按需引入

#### 2.6 插件系统 (Plugin API) ⭐⭐
- **上游**: 全栈插件框架
  - `registry.plugin(PluginContribution(...))` 注册浏览器页面、会话动作、模型工具
  - Manifest + 静态资源目录支持
  - Host model invocation（插件可调用宿主模型）
  - 示例: bookmarks, jev-context, jev-classify, jev-screening
- **Numina**: 无插件系统；扩展通过 adapter 层或 MCP server
- **引入价值**: 如果需要第三方扩展能力（如家庭自定义工具），这是正式路径
- **适配工作量**: 高 — 需完整引入 extensions 框架 + 鉴权对齐
- **建议**: 当前 MCP + skill 系统已满足需求，暂不急

#### 2.7 Guardrails 护栏 ⭐⭐
- **上游**: `guardrails/` — 工具调用风险闸门
  - TypeSafe (Jev) provider: 是非题判断工具调用风险
  - `allowed_tools` 本地硬许可 + 远程风险评估
  - fail_closed 策略
- **Numina**: 工具安全依赖 `allowed-tools` in SKILL.md + PolicyGuard
- **引入价值**: 为高风险操作（金融交易、数据删除）增加一层运行时风险评估
- **适配工作量**: 中 — 需要 TypeSafe/Jev API key

#### 2.8 更多中间件 ⭐⭐
- **上游**: 60+ 中间件，我们只用了少量
- **值得引入的**:
  - `read_before_write_middleware.py` — 写前强制读，防盲目覆盖
  - `tool_receipt_middleware.py` — 工具调用收据/审计
  - `loop_detection_middleware.py` — 循环检测（我们遇到过 agent 循环问题）
  - `tool_output_budget_middleware.py` — 工具输出预算控制
  - `clarification_middleware.py` — 智能澄清（agent 不确定时主动提问）
  - `durable_context_middleware.py` — 持久上下文管理
  - `safety_finish_reason_middleware.py` — 安全终止检测
- **Numina**: 主要依赖 skill 层面的控制，中间件链较薄
- **引入价值**: 增强 agent 运行的健壮性和安全性
- **适配工作量**: 低-中 — 中间件按配置启用

#### 2.9 知识检索增强 (RAGFlow) ⭐⭐
- **上游**:
  - Per-message knowledge scope selection
  - Verifiable source citations（页码、摘录、可追溯）
  - Knowledge scope enforcement at gateway/middleware/subagent
- **Numina**: 无 RAGFlow 集成
- **引入价值**: 如果未来需要家族知识库（财务文档、保险条款等），这是现成路径
- **适配工作量**: 高 — 需部署 RAGFlow + 多租户隔离

#### 2.10 调度器 (Scheduler) ⭐⭐
- **上游**: 定时任务系统
  - 按标题/prompt 搜索
  - Interval task 管理
  - Scheduled task runs 持久化
- **Numina**: `scheduler_worker` 是自建 APScheduler 方案
- **引入价值**: 统一调度入口（AI 定期报告、资产快照等）
- **适配工作量**: 高 — 需与现有 scheduler_worker 合并或替换

#### 2.11 更多 Community Tools / 搜索 Provider ⭐⭐
- **上游新增**:
  - Unbrowse web_fetch (JS 渲染 + Markdown 输出)
  - Firecrawl async 迁移
  - Tavily async 迁移
  - InfoQuest async 迁移
  - Image search: color + license 过滤
  - 总计 20+ community providers (brave, exa, searxng, serper, tavily, jina_ai, ragflow, crawl4ai, etc.)
- **Numina**: 使用 ddg_search + 有限的 web_search_providers 配置
- **引入价值**: 多 provider 降级 + 专业搜索（金融数据、图片搜索）
- **适配工作量**: 低 — 配置驱动

---

### Tier 3 — 长期价值，低优先级

#### 2.12 Blob Storage 契约 ⭐
- **上游**: 内容寻址 blob 存储（sha256, BlobRef, local_fs backend）
- **Numina**: 用 storage package
- **引入价值**: 大文件/图片/附件管理
- **建议**: 当前 storage package 够用

#### 2.13 Checkpoint Retention Service ⭐
- **上游**: checkpoint 修剪服务（叶子节点修剪、恢复头保护）
- **Numina**: 无自动修剪
- **引入价值**: 长期运行的 checkpoint DB 大小控制
- **建议**: 当 DB 增长成问题时再引入

#### 2.14 Managed Models (Settings UI) ⭐
- **上游**: 管理员可从 Settings → Models 管理共享模型
- **Numina**: 模型配置在 config.yaml 或 AI config 页面
- **引入价值**: 更友好的模型管理 UX
- **建议**: 我们已有自建 AI 配置页面

#### 2.15 IM Channels (WeChat, Slack, etc.) ⭐
- **上游**: 微信二维码登录、飞书/Slack/Telegram/Discord/钉钉桥接
- **Numina**: 纯 Web 端
- **引入价值**: 如果需要微信/IM 接入
- **建议**: 产品方向决策，非技术优先级

#### 2.16 Auth 增强 ⭐
- **上游**: Resource-level authorization, skill visibility filtering, plugin action auth
- **Numina**: PolicyGuard 做角色/能力门控
- **引入价值**: 更细粒度的权限控制
- **建议**: 当前 PolicyGuard 满足需求

---

## 3. 上游重要 Fix（值得通过升级获取）

| Fix | 描述 | Numina 是否受影响 |
|-----|------|-------------------|
| `avoid quadratic think-block stripping` | 未关闭标签的二次复杂度修复 | ✅ 我们遇到过 thinking block 泄漏 |
| `preserve response_metadata in dynamic_context` | 动态上下文复制时丢失元数据 | ✅ 可能影响 context 管理 |
| `deep-merge when_thinking_enabled` | 旧路径 extra_body 浅合并导致键丢失 | ✅ GLM/Qwen thinking 配置可能受影响 |
| `close pooled MCP sessions on shutdown` | 关闭时 MCP 连接泄漏 | ✅ 我们修过类似的 |
| `isolate personal connections from deployment` | MCP 个人连接与部署配置隔离 | ✅ 多租户相关 |
| `load skills off event loop` | 技能加载阻塞事件循环 | ✅ 大 skill 树时性能问题 |
| `keep additional_kwargs through upload` | 上传后乐观气泡丢失引用 | 前端相关 |
| `terminalize batches after exhausted leases` | Subagent batch 租约耗尽后终止 | 如果引入 subagent |

---

## 4. 建议引入优先级路线图

### Phase 1 — 低风险高收益（1-2 周）
1. **Operator Prompt Overlay** — 纯配置，热更新提示词
2. **Memory 增强** — `retrieval_relevance_enabled` + `cognitiveStyle`
3. **Community Tools 扩展** — 添加更多 web_search/web_fetch providers
4. **上游 bug fixes** — 通过 submodule 升级自动获取

### Phase 2 — 中等投入（2-4 周）
5. **Reasoning Contract** — 替代手写 thinking 补丁
6. **PII Redaction 中间件** — 替换/合并自建版本
7. **关键中间件引入** — loop_detection, tool_output_budget, safety_finish
8. **HARNESS_VERSION 升级** — 追平到最新稳定版

### Phase 3 — 战略投入（4-8 周）
9. **Subagent 委托系统** — 复杂 skill 拆分
10. **Guardrails** — 高风险工具调用保护
11. **Scheduler 统一** — 合并自建 scheduler_worker

### 暂缓
- Plugin 系统（MCP + skill 已够用）
- RAGFlow 知识检索（需要产品决策）
- IM Channels（需要产品方向）
- Blob Storage（当前方案够用）

---

## 5. 升级风险评估

| 风险 | 级别 | 缓解策略 |
|------|------|----------|
| sync_tool_patch.py 5 个 patch 签名变化 | 中 | 逐一验证上游目标函数 |
| make_lead_agent() 签名变化 | 低 | CHANGELOG 未标记 breaking |
| StreamEvent 类型变化 | 低 | 上游保持向后兼容 |
| Extensions config_version 升级 | 低 | 配置迁移脚本 |
| 新中间件与现有 adapter 冲突 | 中 | 在 staging 充分测试 |
| Subagent 与多租户隔离冲突 | 高 | 需确保 family_id ContextVar 传播 |

---

## Outstanding Questions

1. **Subagent 多租户**: 上游 subagent 是否支持 per-family 隔离？需要验证 ContextVar 传播
2. **Reasoning Contract 迁移**: 现有 patched_reasoning_chat.py 的 GLM/Qwen 特殊处理是否都能映射到契约格式？
3. **PII Redaction 对比**: 自建 pii_redactor.py vs 上游 pii_redaction_middleware.py 功能覆盖差异？
4. ~~**升级节奏**: 是追平到最新 HEAD 还是选择某个稳定 tag？~~ ✅ 已追平到 `712a11c0`

---

## Phase 1 升级完成记录 (2026-09-28)

### 变更摘要

| 文件 | 变更 |
|------|------|
| `HARNESS_VERSION` | `6556d09d` → `712a11c0` (693 commits, v2.1.0) |
| `pyproject.toml` | deerflow-harness rev 更新到 `712a11c0` |
| `base/config.yaml` | 添加 `config_version: 50`；memory 重构为新 schema |
| `memory_config_bridge.py` | 更新 `_MEMORY_CONFIG_IMPORTERS` 列表 + 添加 `judge` 参数 |
| `sync_tool_patch.py` | 删除过时的 `_apply_mcp_cache_threading_lock_patch` (上游已修复) |
| `test_memory_config_bridge.py` | 更新 mock 签名适配上游新参数 |

### 验证结果

- ✅ 629 tests passed, 6 skipped, 0 failed
- ✅ ruff lint 通过
- ✅ `make_lead_agent()` / `DeerFlowClient` / `StreamBridge` / `RunManager` API 兼容

### 自动获得的 upstream 修复 (2.1.0)

- MCP cache 死锁修复 (threading.RLock + threading.Condition)
- 二次复杂度 think-block 剥离修复
- `when_thinking_enabled` 深度合并修复
- MCP 连接关闭时泄漏修复
- MCP 个人连接与部署配置隔离
- Skill 加载移出事件循环 (性能)
- 多个中间件安全性修复

### 下一步 (Phase 2)

1. **Reasoning Contract** — 替代 `patched_reasoning_chat.py`
2. **PII Redaction 中间件** — 评估是否替换自建版本
3. **可选中间件引入** — loop_detection, tool_output_budget, safety_finish
4. **Memory 增强** — `retrieval_relevance_enabled`, `cognitiveStyle`
