---
date: 2026-05-19
topic: async-agent-task-result-persistence-v2
status: Draft
scope: Standard
supersedes: docs/brainstorms/2026-05-17-async-agent-task-result-persistence-requirements.md
---

# 异步 Agent 任务结果落地（二次优化）

**Origin:** 一次优化（2026-05-17）的成果未在生产环境解决问题。本次为二次迭代，目标是让 alerts/disposal/spending_leak/allocation 四个 capability 真正能在 UI 上看到刷新结果，而不只是"提交后立刻显示成功"。

## Problem Frame

### 用户视角

用户在 Dashboard 进入 AI 老化预警 / 闲置清仓 / 消费漏洞 / 配置漂移 任意一个页面，点击「重新扫描」按钮：

1. 控制台展示 thinking + answering 流式文本（看起来正常）
2. 流结束 → console 折叠 → toast 提示"扫描完成"
3. **页面上的卡片列表仍然为空**（或保留上一次的旧数据）

UI 层把"提交成功 / 流式结束"误当成了"分析结果落库"，但实际数据库中并没有写入新的结构化记录。

### 一次优化为何没解决

一次优化（2026-05-17）已经做完：

- ✅ `server/apps/backend/app/services/ai_result_parser.py` — 正则提取 `<!-- STRUCTURED_DATA ... -->` 块
- ✅ `server/apps/backend/app/services/ai_result_writer.py` — 六个 capability 的写入器
- ✅ `server/apps/backend/app/routers/_ai_events_helper.py` — 流结束后调用 parser + writer
- ✅ `server/apps/agent/skills/custom/{alerts,disposal,spending_leak,allocation,report,liability}/SKILL.md` — 提示词已包含 STRUCTURED_DATA 输出指令

但生产环境表现仍然是"流结束后页面空白"。基于代码静态分析，二次失效点定位为：

1. **`_llm_fallback_extract` 是 stub** —— `ai_result_parser.py:194-232` 写着 `# TODO: Call LLM with extraction prompt`，目前 regex 失败时直接返回 `None`
2. **静默降级 + 零可观测性** —— `parse_capability_result` 返回 `None` 时，仅 `logger.warning` 一行，前端、用户、运维都看不到失败信号
3. **LLM 不可靠地输出 HTML 注释格式** —— 一些模型（尤其是低温度但未启用结构化输出模式的）会丢失 `<!--`、把 JSON 包成 ```json ``` 围栏、或者在注释外侧多加 markdown 标题；当前 regex `<!-- STRUCTURED_DATA\s*\n?(.*?)\n?\s*-->` 对这些变体一律不匹配
4. **任务被标记为"completed"早于结构化结果可用性** —— `_ai_events_helper.py:103` 先 `complete_task`、再调用 parser/writer，且写入失败不会回滚 task 状态。前端的 `onComplete` 看到 task=completed 就立刻 `loadAlerts()`，结果 GET 一个空表
5. **per-family 自定义 prompt 覆盖会清空 SKILL.md 内容** —— `skill_loader.py:127` 的 `effective_prompt = entry.prompt if entry.prompt else base.prompt`，但 `base.prompt = ""`（注释说"prompts live in skills/custom/*/SKILL.md, loaded by DeerFlow harness"）。如果某家庭曾在后台配置过自定义 prompt 并清空过，可能落到一个完全没有 STRUCTURED_DATA 指令的 prompt 上

第 (4) 个失效点是核心：把"agent 流结束"误等同于"结构化结果可用"——这就是用户描述的"混淆了提交成功和真实完成的状态"。

## Assumptions（请校正）

ASSUMPTIONS I'M MAKING:
1. 用户希望保留现有的"流式 console + 后处理写库"架构，不是要重做一套同步等待的请求-响应流。
2. report、liability、AI 问答、time_machine 不在本次范围内（per 用户回答）。
3. 当前 LLM 对 `<!-- STRUCTURED_DATA -->` 格式的遵循率，不是单靠 prompt 工程就能拉高到生产可接受水平 —— 必须有 LLM fallback 作为兜底，或者切到更结构化的输出协议。
4. 「直接返回成功」描述的是"task 显示 completed → 卡片仍空"，不是"agent 根本没被调用"。如果是后者（agent 端 0 token 输出），方案需要不同。

→ 校正以上，否则按此推进。

