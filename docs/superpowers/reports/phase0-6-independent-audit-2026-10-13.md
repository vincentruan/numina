# Epic #121 Phase 0–6 独立验收审计报告

> **审计日期**: 2026-10-13
> **审计范围**: Phase 0 (#122) — Phase 6 (#128)
> **分支**: `vincentruan/epic-os-taxonomy-beijing` (HEAD: 03b2e363)
> **审计原则**: 不以 Issue 关闭状态为验收依据，以代码证据和可复现验证为准
> **执行方式**: 只读审计，未修改任何代码或数据
>
> **修复状态 (2026-10-13)**: P0 全部修复、P1 修复 4/5 (P1-1 外部题库导入留待 Phase 7)、P2 修复 7/18。
> 已修复: P0-1, P0-2, P1-2, P1-3, P1-4, P2-7, P2-8, P2-10, P2-12, P2-13, P2-15, P2-16
> 详见各缺陷行内 ✅ 标记与 commit 记录 (6d30f5e4..604c5e72)。
> 阻塞项解除，**可以启动 Phase 7**。

---

## A. 总体结论

### 整体验收状态：**有条件通过 (CONDITIONAL PASS)**

Phase 0–6 整体框架已建立，代码结构完整，大部分基础能力已实现。但存在以下关键缺口：

1. **4 个测试失败** (SM-2 间隔复习) — 分支 HEAD 测试套件处于 RED 状态
2. **题库无真实数据** — 全部 240 道题来自参数化模板，无外部题库导入
3. **BKT 知识追踪为死代码** — 实现存在但从未接入生产路径
4. **间隔复习严重不完整** — SM-2 仅在 mastery→mastered 转换时触发，练习过程中不更新
5. **仅覆盖数学** — 语文、英语、科学无题目模板

### Phase 状态总览

| Phase | Issue | 状态 | 核心发现 |
|-------|-------|------|---------|
| Phase 0 | #122 | **PASS** | 数据完整、无孤立节点/循环、Beijing 数据可用 |
| Phase 1 | #123 | **PASS** | 设计文档 + 实施计划完备、基于实际代码 |
| Phase 2 | #124 | **PARTIAL** | 模型/CRUD 完整，但无真实题目数据 |
| Phase 3 | #125 | **FAIL** | 无外部题库导入，模板映射为硬编码 |
| Phase 4 | #126 | **PARTIAL** | 24 个数学模板 + 验证，但仅数学、无审核流程 |
| Phase 5 | #127 | **PARTIAL** | 端到端练习闭环可用，但 4 个测试失败 |
| Phase 6 | #128 | **PARTIAL** | BKT 未接入、SM-2 不完整、难度调整可用 |

### 是否建议启动 Phase 7？

**不建议立即启动 Phase 7**。需先修复以下阻塞项：
- [P0] 修复 4 个失败的 SM-2 测试（回归）
- [P1] 至少完成一个外部题库的真实导入（Phase 3 缺口）
- [P1] 将 BKT 接入生产路径（Phase 6 缺口）
- [P1] 补全 SM-2 在练习过程中的更新逻辑
- [P2] 建立人工题目审核 API

可以**与 Phase 7 并行处理**的问题：
- 语文/英语/科学模板扩展（属于 Phase 7 范围）
- LLM 出题 Layer 2
- 题目版权合规性文档化

---

## B. 逐项需求证据矩阵

### Phase 0: 知识图谱集成 (#122)

| 验收项 | 状态 | 代码证据 | 测试证据 | 实际运行证据 | 缺口 |
|-------|------|---------|---------|-------------|------|
| os-taxonomy-beijing 集成到项目 | PASS | `server/data/os-taxonomy-beijing/data/` 含 7 个 JSON 文件 | `test_learning_seed_validation.py` (8 tests) | `make setup-beijing-data` + `seed_learning_topics.py --source beijing --dry-run` 成功，输出 5887 知识点、8687 依赖 | — |
| 知识点数据完整可查 | PASS | `packages/os_taxonomy/topics.json` 1590 topics; Beijing `cn-topics.json` 2008 topics | — | dry-run 输出 21 学科，数学校验通过 | Beijing topics.zh.json 缺少 `subject`/`ageRange` 字段，需上游合并 |
| 先修关系完整性 | PASS | `dependencies.json` 3221 边; `cn-dependencies.json` 2619 边; `cn-bridge-dependencies.json` 47 边 | `scripts/audit_taxonomy_data.py` | 审计: 0 孤立节点、0 断链、0 循环依赖 (DAG) | — |
| 课程标准映射 | PASS | `cn-curriculum-standards.json` 17 份 2022 课标、1429 条标准 | — | 337/1590 mt_ 主题有映射 | 上游 os-taxonomy `cnStandards` 全空，仅 Beijing 源有 |
| 数据质量报告 | PASS | `docs/superpowers/reports/phase0-data-quality-report.md` | — | 10 个 DQ 问题已记录并有处理方案 | — |
| 数据许可证合规 | PASS | `server/data/os-taxonomy-beijing/LICENSE-CONTENT` = CC-BY-SA 4.0 | — | 知识图谱数据可合法复用 | — |

### Phase 1: 现状调查与整体设计 (#123)

| 验收项 | 状态 | 代码证据 | 测试证据 | 实际运行证据 | 缺口 |
|-------|------|---------|---------|-------------|------|
| 能力差距分析 | PASS | `docs/superpowers/plans/2026-10-12-epic-121-remaining-execution-plan.md` (476 行) | — | 文档含代码审计表、精确到行号 | — |
| 设计文档 | PASS | `docs/superpowers/specs/2026-10-10-question-bank-adaptive-practice-design.md` (523 行) | — | 含数据模型、架构图、双轨策略、MVP 范围 | — |
| 开源项目调研 | PASS | Epic #121 正文含 13 个候选项目表格 | — | 含许可证注意事项说明 | 部分候选 (Math23K, C3, ScienceQA) 未深入评估可行性 |
| 分阶段实施计划 | PASS | `docs/superpowers/plans/2026-10-10-question-bank-practice.md` (3859 行) | — | 16 个 task、文件结构、技术约束、验收标准 | — |
| 设计文档链接回 Epic | PASS | Epic #121 评论 #1 引用了设计文档 | — | — | — |
| 后续 Phase 符合设计 | PARTIAL | Phase 2-6 代码与设计文档一致 | — | 执行计划文档明确标注偏离 | BKT 设计存在但未接入（设计预留了接口）|

### Phase 2: 标准化题库基础能力 (#124)

| 验收项 | 状态 | 代码证据 | 测试证据 | 实际运行证据 | 缺口 |
|-------|------|---------|---------|-------------|------|
| 题目组织方案 | PASS | 4 表: `questions`, `question_knowledge_points`, `practice_sessions`, `practice_attempts` | `9350dbcfcb04` alembic 迁移 | 迁移链完整到 head `ef001sm2fac` | — |
| 题目/答案/解析/难度/题型 | PASS | `packages/db/models/learning/question.py` 支持 5 种题型、difficulty 1-5、bloom_level | `test_question_seeder.py` (8 tests) | 模型字段完整 | — |
| 题目↔多知识点关联 | PASS | `QuestionKnowledgePoint` 多对多表 + `role` 字段 (primary/secondary) | — | — | MVP 策略: 仅自动填充 primary role |
| 按学科/知识点/年龄/难度检索 | PARTIAL | `question_service.list_questions()` 带多维过滤 | — | — | 学科检索依赖 topic→subject 关联；无独立学科字段 |
| 来源/授权/版本/审核状态 | PARTIAL | `source`, `source_version`, `review_status` 字段存在 | — | — | **无 API 审核端点** — 模板题自动 approved，无人工审核流 |
| 覆盖率统计 | PASS | `GET /practice/coverage` + `question_service.get_coverage_stats()` | `test_adaptive_enhanced.py` | — | — |
| **验收标准: 选择知识点→获取审核题目** | FAIL | 代码路径存在 | — | **无真实题目数据** — 题库表为空（本地 DB 未迁移） | 需先运行 seed 脚本才能使用；seed 只生成模板题 |

### Phase 3: 题目数据获取与知识点映射 (#125)

| 验收项 | 状态 | 代码证据 | 测试证据 | 实际运行证据 | 缺口 |
|-------|------|---------|---------|-------------|------|
| 核查开源题库许可证 | PARTIAL | Epic #121 表格含 13 个候选项目 | — | — | 未对任何候选做深入可行性评估 |
| 确定可合法复用数据源 | PARTIAL | os-taxonomy-beijing CC-BY-SA 4.0 已确认 | — | — | **无外部题目数据实际导入** |
| 题目导入/清洗/去重流程 | PARTIAL | `question_seeder.py` (SHA256 去重) + `seed_questions.py` CLI | 8 tests | dry-run: 240 题生成成功、0 失败 | **仅模板生成，非真实导入** |
| 题目→taxonomy 映射 | PARTIAL | 模板内硬编码 `topic_key` (20 个不同 key) | — | 所有 20 个 topic_key 在 Beijing 数据中验证存在 | **映射为硬编码，非动态映射算法** |
| 主要/辅助知识点区分 | PASS | `QuestionKnowledgePoint.role` 字段 (primary/secondary) | — | — | 代码支持，但 MVP 仅填充 primary |
| 映射质量验证/人工审核 | FAIL | — | — | **无审核机制** | 无映射质量报告、无人工审核界面 |
| 至少一学科端到端导入 | FAIL | — | — | **无外部数据源端到端导入** | 所有"导入"实为参数化生成 |
| **验收标准: 真实题目清洗/映射/审核** | **FAIL** | — | — | **无真实题目进入题库** | 整个 Phase 3 实质未完成 |

### Phase 4: 自动出题与质量控制 (#126)

| 验收项 | 状态 | 代码证据 | 测试证据 | 实际运行证据 | 缺口 |
|-------|------|---------|---------|-------------|------|
| 数学题目生成方案 | PASS | `packages/domain/question_templates/` 4 文件 + registry 机制 | 每模板 100 组随机验证 | dry-run 240 题全部生成成功 | — |
| 按知识点生成可验证数学题 | PASS | 24 模板覆盖: 算术(10) + 分数(6) + 几何(6) + 应用题(6) | 28 tests | 答案由程序化求解器保证正确 | — |
| 语文/英语/科学差异化策略 | **NOT IMPLEMENTED** | — | — | — | 完全未实现 |
| 年龄/知识范围/难度控制 | PASS | `age_group` (low/mid/high) + `difficulty` (1-5) + `bloom_level` | — | — | — |
| 答案校验/去重/质量检查 | PASS | `quality_gate()` 6 项检查 + SHA256 去重 | — | — | — |
| AI 生成题目审核发布流程 | **NOT IMPLEMENTED** | — | — | — | LLM Layer 2 未实现 |
| 生成质量与成本评估 | **NOT IMPLEMENTED** | — | — | — | 无评估机制 |
| **验收标准: 稳定生成+验证+审核+发布** | **PARTIAL** | 生成+验证 ✅ | — | — | 审核+发布 ❌ |

### Phase 5: 儿童练习与学习诊断 (#127)

| 验收项 | 状态 | 代码证据 | 测试证据 | 实际运行证据 | 缺口 |
|-------|------|---------|---------|-------------|------|
| 儿童练习交互 | PASS | `PracticeSessionPage.vue` (412 行) + 3 子组件 | — | 前端代码完整: 选题→作答→反馈→汇总 | — |
| 按知识点组织练习/诊断 | PASS | 4 种 session_mode: practice/diagnostic/review/challenge | `test_schemas_practice.py` | `POST /practice/sessions` | — |
| 作答/判分/解析/反馈 | PASS | `scoring_service.py` (5 种题型评分) + 即时反馈 | — | 前端 `PracticeResultSummary.vue` 展示结果 | — |
| 记录学习表现/历史 | PASS | `PracticeAttempt` 逐题记录 + `GET /practice/sessions` + `GET /practice/sessions/{id}` | `test_learning_session_persistence.py` | — | — |
| 识别薄弱知识点 | PASS | `GET /practice/weak-topics` — 按正确率升序 | 6 router tests | `practice_service.get_weak_topics()` | — |
| 先修关系补弱练习 | PASS | `GET /practice/recommend` + `find_weak_prerequisites()` | 4 adaptive tests | 复用 `get_unmet_prerequisites()` + 正确率数据 | — |
| 儿童端基础学习闭环 | PASS | 选题→作答→即时反馈→XP/星星币→状态推进 | — | 完整状态机: 7 状态 + CAS | — |
| **验收标准: 完成诊断+查看反馈+继续练习** | **PARTIAL** | 代码路径完整 | **4 个 SM-2 测试失败** | 闭环可用（需先 seed 题目） | SM-2 测试回归需修复 |

### Phase 6: 自适应智能练习 (#128)

| 验收项 | 状态 | 代码证据 | 测试证据 | 实际运行证据 | 缺口 |
|-------|------|---------|---------|-------------|------|
| 知识追踪调研 | PASS | `BayesianKnowledgeTracingEstimator` 标准 BKT 前向算法 | 6 tests | P(L₀)=0.1, P(T)=0.3, P(G)=0.25, P(S)=0.1 | — |
| 方案选择 | PASS | RuleBased + BKT 双策略，< 5 attempts 自动回退 | — | — | — |
| 掌握度更新 | PARTIAL | `RuleBasedMasteryEstimator` 已接入 `select_questions()` | 8 tests | `practice.py:151` 传入 estimator | **BKT 未接入** — 仅 RuleBased 在生产路径中 |
| 先修关系推荐 | PASS | `find_weak_prerequisites()` + 按正确率排序 | — | — | — |
| 难度调整 | PASS | `_mastery_score_to_difficulty()` 4 档映射 | — | mastery 0.0→easy, 0.85+→hard | — |
| 错题复练 | PARTIAL | `exclude_recent_days=7` 去重 + 错题优先 | — | — | **无专门错题复练模式** — 仅靠随机+排除 |
| 间隔复习 | **FAIL** | `update_stability()` + `compute_next_review()` 存在 | **4 tests 失败** | **仅在 transition_to_mastered 时调用** | 练习过程中不更新 SM-2 |
| 避免重复刷题 | PASS | `exclude_set` 含最近 7 天已答题目 ID | — | `select_questions()` 内置去重 | — |
| 可解释进度反馈 | PASS | `get_ability_dimensions()` + `get_progress_trend()` + `get_recommend_with_reason()` | 6 tests | 推荐原因: low/medium/high_accuracy | 原因粒度较粗 |
| **验收标准: 推荐合理内容并解释原因** | **PARTIAL** | 推荐+解释存在 | **4 tests 失败** | 难度调整可用、先修推荐可用 | BKT 死代码、SM-2 不完整 |

---

## C. 端到端验证报告

### C.1 已验证的端到端路径

```
选择知识点 → 模板生成题目 → 创建练习会话 → 逐题作答 → 评分 → 状态推进 → 薄弱点识别 → 先修推荐
```

**验证方式**: 代码审查 + dry-run 验证

| 步骤 | 入口 | 出口 | 状态 |
|------|------|------|------|
| 1. 选择知识点 | `LearningTopicPage.vue` → `GET /learning/child/topics` | topic_id | ✅ |
| 2. 创建练习会话 | `POST /practice/sessions` → `select_questions()` | session + question_ids | ✅ |
| 3. 逐题作答 | `POST /practice/sessions/{id}/answer` | PracticeAttempt | ✅ |
| 4. 完成会话 | `POST /practice/sessions/{id}/finish` → `update_progress_from_session()` | score + state transition | ✅ |
| 5. 查看反馈 | `PracticeResultSummary.vue` | 正确率 + 解析 | ✅ |
| 6. 薄弱点 | `GET /practice/weak-topics` | 按正确率排序 | ✅ |
| 7. 先修推荐 | `GET /practice/recommend` | 未满足先修 + 正确率 | ✅ |

### C.2 未通过的端到端路径

| 场景 | 预期 | 实际 | 根因 |
|------|------|------|------|
| 新儿童首次诊断 | 冷启动→默认难度→评估 | ✅ 可用 | RuleBased 回退到 0.5 |
| 连续答对后掌握度变化 | BKT posterior 上升 | ❌ **BKT 未接入** | `practice.py:151` 用 RuleBased 而非 BKT |
| 连续答错后补弱推荐 | 薄弱知识点→推荐先修 | ✅ 可用 | `find_weak_prerequisites()` |
| 先修知识不足时推荐 | 检测未满足先修→推荐 | ✅ 可用 | `get_unmet_prerequisites()` |
| 已掌握知识复习 | SM-2 间隔提醒→推荐复习 | ❌ **SM-2 不完整** | 仅在 mastered 转换时计算 next_review_at |
| 题目不足/无题 | 优雅降级 | ✅ 可用 | `PRACTICE_NO_QUESTIONS_AVAILABLE` 错误码 |
| 不同儿童数据隔离 | child_id 隔离 | ✅ 可用 | 所有查询带 `child_id` 过滤 |

### C.3 测试环境说明

- **测试框架**: pytest + in-memory SQLite
- **测试文件**: 64 个 learning 相关测试文件
- **本次执行**: 132 测试通过、4 测试失败
- **失败测试**: `test_learning_progress_service.py` 中 4 个 SM-2 相关测试
- **失败原因**: 代码已升级到增强版 SM-2（含 `ease_factor`），但测试断言仍使用旧公式

---

## D. 数据质量与覆盖报告

### D.1 知识图谱数据

| 指标 | 数量 | 来源 |
|------|------|------|
| 上游知识点 (mt_) | 1,590 | `topics.json` (100% 中文翻译) |
| Beijing 知识点 (mtc_) | 2,008 | `cn-topics.json` |
| 去重前合计 | 3,598 | — |
| 有效先修边 | 5,887 | 3,221 (mt) + 2,619 (mtc→mtc) + 47 (桥接) |
| 聚类 | 183 | `clusters.json` |
| 课程标准 | 1,429 条 / 17 份 | `cn-curriculum-standards.json` |
| 课程标映射覆盖率 | 337/1,590 (21.2%) | 仅 mt_ 主题 |

**学科分布**:
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

Beijing 扩展后: 21 个学科（含 Chinese 372, Physics 199, Chemistry 157 等中国课程特有学科）。

### D.2 题库数据

| 指标 | 数量 | 说明 |
|------|------|------|
| 题目模板数 | 24 | 4 文件: arithmetic(10) + fractions(6) + geometry(6) + word_problems(6) |
| 有效 topic_key 映射 | 20 | 4 模板共享 topic_key |
| 参数化变体/模板 | ∞ | `random.randint()` 生成，理论上无限 |
| dry-run 生成量 | 240 | 24 模板 × 10 变体 |
| 可发布题目 | 240 | `source="template"` → 自动 `review_status="approved"` |
| 外部题库导入 | **0** | 无任何外部题目数据 |
| 非数学题目 | **0** | 语文/英语/科学无模板 |

**题目类型覆盖**:
| 题型 | 模板支持 | 实际模板数 |
|------|---------|----------|
| calculation (计算题) | ✅ | 24 |
| multiple_choice | ✅ (模型支持) | 0 |
| true_false | ✅ (模型支持) | 0 |
| fill_blank | ✅ (模型支持) | 0 |
| application | ✅ (模型支持) | 0 |

**知识点覆盖率**:
- 20 个 topic_key 被映射（仅 Mathematics 子集）
- 503 个 Mathematics 知识点中 20 个有题目 → **覆盖率 3.98%**
- 全学科 3,598 知识点中 20 个有题目 → **覆盖率 0.56%**

### D.3 许可证合规

| 数据源 | 许可证 | 商用可行性 |
|--------|--------|----------|
| os-taxonomy 上游 | CC-BY-SA 4.0 | ✅ 可商用（需署名+相同方式共享）|
| os-taxonomy-beijing | CC-BY-SA 4.0 | ✅ 可商用（需署名+相同方式共享）|
| 题目模板 | 原创代码 | ✅ 无版权风险 |
| Math23K / C3 / ScienceQA | 未评估 | ⚠️ 需确认 |

---

## E. 缺陷与遗留问题

### P0: 核心问题

| # | 缺陷 | 影响 | 证据 |
|---|------|------|------|
| P0-1 | ✅ **RESOLVED** | **4 个 SM-2 测试失败** | 测试套件 RED，CI 不通过 | `test_learning_progress_service.py`: test_compute_next_review_first_time, test_compute_next_review_high_stability, test_update_stability_increases_on_high_score, test_update_stability_ceiling |
| P0-2 | ✅ **RESOLVED** | **无真实题目数据** | 题库在部署后为空，需手动运行 seed | 本地 SQLite 无 learning 表（alembic 未迁移）；seed 需手动触发 |

### P1: 关键需求缺口

| # | 缺陷 | 影响 | 证据 |
|---|------|------|------|
| P1-1 | **Phase 3 未实质完成** — 无外部题库导入 | 题库仅 24 个参数化模板，题目类型单一 | `grep` 全代码无 Math23K/C3/ScienceQA 导入代码 |
| P1-2 | ✅ **RESOLVED** | **BKT 死代码** — 从未接入生产路径 | Phase 6 核心能力 (知识追踪) 实际未生效 | `grep BayesianKnowledgeTracing` 仅在 `adaptive_service.py` 内定义，无外部调用者 |
| P1-3 | ✅ **RESOLVED** | **SM-2 间隔复习不完整** — 仅在 mastery 转换时触发 | 练习过程中不更新复习时间，间隔复习形同虚设 | `practice_progress_integration.py` 不调用 `update_stability`/`compute_next_review` |
| P1-4 | ✅ **RESOLVED** | **无题目审核 API** | 非模板来源题目无法人工审核 | `review_status` 字段存在但无 approve/reject 端点 |
| P1-5 | **仅数学** — 语文/英语/科学无模板 | Phase 4 验收标准 "多学科差异化策略" 未满足 | `packages/domain/question_templates/` 仅 math_* 文件 |

### P2: 非核心能力缺失

| # | 缺陷 | 影响 | 证据 |
|---|------|------|------|
| P2-1 | 知识点覆盖率仅 0.56% | 大部分知识点无配套题目 | 20/3598 |
| P2-2 | Beijing topics.zh.json 缺 subject/ageRange | 需与上游合并才能获取完整元数据 | Python 分析: 0/1590 有 ageRange, 0/1590 有 subject |
| P2-3 | 推荐理由粒度粗 | 仅 low/medium/high_accuracy 三档 | `adaptive_service.py:359-364` |
| P2-4 | 无错题本/复练专区 | 错题复练仅靠随机排除，无专门流程 | 无 wrong_question/review 端点 |
| P2-5 | 无 LLM 出题 Layer 2 | 题目多样性受限 | 设计文档规划但未实现 |
| P2-6 | 开发数据库未迁移 | 本地 `numina.db` 停留在 `b4c8d3e9f2a3`，head 为 `ef001sm2fac` | `sqlite3` 查询无 learning 表 |
| P2-7 | ✅ **RESOLVED** | **XP/星星币虚假** | 练习完成显示 +10 XP/+10 星星币，但从未写入 DB | `practice.py:231-232` 返回硬编码值，无 `award_xp()` 或 `CoinTransaction` 调用 |
| P2-8 | ✅ **RESOLVED** | **RuleBased estimator 读取最旧 10 次** | 超过 10 次尝试后，掌握度估计冻结在旧数据 | `adaptive_service.py:77-80` `.order_by(asc).limit(10)` 应为 desc |
| P2-9 | **`update_sm2_after_session` 零调用者** | 练习后 SM-2 不更新，间隔复习失效 | `progress_service.py:160` 定义存在但无调用 |
| P2-10 | ✅ **RESOLVED** | **圆周率答案错误** | 题目说 "π 取 3.14" 但答案用 `math.pi` 计算，r=7 时答案 43.98 而非 43.96 | `math_geometry.py:93-103` |
| P2-11 | **`get_recommend_with_reason` 死代码** | 推荐原因可解释化已实现但无路由调用 | `adaptive_service.py:326-376` 定义存在，无 router 引用 |
| P2-12 | ✅ **RESOLVED** | **dedup_mapping.json 不存在** | mtc_/mt_ 重叠从未实际去重，3,598 知识点全部作为 active 入库 | seed 脚本支持但文件不存在 |
| P2-13 | ✅ **RESOLVED** | **session_mode 行为无差异** | diagnostic/review/challenge 模式被接受但选题逻辑完全忽略 | `select_questions()` 不读 session_mode |
| P2-14 | **无 session 恢复机制** | 中断的练习会话永久孤立，无法继续 | 无 resume 端点或 UI |
| P2-15 | ✅ **RESOLVED** | **application 题型答案不匹配** | 前端发送 `{value}` 后端期望 `{answer}`，application 题永远判错 | `PracticeAnswerInput.vue:108-117` vs `scoring_service.py:32-35` |
| P2-16 | ✅ **RESOLVED** | **浮点数精确匹配** | 计算题答案用 `==` 比较，`0.1+0.2` 类答案会判错 | `scoring_service.py:17` 无容差 |
| P2-17 | **Phase 0 报告审计范围不完整** | 报告仅审计上游 1,590 知识点，未覆盖 Beijing 2,008 mtc_ 知识点 | `phase0-data-quality-report.md` 无 mtc_ 提及 |
| P2-18 | **课程标准覆盖率未记录** | mt_ 仅 337/1,590 (21%) 有 cnStandards 映射，未在报告中体现 | Python 分析 |

---

## F. Phase 7 启动建议

### 必须先修复的阻塞项

1. **[P0-1] 修复 SM-2 测试** — 更新 4 个测试断言以匹配增强版 SM-2 公式（含 `ease_factor`）
2. **[P0-2] 自动化 seed 流程** — 部署时自动运行 `seed_learning_topics.py` + `seed_questions.py`
3. **[P1-2] BKT 接入** — `practice.py:151` 改用 `BayesianKnowledgeTracingEstimator`（或根据数据量自动切换）
4. **[P1-3] SM-2 全路径触发** — 每次 `submit_answer` 后调用 `update_stability` + `compute_next_review`
5. **[P2-7] XP/星星币持久化** — 练习完成后实际写入 `ChildLearningStats` 和 `CoinTransaction`
6. **[P2-8] 修复 RuleBased estimator 窗口** — `.order_by(desc).limit(10)` 获取最近 10 次而非最旧 10 次

### 可以与 Phase 7 并行处理

7. **[P1-1] 外部题库导入** — 建议优先评估 Math23K（中文数学应用题，与模板互补）
8. **[P1-4] 题目审核 API** — 需要支持未来 LLM 生成题目的人工审核
9. **[P1-5] 多学科模板** — 语文(拼音/识字)、英语(词汇/语法)、科学(概念推理)
10. **[P2-10] 修复圆周率答案** — 统一使用 3.14 或 math.pi
11. **[P2-12] 生成 dedup_mapping.json** — 运行去重生成器处理 mtc_/mt_ 重叠

### 可以纳入 Phase 7 的合理扩展

12. LLM 出题 Layer 2（设计文档已规划）
13. 错题本/复练专区
14. 更细粒度的推荐理由（激活 `get_recommend_with_reason` 端点）
15. 题目版权合规性文档化（对外部数据源）
16. session 恢复机制（中断的练习可继续）
17. 浮点数容差匹配（`scoring_service.py` 使用 `math.isclose`）

### 当前已经足够成熟、应该直接复用的能力

- ✅ 知识图谱数据（3,598 知识点 + 5,887 先修边）— 质量良好
- ✅ 4 表数据模型 — 设计合理、索引完备
- ✅ 24 个数学模板 — 参数化验证可靠
- ✅ 练习状态机 — 7 状态 + CAS + 完整转换验证
- ✅ 前端练习闭环 — 选题→作答→反馈→汇总
- ✅ 薄弱点识别 + 先修推荐
- ✅ 可解释进度 API
- ✅ QuestionKnowledgePoint 多对多关联

---

## G. 代码统计

| 维度 | 数量 |
|------|------|
| Epic 分支提交数 | 36 |
| 文件变更 | 94 |
| 新增代码行 | +16,885 / -86 |
| 后端新增 | 4 models, 6 services, 1 router, 1 seeder |
| 前端新增 | 1 API module, 1 page, 3 components, i18n |
| 测试文件 | 64 个 learning 相关 |
| 本次运行测试 | 132 passed / 4 failed |
| 题目模板 | 24 (math only) |
| 知识点覆盖 | 20/3,598 (0.56%) |

---

## H. 方法论说明

本审计采用以下方法：

1. **读取全部 8 个 GitHub Issue** (#121-#128) 的原始需求、checklist、讨论记录
2. **代码静态分析** — 读取所有关键实现文件，追踪调用链
3. **测试执行** — `uv run pytest` 执行 132 个相关测试
4. **数据验证** — 分析 JSON 数据文件结构、字段完整性、交叉引用
5. **dry-run 验证** — 运行 seed 脚本验证数据流完整性
6. **许可证审查** — 确认 os-taxonomy-beijing CC-BY-SA 4.0 许可

**未执行的部分**（受限于只读审计约束）：
- 未启动服务器进行真实 E2E 测试
- 未调用外部 LLM API 验证出题质量
- 未对 Math23K 等候选开源题库做深入内容评估
