# Learning OS 需求文档 — 多角色综合审查报告

> Date: 2026-09-22
> Source: `docs/superpowers/specs/2026-09-22-learning-os-design.md`
> Review method: 7-persona parallel review (ce-doc-review) + codebase verification

---

## 审查覆盖

| 审查角色 | 状态 | 发现数 | 模型 |
|----------|------|--------|------|
| Coherence (一致性) | ✅ | 5 | haiku |
| Feasibility (可行性) | ⚠️ 代码库验证补充 | 2 | sonnet (failed) + verification |
| Product Lens (产品战略) | ✅ | 8 | opus |
| Design Lens (设计完整性) | ✅ | 13 | sonnet |
| Security Lens (安全) | ⚠️ 代码库验证补充 | 1 | opus (failed) + verification |
| Scope Guardian (范围) | ✅ | 6 | sonnet |
| Adversarial (对抗) | ✅ | 12 | opus |

## 需求目标达成评估

核心目标："设计一个基于 os-taxonomy 知识图谱的儿童 AI Learning OS，能够理解孩子能力状态、规划学习路径、生成个性化教学内容、通过游戏化激励成长，并向家长提供成长洞察。"

| 目标 | 达成度 | 说明 |
|------|--------|------|
| 基于 os-taxonomy 知识图谱 | ✅ 已达成 | 数据模型完整映射 topics/dependencies/clusters |
| 理解孩子能力状态 | ⚠️ 部分达成 | 有 mastery_level/score，但缺少纵向能力建模 |
| 规划学习路径 | ⚠️ 部分达成 | prerequisite DAG 可解锁，但自适应推荐推迟到 Phase 2 |
| 生成个性化教学内容 | ⚠️ 部分达成 | AI tutor SKILL.md 有基础设计，但 assessmentPrompt 质量不确定 |
| 游戏化激励成长 | ✅ 已达成 | coins + badges + streak + XP(Phase 2) |
| 向家长提供成长洞察 | ❌ 未达成 | Phase 1 只有审核队列，洞察雷达图/趋势在 Phase 2 |
| 融入父母孩子日常任务 | ❌ 未达成 | 与现有 chore/literacy 系统仅"共享激励"，无日常流程整合 |

---

## 🔴 P0 — 必须在规划阶段前解决 (4 项)

### F-01. 英文知识图谱 vs 中文儿童用户 — MVP 根本性阻断

> **来源：** product-lens, scope-guardian, adversarial (三方交叉验证)

目标用户是 6-12 岁中文儿童，但 os-taxonomy 的 1,590 个 topic 名称、描述、evidence 标准、assessment prompt 全部是英文。文档将此归类为"风险"并推迟到 Phase 2 翻译——这意味着 **Phase 1 MVP 对目标用户完全不可用**。6 岁的孩子无法阅读英文学术内容。

**建议：** 这不是开放问题，而是先决条件。选择以下之一：
- (a) Phase 1 包含翻译管线（LLM 翻译 + 人工审核），至少覆盖 topic name/description/evidence
- (b) 缩小 Phase 1 到 1-2 个学科（如数学 ~200 topics），手动翻译
- (c) 将 Phase 1 重新定位为英语学习场景（英文内容本身就是功能）

### F-02. 产品类别冲突 — 学习系统嵌入家庭资产管理 App

> **来源：** product-lens

Numina 的用户认知是"记账/家务/零花钱 App"。在这个语境下突然加入 1,590 个学术知识节点，改变了产品类别但没有改变入口、引导或价值主张。用户不会因为一个财务 App 有学术辅导功能而使用它。

**建议：** 明确论证为什么 Learning OS 必须在 Numina 内部而非独立工具。如果答案是"共享 gamification 基础设施"，先用现有 LiteracyScenario 系统验证学术场景是否可行——成本仅是当前方案的 5%。

### F-03. "Child Model" 愿景与数据模型不匹配

> **来源：** product-lens, adversarial

核心价值主张是"这个孩子下一步最适合学什么？"——但"readiness"的计算只是知识图谱遍历（hard prerequisites 是否 mastered）。这是图的属性，不是孩子的模型。数据模型只有 mastery_level（7 状态机）和 mastery_score（单个 float），缺少学习速度、能力维度、参与度模式、遗忘曲线。

**建议：** 要么诚实降级为"知识图谱驱动的学习清单 + AI 辅导"，要么在数据模型中补充：(1) 每次评估的历史记录、(2) 间隔重复的时间追踪、(3) 至少一个跨 topic 的能力维度轴。

