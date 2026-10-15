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

## 当前系统状态（代码审计 @ d3884aea）

| 组件 | 状态 | 关键发现 |
|------|------|---------|
| 模板引擎 | ✅ 可用 | 4 个算术模板 (`math_arithmetic.py`)，registry 机制完整 |
| 题目 CRUD | ✅ 可用 | `question_service.py` + quality gate |
| 练习 API | ✅ 9 端点 | sessions/answer/finish/weak-topics/recommend 等 (`routers/practice.py`) |
| 状态机 | ✅ 完整 | 7 状态 + CAS + XP/星星币 + 通知 |
| SM-2 间隔复习 | 🟡 简化版 | 单 stability 浮点，`interval = 3 * stability`，**无 ease_factor** |
| 选题引擎 | 🟡 朴素 | difficulty bucket + random shuffle，**无 BKT** |
| MasteryEstimator | 🟡 未接线 | `RuleBasedMasteryEstimator` 实现存在，但 **`select_questions()` 不调用它** |
| 题目生成 pipeline | ❌ 缺失 | **无批量生成脚本**，`GeneratedQuestion` → `Question` 表桥不存在 |
| topic_key→topic_id 映射 | ❌ 缺失 | `GeneratedQuestion.topic_key` 无法关联到 `LearningTopic.id` |
| 多学科学科模板 | ❌ 缺失 | 仅 `math_arithmetic`，缺分数/几何/应用题 |

### 知识图谱数据概况

`server/packages/os_taxonomy/topics.json` 包含完整 os-taxonomy-beijing 中文数据：

| 指标 | 数量 |
|------|------|
| 知识点 (topics) | 1,590（全部已翻译） |
| 先修关系 (dependencies) | 3,221 条边 |
| 聚类 (clusters) | 183 |

**各学科知识点分布**:

| 学科 | 数量 | 占比 |
|------|------|------|
| Science | 547 | 34.4% |
| Mathematics | 503 | 31.6% |
| English | 286 | 18.0% |
| History | 90 | 5.7% |
| Personal & Social Development | 88 | 5.5% |
| Life Skills | 37 | 2.3% |
| Computing | 21 | 1.3% |
| Learning to Learn | 18 | 1.1% |

> **注意**: Phase 7 全学科扩展时，Mathematics (503) 是最大单一学科，需优先保证模板覆盖。Science (547) 总量最大但知识点粒度可能不同。

### 测试覆盖

- **55 practice 相关 tests** 全部通过（Phase 2-5 交付）
- **2,210+ 后端总 tests**

### Makefile 变更（已提交 @ cff18c6a）

```
setup-learning-data → setup-beijing-data + setup-os-taxonomy-data
```

两个 target 分别处理 os-taxonomy-beijing 中文数据下载和上游 os-taxonomy 子模块初始化。

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
- 统计各学科知识点数量分布（已初步统计见上方表格）
- 先修关系完整性检查：
  - **孤立节点检测**: 无入边且无出边的 topic（知识点在图谱中孤立存在）
  - **循环依赖检测**: A→B→C→A 的先修环路（会导致状态机死锁）
  - **断链检测**: topic 引用了 prerequisites 中不存在的 topic_key
- 课程标准映射覆盖率（对照 2022 义务教育数学课程标准）
- 输出: `docs/superpowers/reports/phase0-data-quality-report.md`
- 辅助脚本: `server/scripts/audit_taxonomy_data.py`（一次性统计脚本，不进入生产代码）

#### Sub-issue 122b: 数据质量问题记录 + Makefile 提交

- ~~提交已有 Makefile 变更~~（已在 `cff18c6a` 提交 ✅）
- 记录已知数据质量问题 + 处理方案：
  - 孤立节点 → 标记但不删除（保留完整性）
  - 循环依赖 → 记录并在 progress_service 中添加防护
  - 断链 → 在 topic_service 中校验时过滤无效 prerequisite
- 关闭 #122

**执行方式**: 主线程直接操作（轻量统计脚本 + 报告撰写）
**预估**: 1 个 subagent（统计脚本 + 报告撰写）

---

### Step 3: Phase 3 (#125) — 题目生成 Pipeline + 知识点映射 ⭐ P1

**目标**: 建立真实题目的合法生成/导入流程，实现题目到 taxonomy 微知识点的可靠映射。
**设计约束**: Spec §1.4（版权安全、质量优先）、§3.1-3.4（三层生成策略）、§8（开源数据源结论）