## Approaches（先看候选，再选推荐）

### A. 强化现有协议（保留 HTML 注释 + 后处理）

**做法：**
- 实现 `_llm_fallback_extract` 真正的 LLM 提取调用
- 把 `complete_task` 推迟到 parser+writer 都完成之后；任一失败则 `fail_task` 并通过 `capability.error` 事件告知前端
- 增加 `extraction_method` 审计字段（regex / llm_fallback / failed）
- regex 容错升级：兼容 ```json ``` 围栏、纯 HTML 注释、bare JSON 三种变体
- 前端在 `capability.error` 时显示具体提示而不是泛化"扫描完成"

**优点：**
- 改动局部，不动 stream 协议
- 复用已写好的 parser / writer / 表结构
- LLM fallback 作为兜底显著提升结构化成功率

**缺点：**
- `_llm_fallback_extract` 增加一次额外 LLM 调用（成本、延迟 +1-3s）
- 仍然依赖 LLM 在两次调用中的协作
- HTML 注释这种载体本身就不是为机器解析设计的

### B. 切换到原生结构化输出（Tool calling / JSON mode）

**做法：**
- DeerFlow harness / agent 调用 LLM 时启用 OpenAI tool_calling 或 JSON mode（取决于 provider 支持度）
- Skill prompt 不再要求 LLM "在文末输出注释块"，而是声明一个 tool schema，由 LLM 通过 tool_call 返回结构化数据
- Backend 直接接收 NDJSON 中的 `tool.call` 事件作为结构化结果，不再做正则提取
- 自然语言摘要走 `token.stream`，结构化结果走 `tool.call`，两条通道清晰分离

**优点：**
- 协议层根除"LLM 是否守格式"问题（tool schema 由 SDK 强制）
- 前端可以更早渲染（流到一半就能拿到部分 tool_call）
- 把"提交成功 vs 真正完成"语义彻底拆开：`tool.call` 才是完成证据

**缺点：**
- 改动跨 agent / DeerFlow / backend / 前端 NDJSON 解析多个层
- 不是所有 provider 都支持（DeepSeek/Qwen 等本地路径需要单独验证）
- 与一次优化已落地的 SKILL.md / parser / writer 大量重叠 → 等于推翻一次优化的协议层

### C. 在 agent 内部做最终成果整合（替换答案文本）

**做法：**
- agent orchestrator 在 stream 末尾，完成自然语言生成之后，做一次内部 LLM 调用：「把上面这段分析压成 JSON schema」
- agent 端把 JSON 直接持久化到 backend（绕过 NDJSON proxy），通过新的内部端点 `/internal/ai-results/{capability}` 写入
- 前端 NDJSON 流仍然只显示自然语言；写库不再依赖前端流的结束

**优点：**
- 拆开"对话流"和"结果落库"两条独立通道，最贴近用户的诉求模型
- agent 自己负责"我做完了"语义；backend 不必猜测
- 与现有 NDJSON 协议解耦

**缺点：**
- 新增 agent → backend 的内部回调端点（多一条网络路径要加固）
- 仍然要做一次结构化 LLM 调用（成本同 A）
- 任务状态语义需要重新定义（流结束 ≠ task 完成；要等回调）

### 推荐：A + 小部分 C 的混合

**理由：** Approach B 的诱惑很大但代价过重——本次优化是"二次"，意味着用户已经投入过一次工程成本看不到结果，再推翻协议会进一步消耗信任。Approach A 的关键缺口（LLM fallback 是 stub、task 完成时机不对、零可观测性）每一个都有具体可控的修复路径，且 LLM fallback 一旦真的实现，结构化成功率从"靠模型自觉"升级到"两次都失败才彻底失败"，这才是治本。

从 C 借一个关键想法：**`task.status = "completed"` 应当严格表示"结构化结果已落库"，"agent 流结束"是另一个状态（如 `streaming_done` / `post_processing`）**。前端按 `completed` 才触发 `loadAlerts()`，避免空表。

## Requirements

### R1. Task 状态语义重定义

