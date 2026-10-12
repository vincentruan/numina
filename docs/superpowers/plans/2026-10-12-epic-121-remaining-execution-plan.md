# Epic #121 剩余任务执行计划

> **日期**: 2026-10-12
> **分支**: `vincentruan/epic-os-taxonomy-beijing`
> **Epic**: #121 — 基于 os-taxonomy-beijing 建设标准化题库与儿童自适应智能练习系统
> **设计 Spec**: [2026-10-10-question-bank-adaptive-practice-design.md](../specs/2026-10-10-question-bank-adaptive-practice-design.md)
> **前序计划**: [2026-10-10-question-bank-practice.md](./2026-10-10-question-bank-practice.md) (Phase 1-5 已完成)

## 状态

| Phase | Issue | 优先级 | 状态 |
|-------|-------|--------|------|
| Phase 0 数据质量 | #122 | P0 | 🟡 待收尾 |
| Phase 3 题目 Pipeline | #125 | **P1** | ⬜ 待实施 |
| Phase 6 自适应练习 | #128 | P2 | ⬜ 待实施 |
| Phase 7 全学科扩展 | #129 | P3 | ⏸️ 暂缓 |

## 已完成（本次 Epic 前期）

| Phase | Issue | 交付物 |
|-------|-------|--------|
| Phase 1 设计 | #123 ✅ | 设计 Spec + 16-task 实施计划 |
| Phase 2 题库基础 | #124 ✅ | 4 表 (questions, question_knowledge_points, practice_sessions, practice_attempts) + CRUD + quality gate |
| Phase 4 自动出题 | #126 ✅ | 4 arithmetic 模板 (加减乘除) + registry 机制 |
| Phase 5 练习诊断 | #127 ✅ | 9 API 端点 + 55 tests + weak points + prereq practice + 前端练习页 |

## 当前系统状态（代码审计）

| 组件 | 状态 | 关键发现 |
|------|------|---------|
| 模板引擎 | ✅ 可用 | 4 个算术模板，registry 机制完整 |
| 题目 CRUD | ✅ 可用 | question_service + quality gate |
| 练习 API | ✅ 9 端点 | sessions/answer/finish/weak-topics/recommend 等 |
| 状态机 | ✅ 完整 | 7 状态 + CAS + XP/星星币 + 通知 |
| SM-2 间隔复习 | 🟡 简化版 | 单 stability 浮点，`interval = 3 * stability` |
| 选题引擎 | 🟡 朴素 | difficulty bucket + random shuffle，**无 BKT** |
| MasteryEstimator | 🟡 未接线 | protocol + rule-based 实现存在，但 **select_questions 不调用它** |
| 题目生成 pipeline | ❌ 缺失 | **无批量生成脚本**，模板→DB 的桥不存在 |
| topic_key→topic_id 映射 | ❌ 缺失 | GeneratedQuestion.topic_key 无法关联到 LearningTopic.id |
| 多学科学科模板 | ❌ 缺失 | 仅 math_arithmetic |

---

## 执行计划

### Step 1: 更新已完成 Issues

评论完成摘要并关闭：
- #123 Phase 1 — 设计文档 + 16-task plan
- #124 Phase 2 — 4 表 + CRUD + quality gate + 51 tests
- #126 Phase 4 — 4 arithmetic 模板 + registry
- #127 Phase 5 — 9 API + 55 tests + weak points + prereq practice

### Step 2: Phase 0 收尾 (#122) — 知识图谱数据质量审计

**目标**: 产出数据质量统计报告，记录已知问题，关闭 #122。

#### Sub-issue 122a: 知识点统计报告

- 分析 1,590 topics / 3,221 dependencies / 183 clusters 覆盖度
- 统计各学科知识点数量分布
- 先修关系完整性检查（孤立节点、循环依赖）
- 课程标准映射覆盖率
- 输出: `docs/superpowers/reports/phase0-data-quality-report.md`

#### Sub-issue 122b: 数据质量问题记录 + Makefile 提交

- 提交已有 Makefile 变更（setup-beijing-data targets）
- 记录已知数据质量问题 + 处理方案（修复/标记/忽略）
- 关闭 #122

**执行方式**: 主线程直接操作（轻量统计 + 文档）
**预估**: 1 个 subagent（统计脚本 + 报告撰写）

---

### Step 3: Phase 3 (#125) — 题目生成 Pipeline + 知识点映射 ⭐ P1

**目标**: 建立真实题目的合法生成/导入流程，实现题目到 taxonomy 微知识点的可靠映射。
**设计约束**: Spec §1.4（版权安全、质量优先）、§3.1-3.4（三层生成策略）、§8（开源数据源结论）

#### Sub-issue 125a: 模板→DB 批量生成 Pipeline

**缺失**: 模板引擎能生成 GeneratedQuestion，但无代码将其持久化到 Question 表。