#### Sub-issue 125a: 模板→DB 批量生成 Pipeline

**缺失**: 模板引擎能生成 `GeneratedQuestion`，但无代码将其持久化到 `Question` 表。

**实现**:
- `question_seeder.py` — 新增服务模块
  - `seed_questions_from_templates(topic_ids: list[int] | None = None)` 
    - 遍历 `TEMPLATE_REGISTRY` 所有已注册模板
    - 每个模板按 `difficulty_range` 生成 N 个变体（参数化随机）
    - **topic_key → topic_id 映射桥**: 通过 `topic_key` 查询 `LearningTopic` 表获取 `id`
      - 映射逻辑: `topic_key` 格式如 `"math.number.operations.addition"` → 查找 `LearningTopic.key == topic_key`
      - 未匹配时: 记录 warning 日志，跳过该题目（不报错中断）
  - 调用 `question_service.create_question()` 持久化（复用 quality gate 校验）
  - **去重检测**: `stem` + `answer` 哈希比对，相同则跳过
  - 返回统计: `{generated: int, skipped_duplicate: int, skipped_no_topic: int, failed: int}`
- **CLI 入口**: 
  - `make seed-questions` → `uv run python -m apps.backend.scripts.seed_questions`
  - 支持参数: `--topic math.number.*`（按知识点过滤）、`--count 10`（每模板生成数）、`--dry-run`
- **幂等性**: 重复运行安全，去重后不产生重复题目
- **日志**: structlog 输出每步骤统计

**关键文件**:
- 新增: `server/apps/backend/app/services/learning/question_seeder.py`
- 新增: `server/apps/backend/scripts/seed_questions.py` (CLI 入口)
- 修改: `server/apps/backend/app/services/learning/question_service.py` — 可能需添加 `bulk_create_questions()` 或 `check_duplicate()` 辅助方法
- 依赖: `server/packages/domain/question_templates/registry.py` — `TEMPLATE_REGISTRY`

**测试**: 5+ tests
- 幂等性: 运行两次，第二次 `generated=0`
- 去重: 手动插入同 stem+answer 的题目后，seeder 跳过
- topic_key 映射: mock LearningTopic 数据验证映射正确
- quality gate: 不合格题目被拦截
- 无匹配 topic: warning 日志，不中断

#### Sub-issue 125b: 扩展模板覆盖

**设计 Spec §3.4 目标**: ~30 模板覆盖小学数学。当前仅 4 个（算术：加减乘除）。

**新增模板文件** (位于 `server/packages/domain/question_templates/`):

| 文件 | 知识点域 | 模板数 | 示例 |
|------|---------|--------|------|
| `math_fractions.py` | 分数/小数 | ~5 | 分数比较、同分母加减、分数转小数 |
| `math_geometry.py` | 几何基础 | ~5 | 矩形周长、矩形面积、三角形面积、角度计算 |
| `math_word_problems.py` | 应用题 | ~5 | 行程问题、价格计算、比例分配 |
| 扩展 `math_arithmetic.py` | 数的运算 | ~5 | 竖式加法、竖式减法、乘法估算、除法余数、混合运算 |

**每个模板必须**:
- `@register_template("math.xxx.yyy")` 装饰器注册
- 参数化随机（`min_val`/`max_val` 控制数值范围 → 控制难度）
- `topic_key` 关联到 os-taxonomy 知识点（如 `"math.number.fractions.comparison"`）
- 内置求解器（`solve()` 方法）验证答案正确性 — **这是质量关卡的核心**
- 返回 `GeneratedQuestion(stem_zh=中文题干, answer=正确答案, difficulty=1-5, topic_key=...)`

**测试**: 每个模板 2+ tests
- 答案正确性: `solve()` 对 100 组随机参数全部正确
- 参数边界: min/max 边界值不产生负数/零除等无效题

#### Sub-issue 125c: 题目去重 + 覆盖率统计

**实现**:
- **去重增强**: `question_service.check_duplicate(stem, answer)` → 基于 `stem_hash` + `answer_hash` 的查重
  - `GeneratedQuestion` 在入库前计算哈希，与现有 `questions` 表比对
- **`GET /practice/coverage`** — 知识点覆盖率统计 API
  - 响应结构:
    ```json
    {
      "total_topics": 1590,
      "covered_topics": 45,
      "coverage_rate": 0.028,
      "by_subject": [
        {"subject": "Mathematics", "total": 503, "covered": 30, "rate": 0.059}
      ],
      "by_difficulty": {"1": 50, "2": 45, "3": 30, "4": 10, "5": 5},
      "unmapped_topic_keys": ["math.xxx.yyy"]
    }
    ```
  - 按学科/领域统计：有题目的知识点 / 总知识点
  - 按难度分布: difficulty 1-5 各多少题
  - 按题型分布: 计算/比较/应用 各多少