- R1.1 在 `AITask.status` 增加中间态 `post_processing`（或复用 `running` 直到落库完成都不切到 `completed`）。`completed` 严格表示"结构化结果已写入对应 DB 表 OR 经过 LLM fallback 后确认无可写数据（空数组/空对象，且 narrative 字段已落 session_journal）"。
- R1.2 `_ai_events_helper.py` 的 `proxy_capability_events`：流结束后先尝试 parse + write，全部成功才 `complete_task`；任一异常或 parse 返回 None 且 LLM fallback 也失败 → `fail_task(task_id, "structured_extraction_failed", ...)` 并向 NDJSON 发送 `capability.error` 事件
- R1.3 前端 `useAITask` 在收到 `capability.error` 时不调用 `onComplete`，改为显示"分析完成但结构化失败"提示（仍然保留对话 console 中的自然语言文本，用户可读）

### R2. LLM Fallback 真正实现 + 三段式成本控制

- R2.1 实现 `ai_result_parser._llm_fallback_extract`：当 regex 提取失败时，用家庭最便宜的 provider（按 `display_order` 升序第一个）调用一次 LLM，prompt 形如"把以下分析文本里的资产/漏洞/偏离信息抽成 JSON，schema 为 {…}"，返回纯 JSON 字符串
- R2.2 LLM fallback 调用使用 max_tokens=800、temperature=0.1、5 秒超时，避免长时间阻塞
- R2.3 fallback 输出经过相同的 `_validate_json` 校验；通过则写库，未通过则仍然返回 None 并让 R1.2 走 `fail_task` 路径
- R2.4 fallback 调用结果写入新增 `ai_extraction_audit` 表（family_id, capability, task_id, method=regex|llm_fallback|failed, extracted_at, error_msg），用于事后排查模型遵循率
- R2.5 **三段式成本控制（per D7）**：
  - 阶段 1（默认）：regex 失败 → 立即触发 LLM fallback
  - 阶段 2（限流）：(family_id, capability) 在过去 1 小时内 fallback 触发 ≥ 5 次 → 进入 `rate_limited` 状态 30 分钟，期间 regex 失败直接走 `fail_task`，NDJSON `capability.error` 的 message 字段为「AI 输出格式异常，已暂停自动修复」
  - 阶段 3（熔断）：(family_id, capability) 在过去 24 小时内 fallback 触发 ≥ 20 次 → 进入 `circuit_open` 状态，**扫描请求在路由层就返回 NDJSON `capability.error`，不调用 agent**；状态由管理员在「模型管理」页面手动重置才能恢复
  - 计数器实现：基于 `ai_extraction_audit` 表的时间窗口 SQL 查询（不引入 Redis 新依赖），查询命中索引 `(family_id, capability, extracted_at)`
- R2.6 新增 `ai_extraction_circuit` 表（family_id, capability, state=ok|rate_limited|circuit_open, opened_at, opened_until, manually_reset_at, reset_by_user_id），unique 约束 `(family_id, capability)`

### R5. 可观测性 + 管理端干预

- R5.1 R2.4 的 `ai_extraction_audit` 表写入每次提取尝试
- R5.2 增加管理端 `GET /admin/ai-extraction-audit?capability=alerts&days=7`，返回成功率、各 method 占比，便于评估二次优化效果
- R5.3 `_ai_events_helper.py` 的 logger 改为 `logger.error`（不再是 warning），并附带 task_id / family_id / answer 文本前 500 字（脱敏后）方便回溯
- R5.4 **「模型管理」页面新增「提取熔断」区块（per D7）**：
  - 列表显示当前 `state != ok` 的所有 (family_id, capability) 对
  - 每行显示：capability 名称、当前状态（限流中 / 熔断中）、进入状态时间、24h 触发次数、操作按钮
  - 「重置」按钮：调用 `POST /admin/ai-extraction-circuit/reset`，body `{family_id, capability}`，清空计数 + 状态置回 `ok`
  - 「查看审计日志」链接：跳转到 R5.2 的审计页面，预置 family_id + capability 过滤
- R5.5 `useAITask` 在收到 NDJSON `capability.error` 且 message 包含 `"已暂停自动修复"` 时，toast 提示用户「AI 输出格式异常，请稍后重试，或联系管理员」

### R6. 前端最小调整 + 失败时保留自然语言文本