### F-04. AI 评估可靠性缺乏实证基础

> **来源：** adversarial

系统核心价值依赖 LLM 通过对话准确判断孩子是否掌握了数学/科学概念。但 LLM 已知存在：谄媚倾向、冗长偏差、数学推理不一致。如果 AI 评估系统性出错，错误的掌握度信号会沿 prerequisite 链级联传播。

**建议：** 在 P0 承诺 AI 评估前，建立基准数据集（儿童评估录音 + 专家标注），设定 AI-专家一致率验收标准（如 Cohen's kappa > 0.7），定义低置信度时的降级策略。

---

## 🟡 P1 — 高优先级 (11 项)

### F-05. 知识地图可视化：节点图 vs 列表 vs 网格 — 核心 UX 未决定

> **来源：** design-lens, scope-guardian

线框图画了节点图可视化，风险表承认"MVP 用简化列表/网格视图"。两种完全不同的交互范式。

**建议：** MVP 选定 grid（按 domain 分组，匹配 cluster 表），依赖关系箭头作为 Phase 2 增强。

### F-06. mastery 状态机 "review" 入口路径缺失

> **来源：** coherence, adversarial

状态表列出 "review" 的两个进入条件，但 ASCII 图只画了一条路径。"遗忘触发"需要调度器/后台任务，Phase 1 没有实现。

**建议：** 在状态图中补充 `mastered --[长时间未练习]--> review`，或将 "review" 的遗忘触发路径标记为 Phase 2。

### F-07. Phase 1 表数量错误：声称 5 张实际 6 张

> **来源：** coherence

Section 9 写 "5 张新表"，Section 3 定义了 6 张表。

**建议：** 修改为 "6 张新表"。

### F-08. `learning_assignment.path_id` 引用 Phase 2 表 — FK 悬挂

> **来源：** coherence, scope-guardian

path_id FK → learning_path.id，但 learning_path 在 Phase 2。外键引用不存在的表导致 migration 失败。

**建议：** Phase 1 中 path_id 设为普通 nullable BigInteger（无 FK），Phase 2 再加 FK。

### F-09. `useThreadChat` composable 不存在于 Child App

> **来源：** feasibility (代码库验证)

文档说"复用现有 useThreadChat composable"，但该 composable **仅存在于 `frontend/apps/main/`**。

**建议：** 明确 Phase 1 工作项包括在 child app 创建 useThreadChat 或提取共享包。

### F-10. `stream_run` 新增 app 需要 worker.py 分支 — 文档未提及

> **来源：** feasibility (代码库验证)

新增 `learning-tutor` 需要在 `worker.py` 添加新 runner 分支并注册到 `RESERVED_NAMES`。

**建议：** 补充 worker.py runner 分支和 skill 注册工作项。

### F-11. 6-12 岁视为单一用户群 — 无发展阶段分层

> **来源：** design-lens

6 岁和 12 岁的阅读能力、运动技能、注意力跨度天差地别。数据模型有 age_group 但无对应 UI 适配。

**建议：** 定义 2-3 个 UI 层级。

### F-12. MVP 范围膨胀 — 8/10 项标为 P0 无法裁剪

> **来源：** scope-guardian, product-lens

**建议：** 用"没有这个能否 demo 核心价值？"测试重新分类。

### F-13. AI 会话 → 评估的转换无 UI 设计

> **来源：** design-lens

**建议：** 设计会话流程中的模式切换视觉区分和结果展示。

### F-14. 学习未融入现有日常流程

> **来源：** product-lens

**建议：** 定义整合契约：学习赚币汇率、每日承诺、家长看板合并展示。

### F-15. 家长审核路径的可行性问题

> **来源：** product-lens, adversarial

**建议：** 家长审核需要具体评估机制——实际回答记录、AI 置信度指标、或简化为时间投入判断。

### F-16. 无知识图谱版本/更新机制

> **来源：** adversarial

**建议：** 添加版本字段、upsert 重导入 CLI、冲突解决策略。

---

## 🔵 P2 — 值得关注 (9 项)