- **映射质量验证**: 统计 `question.topic_key` 在 `learning_topics` 中不存在的比例
- 前端: 管理端覆盖率仪表盘（或家长端知识点覆盖概览）— 可选，Phase 3 先交付 API

**关键文件**:
- 修改: `server/apps/backend/app/services/learning/question_service.py` — 新增 `check_duplicate()` + `get_coverage_stats()`
- 修改: `server/apps/backend/app/routers/practice.py` — 新增 coverage 端点
- 新增: coverage response schema（追加到 `schemas/practice.py`）

**测试**: 3+ tests
- 覆盖率计算: 手动构造已知分布的题目数据，验证统计正确
- 去重检测: 重复 stem+answer 被检出，不同题目不被误判
- 空覆盖率: 无题目时返回 `covered_topics=0`，不报错

**执行方式**: 每个 sub-issue 派生独立 subagent，顺序执行
**循环**: `ce-brainstorm → ce-plan → ce-doc-review → ce-work → ce-code-review → GitHub issue 评论`
**预估**: 3 个 subagent

---

### Step 4: Phase 6 (#128) — 自适应智能练习 ⭐ P2

**目标**: 基于知识追踪和掌握度估计，实现个性化智能选题和自适应学习路径。
**设计约束**: Spec §4（自适应练习引擎）、§4.4（MasteryEstimator 接口已预留）

#### Sub-issue 128a: 接线 MasteryEstimator + 增强 RuleBased

**现状**: `adaptive_service.py` 中 `MasteryEstimator` protocol + `RuleBasedMasteryEstimator` 存在但 `select_questions()` 不调用它。当前选题仅靠 `LearningProgress.mastery_level` 静态映射到 difficulty bucket。

**实现**:
- **接线**: `select_questions()` 内部调用 `estimator.estimate(child_id, topic_id, recent_attempts)` 获取动态掌握度
  - 返回值 0.0-1.0 → 映射到 difficulty 1-5（替代当前静态映射表）
- **增强 `RuleBasedMasteryEstimator`**:
  - **加权近期表现**: 最近 5 次 attempt 按时间衰减加权（`weight = 0.8^(n-1)`）
  - **答题耗时因子**: 快速正确（< expected_time）权重 1.2，慢速正确权重 0.9
  - **最小样本量阈值**: < 3 attempts → 回退到 `mastery_level` 静态映射（数据不足不可靠）
  - **注入方式**: 模块级单例 `DEFAULT_MASTERY_ESTIMATOR`，`select_questions()` 接受可选 `estimator` 参数覆盖
- **向后兼容**: 默认行为不变（回退路径保证）

**关键文件**:
- 修改: `server/apps/backend/app/services/learning/adaptive_service.py`
  - `select_questions()` 签名添加 `estimator: MasteryEstimator | None = None`
  - 新增 `_get_mastery_score()` 内部方法封装 estimate 调用

**测试**: 5+ tests
- 加权正确率: 最近全对 > 早期全对最近差
- 时间衰减: 3 次全对 vs 3 次全错，正确率差异 > 0.3
- 阈值回退: 0-2 attempts 时使用 mastery_level 映射
- 向后兼容: 不传 estimator 时行为与旧逻辑一致

#### Sub-issue 128b: BKT 知识追踪

**设计 Spec §4.4**: `BayesianKnowledgeTracingEstimator(MasteryEstimator)` — Phase 2+ 可替换。

**实现**:
- `BayesianKnowledgeTracingEstimator` 类（新增于 `adaptive_service.py`）
  - Per-topic 参数: `P(L₀)=0.1` (初始掌握概率), `P(T)=0.3` (转移概率), `P(G)=0.25` (猜测概率), `P(S)=0.1` (失误概率)
  - **`estimate()`**: 基于 `PracticeAttempt` 历史计算 posterior P(Lₙ|observations)
    ```
    P(Lₙ|correct) = P(Lₙ)(1-P(S)) / [P(Lₙ)(1-P(S)) + (1-P(Lₙ))P(G)]
    P(Lₙ₊₁) = P(Lₙ|obs)(1-P(T)) + (1-P(Lₙ|obs))P(T)
    ```
  - **参数存储**: `LearningProgress.bkt_params_json` (JSON 字段, 或新增 `topic_mastery_params` 表)
    - `{topic_id: {p_l0, p_t, p_g, p_s, p_current}}` 
  - **`update()`**: 每次 attempt 后调用，更新 belief state
  - 集成点: `practice_progress_integration.update_progress_from_session()` 中 session finish 时批量更新
  - **数据量阈值**: per-topic < 5 attempts → 回退到 `RuleBasedMasteryEstimator`
  - Alembic 迁移: 新增 `bkt_params_json` JSON 字段到 `learning_progress` 表