- R6.1 `useAITask` 在 `capability.error` 时设置 `status='failed'`，**不清空 thinkContent / answerContent**（per D6），不再调 `onComplete`
- R6.2 `aiTask.scanComplete` toast 改为只在 task 真正 completed（通过 R1.2 后）时显示
- R6.3 现有页面的"重新扫描"按钮在 `failed` 状态显示重试
- R6.4 **失败时 TaskConsole 不折叠（per D6）**：保留显示已累积的自然语言文本，并在 console 顶部追加红色警告条「⚠️ 分析已完成，但结构化结果落库失败，可参考上方文本」+ 内嵌「重试」按钮
- R6.5 console 的「重试」按钮调用 `startStream()` 重新发起请求；如果当前已 `circuit_open`，请求会立即得到 `capability.error` 并显示对应提示

### R3. Regex 容错升级

- R3.1 `STRUCTURED_DATA_PATTERN` 兼容三种载体（按优先级依次尝试匹配，第一命中即用）：
  - `<!-- STRUCTURED_DATA\n…\n-->`（当前协议）
  - ` ```json\n…\n``` `（markdown 围栏，LLM 常见漂移）
  - 末尾的纯 JSON（从最后一个 `[` 或 `{` 开始到字符串结尾，两端 balanced 括号校验）
- R3.2 三种载体的命中分布写入 R2.4 的审计表，便于观察哪种格式最稳

### R4. 协议层补丁（兼容 per-family override）

- R4.1 修复 `skill_loader.py:127`：当 `entry.prompt` 为空且 `base.prompt` 也为空时（即所有 capability 当前的状态），不要把空字符串作为 effective_prompt 传给 DeerFlow，而是从 `skills/custom/{capability}/SKILL.md` 读取 prompt 内容（DeerFlow harness 已支持但未在 SkillConfig 暴露）
- R4.2 在 SkillConfig 上新增 `effective_prompt` 字段，由 SkillLoader 在加载时填充（base path: `skills/custom/{capability}/SKILL.md` 的 description 之后的 markdown body），并暴露给 orchestrator 用于审计

> **注：** 当且仅当 R4 的诊断确认 SKILL.md 没有真正进入 LLM prompt 时才需要做。先通过 audit 日志在生产抓一次 raw answer 文本验证，如果文本里能看到 STRUCTURED_DATA 块，说明 prompt 是生效的，R4 退化为可选；如果完全看不到，R4 就是必做。

### R5. 可观测性 + 管理端干预（已纳入 R2/R5/R6 上方扩展，本节作为索引）

> R5 的内容已合入 R2.5/R2.6 + R5.1–R5.5；不重复列出。

## Success Criteria

1. **生产环境实测**：依次触发 alerts / disposal / spending_leak / allocation 四个刷新按钮，至少 3/4 在 90 秒内 UI 上看到非空卡片列表
2. **可观测性**：`ai_extraction_audit` 表至少能区分 regex_hit / llm_fallback_hit / both_failed 三类
3. **task 状态语义**：在 `completed` 状态下 100% 能 GET 到结构化数据；如果 GET 不到，说明 task 实际是 `failed` 而不是 `completed`
4. **不破坏现有流式 UX**：TaskConsole 的实时文本展示无变化，user-facing 体验在最差情况下也比现状好（看到错误提示而不是空表 + 假成功 toast）

## Scope Boundaries

### In scope
- 四个 capability：alerts / disposal / spending_leak / allocation
- Backend：`ai_result_parser.py`（R2/R3）、`_ai_events_helper.py`（R1.2/R5.3）、新表 `ai_extraction_audit`（R2.4/R5.2）
- Agent：`skill_loader.py`（仅当 R4 诊断必需时）
- Frontend：`useAITask.ts`、相关页面 toast/error 提示文案

### Outside scope（明确不做）
- AI 问答 chat、time_machine（按用户指示）
- report、liability（用户未列入二次优化范围；如有问题二次优化稳定后再独立处理）
- 切换到 tool_calling / JSON mode（Approach B）—— 留给三次优化（如本次仍未解决）
- 重新设计 task queue / promote 机制
- 重新设计 NDJSON 协议格式
- 前端 UI 重做

### Deferred to follow-up
- 用 tool_calling 替换 STRUCTURED_DATA 协议（Approach B），仅在二次仍达不到 R6 的成功率时启动
- 给 LLM fallback 加上模型/时延/费用的 metrics dashboard
- 对 report、liability 做同样的二次优化（如果它们也表现出"完成但空表"问题）