| # | 发现 | 来源 |
|---|------|------|
| F-17 | Coin 触发时机矛盾："学习完成" vs "首次掌握" | coherence |
| F-18 | 所有页面缺少空状态/加载/错误状态设计 | design-lens |
| F-19 | 学科 tab 在孩子无 topic 时的行为未定义 | design-lens |
| F-20 | 评估失败的儿童情感/UX 设计缺失 | design-lens |
| F-21 | 徽章系统碎片化：4+ 独立成就体系 | product-lens |
| F-22 | "不是课程平台"定位但未定义孩子实际体验 | product-lens |
| F-23 | 7 状态机对 MVP 过度设计 — 建议简化为 4 状态 | adversarial |
| F-24 | 系统能评估但不能教 — 无结构化教学内容 | adversarial |
| F-25 | 知识图谱质量未验证 — 无教育标准交叉验证 | adversarial |
| F-26 | 并行架构 + Phase 3 整合目标 = 未来返工风险 | adversarial |

---

## 🔒 安全审查补充

### 好消息：现有 MCP 工具体系已有 5 层防御

代码库安全验证发现现有架构的安全机制非常完善：

1. **角色过滤** — `list_tools_for_role()` 按角色暴露工具
2. **Frozen session slots** — MCPSession 在 SSE 握手时冻结 family_id/user_id/role，不可篡改
3. **Family-scoped queries** — 所有数据查询强制 family 范围
4. **Filesystem sandbox** — 文件操作限定在 `{family_id}/threads/{thread_id}/` 内
5. **ContextVar propagation** — 租户身份通过 ContextVar 传播，含完整断言

**新的 learning MCP tools 只需遵循现有模式即可获得同等保护。**

### 但文档应补充

- AI 处理儿童对话数据的隐私合规（数据发送到外部 LLM provider）
- 学习记录的数据保留策略
- os-taxonomy 的许可证/归属要求

### Auth 模式验证

代码库确认：
- `require_adult` 和 `get_current_child_user` 均存在且就绪
- Child 端永远不接受 `child_id` 路径参数（身份来自 auth token）
- Parent 端 `{child_id}` 始终验证 `User.family_id == user.family_id`
- MCP 工具通过 frozen slots 防止跨租户访问

---

## ⚠️ 关键残留风险

> **复合质量风险（adversarial）：** 英文知识图谱 + AI 中文教学 + 不可靠评估 = 每层增加不确定性，早期层的错误在后期中**静默传播**。文档风险表独立处理每个风险，但它们的交互是乘法关系，不是加法。

> **最大设计风险（design-lens）：** 6-12 岁年龄范围如果不分层，产品会疏远 youngest（太文字密集）或 oldest（太幼稚）的用户。这影响文档中的每一个界面。

> **最大产品风险（product-lens）：** 文档可能在解决开发者的兴趣（知识图谱、AI 辅导）而非用户问题。没有证据表明家庭中的孩子表达了现有工具无法满足的学习需求。

---

## 🎯 核心结论

文档**技术架构设计扎实**（数据模型完整、API 分层清晰、与现有系统集成点明确），但在三个维度存在根本性挑战：

1. **可行性断层：** 英文知识图谱 → 中文儿童用户之间的鸿沟是阻断性的
2. **愿景-实现脱节：** "Child Model + 个性化 readiness" 的宏大愿景 vs 简单的 mastery 数据模型
3. **范围过大：** Phase 1 MVP 对独立开发者来说过于庞大

**最关键的下一步决策：**
1. 语言问题必须先解决（F-01）——它决定了 MVP 是否对目标用户有价值
2. 缩小 MVP 到验证核心假设的最小集合（F-12）
3. 决定是诚实降级为"知识图谱驱动学习清单"还是补充 Child Model 数据（F-03）

---

## 代码库集成验证结果

| # | 检查项 | 状态 | 关键说明 |
|---|--------|------|----------|
| 1 | SnowflakeBase 模式 | ✅ 存在 | ORM Base ≠ Pydantic SnowflakeBase，文档需区分 |
| 2 | CoinTransaction 模型 | ✅ 存在 | String(20) type 可扩展，新增 `learning_earn` 无需 migration |
| 3 | stream_run 接口 | ✅ 存在 | 需新增 worker.py runner 分支 + RESERVED_NAMES 注册 |
| 4 | LiteracyBadge 模式 | ✅ 存在 | 两模型模式 (Definition + earned Badge)，source 字段自由格式 |
| 5 | Auth guards | ✅ 均存在 | require_adult + get_current_child_user 就绪 |
| 6 | useThreadChat | ❌ Child App 无 | 仅存在于 main app，需新建或提取共享包 |
| 7 | Router 命名 | ✅ snake_case | 文件名用下划线，URL 路径可用连字符 |