**关键文件**:
- 修改: `server/apps/backend/app/services/learning/adaptive_service.py` — 新增 BKT 类
- 修改: `server/packages/db/models/learning/progress.py` — 新增 `bkt_params_json` 字段
- 修改: `server/apps/backend/app/services/learning/practice_progress_integration.py` — 集成 BKT update
- 新增: Alembic migration for `bkt_params_json`

**测试**: 5+ tests
- 参数更新: 连续正确后 P(L) 单调递增
- 失误处理: 1 次错误后 P(L) 轻微下降但不归零
- 收敛性: 50 次全对后 P(L) > 0.95
- 回退逻辑: < 5 attempts 时自动降级到 RuleBased

#### Sub-issue 128c: 增强间隔复习 + 错题复练

**现状**: SM-2 简化为 `interval = 3 * stability`，无 `ease_factor` / 历史 interval 追踪。`LearningProgress` 仅有 `stability` 和 `next_review_at`。

**实现**:
- **增强 SM-2** (修改 `progress_service.py`):
  - 新增 `ease_factor` 字段到 `LearningProgress`（初始 2.5，最低 1.3）
  - interval 计算改为经典 SM-2 递推:
    ```
    quality = attempt_quality(attempt)  # 0-5 基于正确性+耗时
    I₁ = 1 day, I₂ = 6 days
    Iₙ = Iₙ₋₁ × ease_factor  (当 quality >= 3)
    ease_factor' = ease_factor + 0.1 - (5-quality)(0.08 + (5-quality)*0.02)
    ```
  - quality < 3: 重置 interval = 1, 不更新 ease_factor
  - Alembic 迁移: `ALTER TABLE learning_progress ADD COLUMN ease_factor REAL DEFAULT 2.5`
- **错题复练队列** (增强 `adaptive_service.py`):
  - review 模式: `select_questions(mode="review")` 优先选 overdue + 历史错题
  - 错题优先级排序:
    1. 错误次数多的（同一知识点反复出错）
    2. 最近错误的（短期记忆仍清晰）
    3. 长时间未练习的（遗忘曲线）
  - 去重保证: 同一题 7 天内不重复（Spec §4.2，已有 `exclude_recent_days` 参数）

**关键文件**:
- 修改: `server/packages/db/models/learning/progress.py` — 新增 `ease_factor` 字段
- 修改: `server/apps/backend/app/services/learning/progress_service.py` — SM-2 递推逻辑
- 修改: `server/apps/backend/app/services/learning/adaptive_service.py` — 错题优先排序
- 新增: Alembic migration for `ease_factor`

**测试**: 5+ tests
- interval 递推: I₁=1, I₂=6, I₃=6×2.5=15
- ease_factor 调整: 连续满分 → ease_factor 上升；连续错误 → 下降但不低于 1.3
- 错题优先: 错误 3 次的题 > 错误 1 次的题 > 无错误但 overdue 的题
- quality < 3 重置: interval 归 1

#### Sub-issue 128d: 可解释学习进度反馈

**现状**: `ability_dimensions_score_json` 字段存在但无消费者。家长看不到孩子各维度的掌握趋势。

**实现**:
- **能力维度统计** (增强 `stats_service.py`):
  - 按领域（数的运算/几何/分数/应用题）汇总最近 N 次正确率
  - 填充 `ability_dimensions_score_json`:
    ```json
    {"数的运算": 0.82, "几何基础": 0.65, "分数小数": 0.40, "应用题": 0.55}
    ```
  - 更新时机: session finish 时计算
  - **前端雷达图数据 API**: `GET /practice/ability-dimensions` 返回维度名+分数
- **知识点掌握趋势**:
  - `GET /practice/progress-trend?topic_id=xxx` — 某知识点随时间的掌握度变化
  - 数据源: `PracticeAttempt` 时间序列 + BKT posterior（若有）
  - 返回: `[{date, mastery_score, correct, attempt_count}]`