## Key Decisions

- **D1：保留 STRUCTURED_DATA 协议** —— 一次优化已经在 6 个 SKILL.md / parser / writer 里固化了这个协议，重做协议会浪费上一轮成本且破坏稳定运行的 chat / time_machine。优先把缝堵上。
- **D2：task.status 语义口径切换** —— 这是用户原话"混淆了提交成功和真实完成的状态"的最直接对应；语义口径不修，前端永远是先得到 completed 再 GET 空表。
- **D3：LLM fallback 而不是更强的 prompt** —— 单纯加强提示词无法保证生产环境的鲁棒性；fallback 是"两次独立尝试"，数学上比一次尝试可靠得多。
- **D4：写一张审计表而不是接 monitoring SaaS** —— 自托管原则；表结构简单，事后查询足够，不增加外部依赖。
- **D5：R4（skill_loader 修复）有条件触发** —— 如果生产 raw answer 里能看到 STRUCTURED_DATA 块，说明 prompt 已生效，R4 不必做；先通过日志验证。

## Dependencies / Assumptions

- 依赖一次优化（2026-05-17）的所有产出仍然在 main 上：parser、writer、`_ai_events_helper.py`、六个 SKILL.md
- 假设至少有一个家庭已经配置了可用 provider（否则 LLM fallback 无法启动；这种家庭的失败仍然需要走 fail_task 路径，不能崩）
- 假设 `AITask.status` 字段是字符串而非 enum，可以平滑加 `post_processing`（如果是 PG enum，需要 alembic migration）
- 假设 `ai_extraction_audit` 表写入失败不应该影响主流程 —— fire-and-forget 即可

## User-Confirmed Decisions（2026-05-19 二次答疑）

- **D6（失败时 console 处理）：保留自然语言文本** —— 在 `capability.error` 后，console 不清空，继续显示 thinking + answering 累积下来的纯文本，并在顶部追加一条红色警告条「分析已完成，但结构化结果落库失败」+「重试」按钮。用户至少能读懂分析结论。
- **D7（LLM fallback 成本控制）：限流→熔断→人工介入** 三段式：
  - 阶段 1（默认每次都尝试）：regex 失败 → 立即触发 LLM fallback；正常路径
  - 阶段 2（限流）：同 family 同 capability 在 1 小时滚动窗口内 fallback 触发 ≥ 5 次，进入"限流"状态：30 分钟内不再触发 fallback，regex 失败直接走 `fail_task`，前端 toast 提示「AI 输出格式异常，已暂停自动修复」
  - 阶段 3（熔断）：同 family 同 capability 24 小时内 fallback 累计触发 ≥ 20 次 → 该 family 的该 capability 进入 `extraction_circuit_open` 状态，扫描请求直接返回 NDJSON `capability.error` 不再调 agent；状态写在 `ai_extraction_audit` 关联的 family-level 表
  - 人工介入：管理端「模型管理」页面新增"提取熔断"区块，列出当前熔断中的 (family, capability) 对，提供「重置」按钮（清空计数 + 关闭熔断），用户可手工恢复

## Outstanding Questions

### Deferred to Planning

- **[影响 R1.1][技术]** `post_processing` 是新枚举值还是复用 `running`？前者更明确但要 migration；后者改最少但前端需要靠新事件而不是 status 区分。
- **[影响 R2.4][技术]** `ai_extraction_audit` 表是按家庭隔离查询还是全局表？多家庭部署时是否需要分区？
- **[影响 D7][技术]** 限流/熔断的计数器存哪里：(a) Redis 滚动窗口（精确但增加依赖），(b) 直接查 `ai_extraction_audit` 表 + 时间窗口 SQL（无新依赖但每次扫描多一次查询）—— 规划时决定。
- **[影响 D7][产品]** 熔断重置按钮是 admin-only 还是普通 family 用户也能点？「模型管理」页当前的权限模型是怎样的，需在规划时确认。

## Next Steps

→ 用户校正 Assumptions / Outstanding Questions  
→ `/ce:plan` 拆解 R1–R6 为可验证 task（preferring R1 + R2 在同一个 PR，R3/R5 独立小 PR，R4/R6 在最后）  
→ R6 上线后做一次 `/qa` 跑端到端，验证四个 capability 各自的"流结束 → completed → 卡片有数据"链路