**实现**:
- `seed_questions_from_templates()` 服务函数
  - 遍历 `TEMPLATE_REGISTRY` 所有模板
  - 每个模板生成 N 个变体（参数化随机）
  - topic_key → topic_id 映射桥（通过 `topic_key` 查询 `LearningTopic`）
  - 调用 `question_service.create_question()` 持久化（复用 quality gate）
  - 去重检测：相同 stem + answer 跳过
- CLI 入口: `make seed-questions` 或 management command
- 幂等性：重复运行不产生重复题目
- 日志：生成/跳过/失败统计

**关键文件**:
- 新增: `server/apps/backend/app/services/learning/question_seeder.py`
- 修改: `server/apps/backend/app/services/learning/question_service.py` (可能需批量接口)
- 新增: topic_key → topic_id 映射逻辑（在 seeder 中或 question_service 中）

**测试**: 5+ tests（幂等性、去重、topic_key 映射、quality gate 拦截）

#### Sub-issue 125b: 扩展模板覆盖

**设计 Spec §3.4 目标**: ~30 模板覆盖小学数学。当前仅 4 个（算术）。

**新增模板文件**:
- `math_fractions.py` — 分数比较、运算、转换 (~5 模板)
- `math_geometry.py` — 周长、面积、角度 (~5 模板)
- `math_word_problems.py` — 行程、价格、比例 (~5 模板)
- 扩展现有 `math_arithmetic.py` — 竖式计算、估算、三位数运算 (~5 模板)

**每个模板**:
- `@register_template("math.xxx.yyy")` 装饰器注册
- 参数化随机（min/max 控制难度）
- topic_key 关联到 os-taxonomy 知识点
- 内置求解器验证答案正确性
- `GeneratedQuestion` 返回（stem_zh 中文题干）

**测试**: 每个模板 2+ tests（答案正确性、参数边界）

#### Sub-issue 125c: 题目去重 + 覆盖率统计

**实现**:
- 去重检测增强：`question_service.check_duplicate(stem, answer)` 
- `GET /practice/coverage` — 知识点覆盖率统计 API
  - 按学科/领域统计：有题目的知识点 / 总知识点
  - 按难度分布
  - 按题型分布
- 前端: 管理端覆盖率仪表盘（或家长端知识点覆盖概览）
- 映射质量验证：topic_key 是否在 learning_topics 中存在

**关键文件**:
- 修改: `server/apps/backend/app/services/learning/question_service.py`
- 修改: `server/apps/backend/app/routers/practice.py` (新增 coverage 端点)
- 新增: `server/apps/backend/app/schemas/practice_coverage.py` 或追加到现有 schemas

**测试**: 3+ tests（覆盖率计算、去重检测、空覆盖率）

**执行方式**: 每个 sub-issue 派生独立 subagent，顺序执行
**循环**: brainstorm → plan → doc-review → work → code-review → issue 评论
**预估**: 3 个 subagent

---

### Step 4: Phase 6 (#128) — 自适应智能练习 ⭐ P2

**目标**: 基于知识追踪和掌握度估计，实现个性化智能选题和自适应学习路径。
**设计约束**: Spec §4（自适应练习引擎）、§4.4（MasteryEstimator 接口已预留）

#### Sub-issue 128a: 接线 MasteryEstimator + 增强 RuleBased

**现状**: `MasteryEstimator` protocol + `RuleBasedMasteryEstimator` 存在但 `select_questions()` 不调用它。

**实现**:
- `select_questions()` 改用 `MasteryEstimator.estimate()` 动态获取掌握度
- 增强 `RuleBasedMasteryEstimator`:
  - 加权近期表现（时间衰减权重）
  - 考虑答题耗时（快速正确 > 慢速正确）
  - 最小样本量阈值（< 3 attempts 回退到 mastery_level 静态映射）
- 注入方式：函数参数或模块级配置，保持向后兼容

**测试**: 5+ tests（加权正确率、时间衰减、阈值回退）

#### Sub-issue 128b: BKT 知识追踪

**设计 Spec §4.4**: `BayesianKnowledgeTracingEstimator(MasteryEstimator)` — Phase 2+ 可替换。

**实现**:
- `BayesianKnowledgeTracingEstimator` 类
  - Per-topic 参数: P(L₀)=初始掌握概率, P(T)=转移概率, P(G)=猜测概率, P(S)=失误概率
  - `estimate()`: 基于 PracticeAttempt 历史计算 posterior P(Lₙ|observations)
  - `update()`: 每次新 attempt 后更新 belief
  - 参数初始化：默认值 + 可选的从数据拟合
  - 数据量阈值：< 5 attempts 回退到 RuleBased
- Alembic 迁移：新增 `topic_mastery_params` 表（或 JSON 字段）存储 per-topic BKT 参数
- 集成到 `practice_progress_integration.update_progress_from_session()`

**测试**: 5+ tests（参数更新、收敛性、回退逻辑）

#### Sub-issue 128c: 增强间隔复习 + 错题复练

**现状**: SM-2 简化为 `interval = 3 * stability`，无 ease_factor / 历史 interval 追踪。