- **推荐原因可解释化**:
  - `/practice/recommend` 返回 `reason` 字段:
    - `"该知识点正确率仅 35%，建议加强练习"`
    - `"该知识点是'分数乘法'的先修，当前掌握不足"`
    - `"该知识点已 7 天未练习，建议复习"`
- 前端: `LearningProgressPage` 增强 — 趋势图 + 推荐原因展示

**关键文件**:
- 修改: `server/apps/backend/app/services/learning/stats_service.py` — 维度统计 + 趋势查询
- 修改: `server/apps/backend/app/services/learning/adaptive_service.py` — recommend 增加 reason
- 修改: `server/apps/backend/app/routers/practice.py` — 新增 `GET /practice/ability-dimensions` + `GET /practice/progress-trend`
- 前端 (可选): child app LearningProgressPage 增强

**测试**: 4+ tests
- 维度统计: 混合正确率按领域加权平均正确
- 趋势计算: 时间序列按日期排序，mastery_score 单调（BKT 保证）
- 推荐原因: 低正确率/先修不足/长时间未练 各生成不同 reason
- 空数据: 无 attempt 时返回空列表，不报错

**执行方式**: 每个 sub-issue 派生独立 subagent，顺序执行
**依赖**: Phase 3 完成后开始（需要足够的题目数据支撑 BKT 和趋势分析）
**循环**: `ce-brainstorm → ce-plan → ce-doc-review → ce-work → ce-code-review → GitHub issue 评论`
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
| Phase 0 收尾 | 主线程或 1 agent | 0-1 | 轻量统计脚本 + 报告 |
| Phase 3 (a→b→c) | 顺序 subagent | 3 | 各 sub-issue 独立但有关联 |
| Phase 6 (a→b→c→d) | 顺序 subagent | 4 | 依赖 Phase 3 + 前一个 sub-issue |

### 每个 Sub-issue 执行流程

```
┌─────────────┐    ┌──────────┐    ┌──────────────┐    ┌─────────┐    ┌──────────────┐    ┌──────────────┐
│ ce-brainstorm│───▶│ ce-plan  │───▶│ ce-doc-review│───▶│ ce-work │───▶│ ce-code-review│───▶│ GitHub 评论  │
│ (scope探索)  │    │(结构化计划)│    │ (文档审查)   │    │(实现代码) │    │ (代码审查)    │    │ (更新issue)  │
└─────────────┘    └──────────┘    └──────────────┘    └─────────┘    └──────────────┘    └──────────────┘
```

每个 sub-issue 派生**独立 subagent**，完成后释放上下文，避免上下文膨胀。

### 质量关卡

每个 sub-issue 完成后验证:
1. `cd server && uv run pytest tests/backend/ -k "相关模块" -v` — 全绿
2. `cd server && uv run ruff check <changed files>` — 无 lint 错误
3. `cd server && uv run ruff format --check <changed files>` — 格式合规
4. 前端变更: `cd frontend && pnpm -r typecheck && pnpm -r lint`
5. 现有 55 practice tests + 全部 2,210+ tests 不回归
6. 新增 tests 覆盖核心逻辑（去重、映射、SM-2、BKT）

### 推荐 Skills

| Skill | 用途 | 时机 |
|-------|------|------|
| `compound-engineering:ce-brainstorm` | 每个 sub-issue 的 scope 探索 | 开始前 |
| `compound-engineering:ce-plan` | 创建结构化实现计划 | brainstorm 后 |
| `compound-engineering:ce-doc-review` | 审查计划文档 | plan 完成后 |
| `compound-engineering:ce-work` | 执行实现 | review 通过后 |
| `compound-engineering:ce-code-review` | 代码审查 | work 完成后 |
| `compound-engineering:ce-commit` | 提交变更 | review 通过后 |
| `superpowers:subagent-driven-development` | 调度各 sub-issue 的 subagent | 全局编排 |
| `numina-sim-test` | 全栈验收测试 | Phase 3 和 Phase 6 完成后 |

### 关键文件索引

| 文件 | 用途 |
|------|------|
| `server/packages/domain/question_templates/` | 模板引擎 + 注册表 (`registry.py`, `base.py`) |
| `server/packages/domain/question_templates/math_arithmetic.py` | 4 个算术模板实现 |
| `server/apps/backend/app/services/learning/question_service.py` | 题目 CRUD + quality gate |
| `server/apps/backend/app/services/learning/adaptive_service.py` | 选题引擎 + MasteryEstimator protocol |
| `server/apps/backend/app/services/learning/progress_service.py` | 状态机 + SM-2 + 间隔复习 |
| `server/apps/backend/app/services/learning/practice_progress_integration.py` | 练习→进度桥接 |
| `server/apps/backend/app/services/learning/stats_service.py` | 学习统计 + 进度查询 |
| `server/apps/backend/app/services/learning/scoring_service.py` | 答题评分 |
| `server/apps/backend/app/services/learning/session_service.py` | 练习会话管理 |
| `server/apps/backend/app/routers/practice.py` | 9 个 practice API 端点 |
| `server/packages/db/models/learning/progress.py` | LearningProgress 模型 (stability, mastery_score, next_review_at) |
| `server/packages/db/models/learning/` | 全部学习相关模型 (Question, PracticeSession, PracticeAttempt 等) |
| `server/packages/os_taxonomy/topics.json` | 1,590 知识点数据 (8 学科) |
| `server/packages/os_taxonomy/dependencies.json` | 3,221 条先修关系 |
| `server/packages/os_taxonomy/clusters.json` | 183 个聚类 |
| `docs/superpowers/specs/2026-10-10-question-bank-adaptive-practice-design.md` | 设计 Spec |
| `docs/superpowers/plans/2026-10-10-question-bank-practice.md` | Phase 1-5 实施计划 (已完成) |

## 风险与缓解

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | BKT 参数初始化缺乏训练数据 | BKT 估计不准，退化为随机 | 使用论文默认值 (P(L₀)=0.1, P(T)=0.3, P(G)=0.25, P(S)=0.1)；< 5 attempts 自动回退 RuleBased；50+ attempts 后才启用 BKT |
| R2 | topic_key → topic_id 映射不完整 | 部分模板生成的题目无法关联知识点 | Seeder 记录未映射的 topic_key 并输出 warning 日志；125c 的覆盖率 API 报告 `unmapped_topic_keys` |
| R3 | 模板扩展后题目质量参差 | 用户做到错误题目，体验差 | 所有模板必须通过 `solve()` 答案正确性验证 + quality gate；100 组随机参数测试 |
| R4 | Phase 6 依赖 Phase 3 题目数据 | BKT 和趋势分析无数据可算 | Phase 3 先交付 ≥30 知识点各 ≥5 题（Spec §Phase 2 进入条件） |
| R5 | 上下文膨胀导致 subagent 质量下降 | 后期 sub-issue 实现粗糙 | 每个 sub-issue 独立 subagent，完成后释放上下文；separate plans per sub-issue |
| R6 | Alembic 迁移冲突 | 新增字段与 main 分支冲突 | 每个 Phase 的迁移独立命名；部署前 rebase 检查 |
| R7 | SM-2 ease_factor 迁移数据兼容 | 现有 `stability` 值无法直接映射到 `ease_factor` | 迁移时为现有记录设默认 ease_factor=2.5；旧 stability 继续用于非 SM-2 路径 |

## 交付物总览

| Phase | 交付物 | 进入条件 |
|-------|--------|---------|
| Phase 0 | 数据质量报告 + Makefile targets ✅ | - |
| Phase 3a | `question_seeder.py` + `seed-questions` CLI + 5 tests | Phase 0 关闭 |
| Phase 3b | ~20 新模板 (分数/几何/应用题/扩展算术) + 40 tests | 3a 完成 |
| Phase 3c | `GET /practice/coverage` API + 去重增强 + 3 tests | 3b 完成 |
| Phase 6a | MasteryEstimator 接线 + 增强 RuleBased + 5 tests | Phase 3 完成 |
| Phase 6b | BKT 知识追踪 + Alembic 迁移 + 5 tests | 6a 完成 |
| Phase 6c | SM-2 ease_factor + 错题复练 + Alembic 迁移 + 5 tests | 6b 完成 |
| Phase 6d | 能力维度 API + 趋势 API + 推荐原因 + 4 tests | 6c 完成 |

## 依赖关系图

```
Phase 0 ──┐
           ├──▶ Phase 3a ──▶ Phase 3b ──▶ Phase 3c ──┐
           │                                           ├──▶ Phase 6a ──▶ Phase 6b ──▶ Phase 6c ──▶ Phase 6d
           │                                           │
           └───────────────────────────────────────────┘
           
Phase 7 (全学科) ─── 暂缓，等 Phase 3 pipeline 稳定后启动
```