**实现**:
- 增强 SM-2:
  - 新增 `ease_factor` 字段（初始 2.5）到 LearningProgress
  - interval 计算：`I₁=1, I₂=6, Iₙ=Iₙ₋₁ * ease_factor`（经典 SM-2 递推）
  - 根据作答质量调整 ease_factor
  - Alembic 迁移
- 错题复练队列:
  - review 模式: 优先选 overdue + 历史错题
  - 错题优先级: 错误次数多的 > 最近错误的 > 长时间未练习的
- 去重保证: 同一题 7 天内不重复（Spec §4.2，已有 exclude_recent_days）

**测试**: 5+ tests（interval 递推、ease_factor 调整、错题优先排序）

#### Sub-issue 128d: 可解释学习进度反馈

**现状**: `ability_dimensions_score_json` 字段存在但无消费者。

**实现**:
- 能力维度统计:
  - 按领域（数的运算/几何/分数）汇总正确率
  - 填充 `ability_dimensions_score_json`
  - 前端雷达图数据 API
- 知识点掌握趋势:
  - `GET /practice/progress-trend` — 某知识点随时间的掌握度变化
  - 数据源: PracticeAttempt 时间序列 + BKT posterior
- 推荐原因可解释化:
  - `/practice/recommend` 返回 `reason` 字段
  - "因为 X 知识点正确率低且是 Y 的先修" / "因为 X 已 7 天未练习"
- 前端: LearningProgressPage 增强（趋势图 + 推荐原因展示）

**测试**: 4+ tests（维度统计、趋势计算、推荐原因生成）

**执行方式**: 每个 sub-issue 派生独立 subagent，顺序执行
**依赖**: Phase 3 完成后开始（需要足够的题目数据）
**循环**: brainstorm → plan → doc-review → work → code-review → issue 评论
**预估**: 4 个 subagent

---

### Step 5: Phase 7 (#129) — ⏸️ 暂缓

**依赖**: Phase 3 模板 pipeline 稳定后再启动。
**范围**: 语文/英语/科学模板扩展 + 覆盖率评估机制。
**预估**: 机械性工作（pipeline 已建好，主要是模板编写）。

---

## 执行策略

### 上下文管理

| Phase | 执行方式 | Subagent 数 | 理由 |
|-------|---------|------------|------|
| Step 1 (关闭 issues) | 主线程 | 0 | 简单 GitHub 操作 |
| Phase 0 收尾 | 主线程或 1 agent | 0-1 | 轻量统计 |
| Phase 3 (a→b→c) | 顺序 subagent | 3 | 各 sub-issue 独立但有关联 |
| Phase 6 (a→b→c→d) | 顺序 subagent | 4 | 依赖 Phase 3 + 前一个 sub-issue |

### 每个 Subagent 流程

```
ce-brainstorm → ce-plan → ce-doc-review → ce-work → ce-code-review → GitHub 评论更新
```

### 质量关卡

每个 sub-issue 完成后验证:
1. `cd server && uv run pytest tests/backend/ -k "相关模块" -v` — 全绿
2. `cd server && uv run ruff check <changed files>` — 无 lint 错误
3. `cd server && uv run ruff format --check <changed files>` — 格式合规
4. 前端变更: `cd frontend && pnpm -r typecheck && pnpm -r lint`
5. 现有 55 tests 不回归

### 关键文件索引

| 文件 | 用途 |
|------|------|
| `server/packages/domain/question_templates/` | 模板引擎 + 注册表 |
| `server/apps/backend/app/services/learning/question_service.py` | 题目 CRUD + quality gate |
| `server/apps/backend/app/services/learning/adaptive_service.py` | 选题引擎 + MasteryEstimator |
| `server/apps/backend/app/services/learning/progress_service.py` | 状态机 + SM-2 + 间隔复习 |
| `server/apps/backend/app/services/learning/practice_progress_integration.py` | 练习→进度桥接 |
| `server/apps/backend/app/routers/practice.py` | 9 个 practice API 端点 |
| `server/packages/db/models/learning/progress.py` | LearningProgress 模型 (含 stability, mastery_score) |
| `server/packages/os_taxonomy/topics.json` | 1590 知识点数据 |
| `docs/superpowers/specs/2026-10-10-question-bank-adaptive-practice-design.md` | 设计 Spec |

## 风险

| 风险 | 缓解 |
|------|------|
| BKT 参数初始化缺乏训练数据 | 使用论文默认值 (P(L₀)=0.1, P(T)=0.3, P(G)=0.25, P(S)=0.1)，数据量 > 50 attempts 后启用 |
| topic_key → topic_id 映射不完整 | Seeder 中记录未映射的 topic_key，输出警告日志 |
| 模板扩展后题目质量参差 | 所有模板必须通过 quality gate + 答案正确性验证 |
| Phase 6 依赖 Phase 3 题目数据 | Phase 3 先交付足够题目（≥30 知识点各 ≥5 题） |
| 上下文膨胀 | 每个 sub-issue 独立 subagent，完成后释放上下文 |
