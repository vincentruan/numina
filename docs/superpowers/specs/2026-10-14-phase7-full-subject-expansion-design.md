# Phase 7: 全学科扩展与持续优化 — 设计文档

**日期：** 2026-10-14
**Issue:** #129
**Epic:** #121
**状态：** 设计中（待实施）

---

## 1. 背景与目标

### 1.1 Phase 0-6 现状

Phase 0-6 建立了完整的知识图谱集成、标准化题库基础、自适应练习闭环、AI 辅导和家长管理能力。经独立审计，整体 CONDITIONAL PASS，所有 P0/P1 阻塞项已修复，141+ 学习测试全部通过。

**已完成的关键能力：**

- 知识图谱：3,598 topics（1,590 上游 + 2,008 北京特定），5,840+ dependencies，183 clusters，valid DAG
- 数据库 Schema：15+ 学习相关表，6 次 alembic 迁移
- 自适应引擎：BKT + RuleBased 掌握度估计，SM-2 间隔复习，3 种 session 模式
- 练习闭环：选题 → 作答 → 评分 → 进度更新 → XP/金币 → 状态转换
- 题目模板引擎：25 个程序化数学模板，装饰器注册机制
- 前端：儿童端 + 家长端完整页面
- 测试套件：141+ 学习相关测试全部通过

**关键缺口：**

- 知识点覆盖率仅 0.56%（25 个 topic_key / 3,598 topics）
- 仅数学有题目模板（语文、英语、科学均为 0）
- 无外部题库导入（Phase 3 遗留 P1-1）
- 无 LLM 辅助出题
- 无开放式题目评分
- Bloom 层次几乎全部 "apply"，缺少 analyze/evaluate/create
- BKT 无遗忘模型
- 北京 topic 缺少 subject/ageRange 字段（P2-2 遗留）

### 1.2 Phase 7 核心目标

在已有题库和自适应练习能力上，形成真正能够持续扩展的全学科儿童学习系统。

### 1.3 设计决策汇总

经过 Brainstorming 澄清，确认以下战略决策：

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 核心策略 | 评价体系先行 | 用数据驱动学科扩展优先级，避免盲目建设 |
| 缺口填补方式 | 混合模式（按题型自动路由） | 不同题型适合不同生成方式，单一方式无法覆盖全学科 |
| 评价体系消费者 | 内部工具 + 家长可见 | 内部驱动内容建设，家长可见增强信任 |
| 审核资源 | 仅开发者本人 | 必须风险分级 + 自动化验证为主，否则审核积压成为瓶颈 |
| 学科扩展顺序 | 数学先行验证流水线 | 风险最低，在熟悉领域验证完整流程后再复制 |

---

## 2. 总体架构

### 2.1 架构分层

Phase 7 在现有系统之上增量扩展三个新层次，不推翻任何已有实现：

```
现有层（Phase 2-6，保持不变）
├── 题库存储: Question / QuestionKnowledgePoint / review_status
├── 练习闭环: PracticeSession → scoring → progress → BKT/SM-2
├── 自适应选题: adaptive_service (mastery → difficulty → selection)
└── 前后端: practice.py / learning*.py 路由 + 儿童端/家长端页面

Phase 7 新增层
├── ① 评价层（P7a 先建）
│   ├── coverage_service — 真实覆盖率评价（升级现有 get_coverage_stats）
│   ├── quality_service — 题目质量评价（程序化验证 + AI 交叉验证 + 风险分级）
│   └── learning_effect_service — 学习效果指标（规则化指标先行）
├── ② 生产层（P7a 后期 ~ P7b）
│   ├── question_router — 出题策略路由器（按题型/学科自动选生成方式）
│   ├── external_import — 外部题库导入适配器（格式转换 + 版权标记 + 质量门）
│   └── llm_generator — LLM 出题管道（草稿 → 程序化验证 → AI 交叉验证 → 风险分级 → 人工抽检）
└── ③ 展示层（P7c）
    ├── 内部: 覆盖率/质量仪表盘（脚本 + API，不建重前端）
    └── 家长可见: 学习效果指标卡片（复用 family/learning 现有页面扩展）
```

### 2.2 学科扩展策略

扩展单位不是「学科」，而是「知识点簇」。3,598 topics 分布在各学科，一次扩展一个学科的某个 domain，每次扩展都走完整流水线：路由 → 生成 → 验证 → 入库 → 覆盖率报告更新。

**数学纵深的第一轮范围：**

| 数学领域 | 现有模板 | 适合生成方式 | 第一轮动作 |
|---------|---------|-------------|-----------|
| 数与运算 | 9 个（算术）+ 5 个（分数） | 程序化模板 | 扩展：小数运算、估算、简便运算 |
| 数量关系/应用题 | 5 个 | 程序化为主，部分 LLM | 扩展：百分数、比例应用、工程问题变式 |
| 图形与几何 | 5 个 | 程序化 + 文字描述图形 | 扩展：体积、角度分类、对称 |
| 测量 | 0 | 程序化模板 | 新增：单位换算、周长面积实测应用 |
| 统计与概率 | 0 | 程序化（数据表文字化） | 新增：平均数、可能性的文字化数据题 |
| 数学推理 | 0 | LLM 生成 + 人工抽检 | 新增：找规律、简单逻辑推理（Bloom: analyze） |

**其他学科的第一轮只做「试点簇」：**

| 学科 | 试点簇 | 主要生成方式 |
|------|--------|-------------|
| 语文 | 汉语拼音 + 识字 | 程序化模板为主 |
| 英语 | 基础词汇 + 简单语法 | 程序化模板 + 外部导入 |
| 科学 | 生命科学事实 + 物质科学事实 | 程序化模板 + LLM |

### 2.3 评分体系扩展

现有 `scoring_service` 支持 5 种结构化题型。Phase 7 新增：

- **`multi_fill_blank`**：多空填空，多个空逐一匹配（统计题、单位换算需要）
- **`ai_graded`**：AI 辅助评分，评分时附带置信度。**置信度低于阈值的题目不进入掌握度计算**，只给反馈不计分——防止 AI 判分过度自信直接影响掌握度

---

## 3. 模块 2：题目生产与审核流水线

### 3.1 出题策略路由器（`question_router`）

路由器是整个生产层的入口。每个「待生产」知识点进来后，路由器决定用哪种生成方式。

**路由决策矩阵：**

| 题目特征 | 生成方式 | 质量门 | 审核策略 |
|---------|---------|-------|---------|
| 有确定答案 + 可参数化（计算/换算/填空） | 程序化模板 | 答案正确性验证（自动） | 无需审核，直接 approved |
| 客观题 + 不可参数化（知识记忆/阅读理解选择） | 外部题库导入 | 格式校验 + 答案交叉验证 | 导入时自动抽样 5% 人工抽检 |
| 结构化推理（找规律/简单推理，答案可验证） | LLM 生成 | 答案正确性验证 + AI 交叉评分 | 风险分级：低风险自动批准，高风险进审核队列 |
| 开放表达（句子/作文/实验设计） | LLM 生成 + 人工 | 格式 + 内容安全 + 学科合理性 | 全部进审核队列 |

**路由输入：** `topic_id` + `required_question_count` + `target_difficulty_range` + `target_bloom_levels`

**路由输出：** 生成任务列表（哪个 topic 用哪种方式生成多少题），以及预期质量分数

**实现：** 在 `question_templates/registry.py` 现有注册机制上扩展。新增 `routing_rules` 配置表，每个 topic/domain 绑定默认生成策略。第一阶段用显式配置表，不做智能路由。

### 3.2 外部题库导入适配器（`external_import`）

**适配器接口：**

```python
class ImportAdapter(Protocol):
    def detect_format(self, raw_data) -> bool: ...
    def parse(self, raw_data) -> Iterator[ImportedQuestion]: ...
    def validate(self, question: ImportedQuestion) -> list[ValidationError]: ...
```

Phase 7 第一轮建 2 个适配器：
- **Math23K 适配器**（MIT 许可，~23K 小学-初中数学应用题，JSON 格式）
- **自建 JSON 格式**（未来人工添加或 LLM 批量导出的标准格式）

**导入流水线：**

```
原始文件 → 适配器检测格式 → parse → validate（格式 + topic_key 映射）
  → 去重（复用现有 content_hash）→ 质量评分（质量评价最小集）
  → 抽样人工审核（5% 置信区间 ±5%）→ 批量入库
```

**关键字段：** `source="external"` + `source_name="math23k"` + `source_license="MIT"` + `imported_at`。所有外部题目初始 `review_status="pending"`，抽样通过后批量改为 `"approved"`。

### 3.3 LLM 出题管道（`llm_generator`）

**核心原则：** LLM 生成题目草稿，但草稿不直接进题库。必须经过三层验证才能入库。

**管道流程：**

```
LLM 生成 prompt → 草稿输出（JSON）
  → 第一层：格式校验（stem 非空、answer 格式正确、topic_key 存在）
  → 第二层：答案正确性验证（能自动验证的：计算题重新算、选择题验证选项互斥）
  → 第三层：AI 交叉验证（用另一个 prompt/模型评阅该题的合理性）
  → 风险分级 → 路由到审核策略
```

**Prompt 设计关键约束：**
- Prompt 中必须包含目标 `topic_key` 的名称和描述（从 LearningTopic 查询），不允许 LLM 自行选择知识点
- 输出必须包含 `topic_key`，服务端校验该 key 与输入一致（防止 LLM 杜撰知识点，复用 finance-coach-target-id-hallucination 的白名单防御经验）
- 输出格式严格 JSON Schema，使用 structured output
- 单次调用生成 1 题（不批量生成——质量会雪崩式下降）

**风险分级规则：**

| 条件 | 风险等级 | 处理 |
|------|---------|------|
| 通过三层验证 + 属于客观题类型（choice/fill_blank/calculation） | 低 | 自动 approved |
| 通过三层验证 + 属于推理/理解题（Bloom: analyze/evaluate） | 中 | 进入审核队列，标记 `review_priority=medium` |
| 未通过第二层或第三层 | 高 | 进入审核队列，标记 `review_priority=high`，附上具体验证失败原因 |
| 任何 AI 评分置信度 < 0.7 | 高 | 同上 |

### 3.4 审核工作流（面向单人审核者的设计）

**预期审核负载（以数学纵深为例）：**

假设一周生产 200 道新题：
- 程序化模板：150 道 → 无需审核（自动验证答案）
- 外部导入：30 道 → 抽样 5% = 1-2 道人工审核
- LLM 生成：20 道 → 高风险约 5-8 道需要审核

**实际审核负载：每周 ~10 道题。**

**审核队列中的题目附带信息（降低审核成本）：**
- 题目内容 + 答案 + 解析
- 自动生成验证结果（答案正确性、AI 交叉评分、内容安全）
- 风险等级和具体原因（不通过哪一层、什么错误）
- 相似题目列表（检查是否高度重复）

### 3.5 与现有系统的集成

| 现有模块 | 集成方式 |
|---------|---------|
| `question_templates/registry.py` | 扩展：新增 `generate_batch()` 方法；新增 `QuestionGenerator` 接口，让 LLM generator 也实现同一接口 |
| `question_seeder.py` | 扩展：新增 `seed_from_external()` 和 `seed_from_llm()` 方法 |
| `question_service.py` | 扩展：`create_question()` 新增 `source_metadata` 参数 |
| `content_safety_filter.py` | 复用：作为 LLM 管道第一层验证 |
| 现有 `review_status` 机制 | 完全复用：pending/approved/rejected 三态不变 |
| 现有 `review` API | 扩展：新增 `batch-review` 端点 |

---

## 4. 模块 3：知识点覆盖评价

### 4.1 设计目标

从「有没有题目」的简单计数，升级为能指导内容建设决策的多维覆盖评价。核心原则：真实覆盖率 ≠ 题目数量。

### 4.2 覆盖率评价模型

每个知识点的覆盖得分由五个维度加权组成：

| 维度 | 权重 | 含义 | 计算方式 |
|------|------|------|---------|
| 存在性 | 30% | 该 topic 是否有 ≥1 道 approved 题目 | 0/1 二值 |
| 难度层次 | 20% | 题目是否覆盖多个难度等级 | 实际难度去重数 / 目标难度数（默认 3 档） |
| 题型多样性 | 15% | 是否有多种题型 | 实际题型数 / 该学科合理题型上限 |
| Bloom 层次 | 20% | 是否覆盖 remember → apply → analyze | 实际 Bloom 层数 / 4 |
| 先修价值 | 15% | 该 topic 是否是其他高价值 topic 的前置条件 | 该 topic 的 dependent 数量（归一化到 0-1） |

**覆盖得分公式：**

```
coverage_score = 0.30 × existence + 0.20 × difficulty + 0.15 × diversity + 0.20 × bloom + 0.15 × prerequisite_value
```

得分范围 0.0 ~ 1.0。

### 4.3 聚合层级

| 层级 | 聚合方式 | 服务场景 |
|------|---------|---------|
| Level 1: 知识点级 | 每个 LearningTopic 一个 coverage_score | 指导出题路由器 |
| Level 2: 领域级 | 每个 domain 加权平均分 | 学科内横向比较 |
| Level 3: 学科级 | 每个 subject 整体覆盖率 | 学科间比较和优先级排序 |

### 4.4 学科差异化参数

不同学科的「理想覆盖」定义不同：

```python
SUBJECT_EXPECTATIONS = {
    "mathematics": {
        "target_bloom_levels": ["remember", "understand", "apply", "analyze"],
        "target_difficulty_tiers": 3,
        "target_question_types": ["calculation", "fill_blank", "multiple_choice", "application"],
        "min_questions_per_topic": 5,
    },
    "chinese": {
        "target_bloom_levels": ["remember", "understand", "apply"],
        "target_difficulty_tiers": 3,
        "target_question_types": ["multiple_choice", "fill_blank", "application"],
        "min_questions_per_topic": 3,
    },
    "english": {
        "target_bloom_levels": ["remember", "understand", "apply"],
        "target_difficulty_tiers": 3,
        "target_question_types": ["multiple_choice", "fill_blank", "application"],
        "min_questions_per_topic": 3,
    },
    "science": {
        "target_bloom_levels": ["remember", "understand", "apply", "analyze"],
        "target_difficulty_tiers": 3,
        "target_question_types": ["multiple_choice", "fill_blank", "application"],
        "min_questions_per_topic": 4,
    },
}
```

没有配置 subject_expectations 的学科不参与覆盖率评价。

### 4.5 去重与有效性

- **有效题目定义：** 内容哈希去重后，review_status = approved，topic_id 有效
- **程序化模板变体：** 来自同一 template 的不同参数题目视为同一题型的一个有效变体，每个变体单独计数
- **LLM 生成题目：** 用 AI 交叉验证时同时检测与已有题目的相似度
- **务实折中：** 不做复杂语义相似度计算，靠 Bloom/难度/题型维度间接约束同质化

### 4.6 产出形式

**API 端点（内部使用）：**

```
GET /practice/coverage/detailed
  → 每个 topic 的 coverage_score + 各维度明细
  → 支持过滤：subject, domain, age_group, score_range
  → 支持排序：按 coverage_score 升序

GET /practice/coverage/summary
  → 学科级 + 领域级聚合分数
  → 每个学科的 topic 覆盖率

GET /practice/coverage/gap-report
  → 覆盖缺口清单：score < 阈值的 topic
  → 按先修价值排序
  → 附带推荐生成方式
```

**脚本工具：**

```bash
python -m server.scripts.coverage_report --subject mathematics --format table
python -m server.scripts.coverage_report --gap-only --output gaps.json
python -m server.scripts.coverage_report --diff <previous_report.json>
```

### 4.7 与现有系统的集成

| 现有模块 | 集成方式 |
|---------|---------|
| `question_service.get_coverage_stats()` | 升级：扩展为返回 coverage_score 多维数据，API 兼容 |
| `LearningTopic` 模型 | 不修改：所有维度从已有字段和 Question 表聚合计算 |
| `LearningDependency` | 用于先修价值维度计算 |
| `LearningCluster` | 用于领域级聚合 |

**计算时机：** 每次生成/导入题目后触发异步计算并缓存。新增 `coverage_cache` 表。全量重算通过脚本手动触发。

---

## 5. 模块 4：题目质量评价

### 5.1 设计目标

让题库质量变得可观察、可衡量、可持续改进。80%+ 的质量判定必须自动化，人工只介入自动化无法判断的边界情况。

### 5.2 质量维度模型

| 维度 | 权重 | 自动化程度 | 评估方式 |
|------|------|-----------|---------|
| 答案正确性 | 30% | 完全自动 | 计算题重新计算；选择/判断题格式校验 + AI 交叉 |
| 知识点匹配 | 20% | 完全自动 | 题目 stem 与 topic 名称/描述的语义一致性（LLM 判断） |
| 题干清晰度 | 15% | 半自动 | 规则检查 + AI 抽样评估 |
| 干扰项质量 | 10% | 半自动 | 选择题选项互斥性检查 + 区分度 |
| 年龄适配 | 10% | 完全自动 | 词汇复杂度对比 age_group |
| 去重性 | 10% | 完全自动 | 内容哈希 + 同源模板变体计数 |
| 教育价值 | 5% | 纯人工 | 抽样评估，领域级平均分 |

**质量得分公式：**

```
quality_score = 0.30 × correctness + 0.20 × topic_match + 0.15 × clarity
              + 0.10 × distractor + 0.10 × age_fit + 0.10 × uniqueness + 0.05 × educational_value
```

得分范围 0.0 ~ 1.0。

### 5.3 各维度具体实现

#### 5.3.1 答案正确性（30%，全自动）

按题目类型的验证策略：

| 题型 | 验证方式 |
|------|---------|
| calculation | 用 Python eval() 重新计算，与 answer 比对（容差 1e-4） |
| fill_blank | 字符串精确匹配 |
| multiple_choice | 检查 answer 是否在 options key 中 + 选项唯一性 |
| true_false | answer 必须在 [true, false] 中 |
| application | answer 必须在 acceptable 列表中 |
| ai_graded | 由 AI 交叉验证完成，输出置信度 |

- 模板生成题目：正确性维度直接给 1.0（生成时自带 verify）
- LLM 生成题目：提取 stem 中的数值和运算关系，用代码重新求解
- 外部导入题目：无法自动验证，正确性维度 = 0.5（中性）

#### 5.3.2 知识点匹配（20%，全自动）

轻量级 LLM 调用：

```
Prompt: "以下题目是否测量了知识点「{topic.name}」？
题目：{question.stem}
答案：{question.answer}
请判断：1.完全匹配 2.部分相关 3.不匹配
只输出数字。"
```

- 输出 1 → 1.0，输出 2 → 0.5，输出 3 → 0.0
- 模板生成题目跳过此验证（直接 1.0）
- 仅对 LLM 生成和外部导入题目执行

#### 5.3.3 题干清晰度（15%，半自动）

自动规则检查（扣分项）：

| 规则 | 触发条件 | 扣分 |
|------|---------|------|
| 过短 | stem 长度 < 10 字符 | -0.3 |
| 含占位符 | 包含 `{` `}` `xxx` `TODO` | -0.5 |
| 含乱码 | 非中英文字符占比 > 30% | -0.5 |
| 无正确结尾 | 不以 `?` `.` `？` `。` `：` 结尾 | -0.1 |
| 含 HTML/Markdown | 包含 `<` `>` `#` `*` 等非内容标记 | -0.2 |

#### 5.3.4 干扰项质量（10%，半自动）

仅适用于 multiple_choice：

- 选项数量 ≥ 3 → 否则 -0.5
- 所有选项互不相同 → 否则 -1.0
- 正确答案不在错误选项中 → 否则 -1.0
- 选项长度差异过大（最长/最短 > 3 倍） → -0.2
- LLM 生成题目额外用 LLM 判断干扰项合理性

#### 5.3.5 年龄适配（10%，全自动）

字频统计法：统计 stem 中非常用汉字（不在 GB2312 一级字库内的字符）的占比。

| age_group | 非常用字占比阈值 | 得分 |
|-----------|----------------|------|
| early (≤7) | ≤ 2% → 1.0, ≤ 5% → 0.5, > 5% → 0.0 |
| lower (8-10) | ≤ 5% → 1.0, ≤ 10% → 0.5, > 10% → 0.0 |
| mid (11-13) | ≤ 10% → 1.0, ≤ 20% → 0.5, > 20% → 0.0 |
| high (14+) | ≤ 20% → 1.0, ≤ 30% → 0.5, > 30% → 0.0 |

#### 5.3.6 去重性（10%，全自动）

- content_hash 在整个题库中唯一 → 1.0
- 同 topic 下有相同 content_hash → 0.0
- 同 topic + 同源模板 + 同 difficulty 的不同变体 → 0.5

#### 5.3.7 教育价值（5%，纯人工）

每领域随机抽取 5 道题人工判断，领域整体教育价值得分 = 抽样平均分。该领域下所有题目使用该领域平均分。

### 5.4 质量评价触发时机

| 事件 | 触发动作 |
|------|---------|
| 题目创建/导入 | 立即计算全维度质量分 |
| 题目被人工审核 | 更新相关维度 |
| 题目作答 N 次后 | 根据作答数据更新干扰项质量和年龄适配 |
| 全量重算 | 脚本手动触发 |

新增 `question_quality` 缓存表。

### 5.5 质量阈值与动作

| quality_score | 状态 | 动作 |
|---------------|------|------|
| ≥ 0.8 | 优秀 | 正常参与选题 |
| 0.6 ~ 0.8 | 合格 | 正常参与选题，标记需持续观察 |
| 0.4 ~ 0.6 | 待改进 | 降低选题权重 |
| < 0.4 | 不合格 | 自动隔离：review_status 改为 "suspended" |

### 5.6 与现有系统的集成

| 现有模块 | 集成方式 |
|---------|---------|
| `validate_question()` | 复用：作为前置格式校验 |
| `scoring_service.py` | 复用：计算题正确性验证 |
| `content_safety_filter.py` | 复用：LLM 题目前置安全检查 |
| 现有 `review_status` | 扩展：新增 `"suspended"` 状态 |
| `question_router` | 集成：质量评价结果反馈给路由器 |
| `coverage_service` | 集成：低质量题目（< 0.4）不计入有效覆盖 |

---

## 6. 模块 5：学习效果评价

### 6.1 设计目标

评估系统是否真正帮助儿童学习。从规则化指标先行，逐步引入更复杂的分析方法。

核心原则：
1. 不声称能准确衡量长期学习效果
2. 内部指标 + 家长可见指标是两套东西
3. 掌握度 ≠ 能力

### 6.2 三层渐进式评估框架

| 层级 | 方法 | 数据需求 | 适用阶段 |
|------|------|---------|---------|
| L1: 规则化指标 | 基于作答记录的直接统计 | 极少 | Phase 7 第一版 |
| L2: 离线验证 | 回顾性分析 | 中等 | 数据积累后（3-6 月） |
| L3: 在线评估 | 实时模型校准 | 大量 | 远期目标 |

Phase 7 只实现 L1，设计好 L2 的数据接口预留。

### 6.3 L1 规则化指标

#### 6.3.1 掌握度估计可靠性

| 指标名 | 计算方式 | 健康范围 | 异常含义 |
|--------|---------|---------|---------|
| 掌握度-正确率偏差 | abs(mastery_score - 最近10次正确率) | < 0.15 | 偏差大说明估计不准 |
| 掌握度波动率 | std(mastery_score 在连续 session 中的变化) | < 0.1 | 波动大说明估计不稳定 |
| 低信心估计占比 | mastery_score 基于 < 5 次作答的 topic 数 / 总 topic 数 | < 30% | 过高说明数据不足 |

**掌握度虚高/虚低检测：**

```python
def detect_mastery_anomaly(child_id, topic_id):
    mastery = get_bkt_mastery(child_id, topic_id)
    recent_accuracy = compute_recent_accuracy(child_id, topic_id, n=10)
    
    if mastery > 0.8 and recent_accuracy < 0.5:
        return "mastery_inflated"
    if mastery < 0.3 and recent_accuracy > 0.7:
        return "mastery_deflated"
    return "normal"
```

异常状态下：掌握度显示为 `confidence=low`，不参与推荐算法决策。

#### 6.3.2 推荐有效性

| 指标名 | 计算方式 | 健康范围 |
|--------|---------|---------|
| 推荐命中率 | 推荐 topic 中 child 实际练习的 / 总推荐数 | > 50% |
| 推荐难度匹配度 | 推荐题目难度与 child mastery 的匹配 | 应在 growth zone |
| 推荐后正确率 | child 练习推荐 topic 后的平均正确率 | 0.5 ~ 0.8 |

#### 6.3.3 错题复练效果

| 指标名 | 计算方式 | 健康范围 |
|--------|---------|---------|
| 复练改善率 | (复练后正确率 - 复练前正确率) / 复练前正确率 | > 0 |
| 复练间隔 | 错题到复练的天数 | 1-7 天 |
| 复练后再次出错率 | 复练后同知识点再次出错的比例 | < 30% |

实现：在 PracticeAttempt 上标记 `is_retry=True`。

#### 6.3.4 无效刷题检测

| 模式 | 检测条件 | 标记 |
|------|---------|------|
| 快速刷正确 | 单 session > 20 题 + 平均 time_spent < 5 秒 | rapid_fire |
| 重复刷已掌握 | 对 mastery > 0.9 的 topic 反复练习 | over_practice |
| 跳题模式 | 连续 5 题 time_spent < 3 秒 | skipping |

检测到无效刷题：该 session 数据不计入掌握度计算，家长端提示异常。

#### 6.3.5 长期薄弱知识点识别

```python
def identify_chronic_weaknesses(child_id):
    for topic_id in get_all_attempted_topics(child_id):
        accuracy_over_time = compute_accuracy_by_session(attempts)
        if len(accuracy_over_time) < 3:
            continue
        last_3 = accuracy_over_time[-3:]
        if all(acc < 0.6 for acc in last_3):
            chronic.append({
                "topic_id": topic_id,
                "avg_accuracy": mean(last_3),
                "sessions_struggling": len(accuracy_over_time),
                "trend": "stable_low" if std(last_3) < 0.1 else "declining",
            })
    return sorted(chronic, key=lambda x: x["avg_accuracy"])
```

#### 6.3.6 学习前后能力变化

不做前测-后测实验设计，改用时间段对比：对比「上周」vs「本周」的平均 mastery_score 变化、新掌握 topic 数量、薄弱 topic 数量变化。

### 6.4 家长可见的学习效果指标

**设计原则：** 家长看到的不是原始数据，而是可理解的、可行动的信息。

| 指标 | 家长看到的 | 底层数据 |
|------|-----------|---------|
| 学科掌握概览 | 每个学科的进度条（已掌握/学习中/未开始） | LearningProgress 状态统计 |
| 本周学习亮点 | 「本周新掌握了 3 个知识点」「连续学习 5 天」 | ChildLearningStats |
| 薄弱环节 | 「分数运算需要更多练习」 | 掌握度 < 0.5 的 topic 中 accuracy 最低的 |
| 学习趋势 | 折线图：过去 4 周该学科平均正确率 | 按周聚合的 PracticeAttempt 统计 |
| 学习建议 | 「建议今天复习分数减法」 | zone_service 推荐 + 间隔复习到期 topic |

**明确不给家长看的：** mastery_score 具体数值、BKT 参数、无效刷题检测规则、题目质量分数。

**展示形式：** 扩展现有 `GET /api/v1/family/learning/children/{id}/progress` 端点：

```json
{
    "learning_effect_summary": {
        "subject_overview": [
            {"subject": "mathematics", "mastered": 8, "learning": 5, "locked": 680, "mastery_rate": 0.012}
        ],
        "weekly_highlights": [
            {"type": "new_mastery", "topic_name": "长方形面积", "count": 3},
            {"type": "streak", "days": 5}
        ],
        "weak_areas": [
            {"topic_name": "同分母分数加法", "accuracy": 0.35, "recommendation": "review"}
        ],
        "trend": {
            "period": "4weeks",
            "mathematics_accuracy": [0.45, 0.52, 0.58, 0.63],
            "direction": "improving"
        },
        "recommendations": [
            "建议今天复习：分数减法",
            "可以尝试挑战：长方形周长"
        ]
    }
}
```

### 6.5 不同学科的评价差异

Phase 7 第一版的务实选择：学习效果指标对所有学科统一使用正确率 + mastery 变化作为核心衡量。学科差异通过 SUBJECT_EXPECTATIONS 间接处理。

### 6.6 与现有系统的集成

| 现有模块 | 集成方式 |
|---------|---------|
| `adaptive_service.py` (BKT) | 读取 mastery_score；异常检测覆盖其输出 |
| `scoring_service.py` | 读取 session score |
| `practice_progress_integration.py` | 读取 state machine 状态 |
| `stats_service.py` | 复用 XP/level/streak 数据 |
| `zone_service.py` | 复用 zone 检测结果 |
| `PracticeAttempt` 模型 | 新增字段：`is_retry` (bool) |
| `PracticeSession` 模型 | 新增字段：`validity_flag` |

---

## 7. 模块 6：持续优化机制

### 7.1 优化闭环总览

```
① 发现缺口 → ② 安排生产 → ③ 验证入库 → ④ 重新评价
    ↑                                          │
    └──────────────────────────────────────────┘

⑤ 作答反馈 → ⑥ 难度校准 → ⑦ 质量监控 → ⑧ 题目隔离
    ↑                                          │
    └──────────────────────────────────────────┘
```

### 7.2 自动发现缺口

```python
def discover_gaps(min_score_threshold=0.3):
    gaps = []
    for topic in get_all_active_topics():
        score = get_coverage_score(topic.id)
        if score < min_score_threshold:
            gaps.append({
                "topic_id": topic.id,
                "current_score": score,
                "prerequisite_value": count_dependents(topic.id),
                "subject": topic.subject,
                "domain": topic.domain,
            })
    return sorted(gaps, key=lambda x: -x["prerequisite_value"])
```

### 7.3 自动安排生产

```python
def generate_production_plan(gaps, weekly_capacity=200):
    plan = []
    remaining = weekly_capacity
    for gap in gaps:
        if remaining <= 0:
            break
        topic = get_topic(gap["topic_id"])
        routing = question_router.route(topic)
        count = min(5, routing.recommended_count, remaining)
        plan.append({
            "topic_id": topic.id,
            "method": routing.method,
            "count": count,
            "target_difficulty": routing.target_difficulty,
            "target_bloom": routing.target_bloom,
        })
        remaining -= count
    return plan
```

### 7.4 难度校准

```python
def calibrate_difficulty(question_id):
    attempts = get_attempts_for_question(question_id)
    if len(attempts) < 10:
        return None
    actual = 1.0 - (sum(a.is_correct for a in attempts) / len(attempts))
    declared = question.difficulty / 5.0
    deviation = abs(actual - declared)
    if deviation > 0.3:
        return {"action": "flag_for_review"}
    elif deviation > 0.2:
        return {"action": "auto_adjust"}
    return None
```

校准策略：
- 偏差 ≤ 0.2：不处理
- 偏差 0.2-0.3：自动微调 Question.difficulty
- 偏差 > 0.3：标记 needs_review=True，进入审核队列

触发时机：每积累 50 条新 attempt 后触发。

### 7.5 质量监控 → 题目隔离

| 监控维度 | 触发条件 | 动作 |
|---------|---------|------|
| 正确率异常 | 某题正确率 < 0.1 或 > 0.99 | 标记 suspicious=True |
| 作答时间异常 | 平均 time_spent < 3 秒 | 标记 suspicious=True |
| 质量分衰减 | 新质量分 < 原质量分 × 0.7 | 触发质量复核 |
| 争议答案 | AI 交叉验证与标准答案不一致 | 标记 answer_disputed=True |

suspended 题目不参与任何选题。

### 7.6 知识点映射优化

LLM 生成题目入库时检查 topic_key 语义匹配度。每季度批量扫描一次 LLM 题目的映射质量。

### 7.7 学习路径优化建议

基于儿童实际表现建议路径调整：
- 已掌握（mastery > 0.8）的 topic → 建议跳过
- 连续 3 次正确率 < 0.4 的 topic → 建议回退到前置知识点

家长手动决定是否调整。

### 7.8 自动化调度

| 任务 | 触发方式 | 频率 |
|------|---------|------|
| 覆盖率重算 | 每次生产批次完成后 | 事件驱动 |
| 质量分重算 | 脚本手动触发 | 每月一次 |
| 难度校准 | attempt 累计 50 条后 | 事件驱动 |
| 缺口发现 + 生产计划 | 脚本手动触发 | 每周一次 |
| 异常监控扫描 | 脚本手动触发 | 每天一次 |

统一入口：`python -m server.scripts.optimization_loop`

### 7.9 与现有系统的集成

| 现有模块 | 集成方式 |
|---------|---------|
| `coverage_service` | 缺口发现输入 |
| `quality_service` | 质量监控基线 |
| `learning_effect_service` | 学习效果数据反馈 |
| `question_router` | 执行生产计划 |
| `adaptive_service.select_questions()` | 排除 suspicious 和 suspended 题目 |
| `Question` 模型 | 新增：`suspicious`, `needs_review`, `empirical_difficulty` |

---

## 8. 模块 7：用户体验

### 8.1 总体原则

Phase 7 前端工作量刻意最小化。核心逻辑在 API 层和脚本层。

### 8.2 内部工具

**覆盖率报告脚本：**

```bash
python -m server.scripts.coverage_report --subject mathematics --format table
python -m server.scripts.coverage_report --gap-only --output gaps.json
python -m server.scripts.coverage_report --quality --subject mathematics
```

**优化循环脚本：**

```bash
python -m server.scripts.optimization_loop discover-gaps --threshold 0.3
python -m server.scripts.optimization_loop generate-plan --capacity 200
python -m server.scripts.optimization_loop calibrate-difficulty
python -m server.scripts.optimization_loop anomaly-scan
```

**题目生产脚本：**

```bash
python -m server.scripts.production_run --plan plan.json
```

**API 端点（挂现有 /api/v1/practice 路由）：**

```
GET /practice/coverage/summary
GET /practice/coverage/detailed
GET /practice/coverage/gap-report
GET /practice/coverage/trend
GET /practice/quality/distribution
GET /practice/quality/flagged
GET /practice/quality/calibration
GET /practice/learning-effect/summary
GET /practice/learning-effect/weaknesses
GET /practice/learning-effect/recommendations
GET /practice/questions/review-queue
POST /practice/questions/batch-review
GET /practice/questions/usage-stats
GET /practice/questions/{id}/grading-explanation
```

### 8.3 家长可见

**扩展现有页面（不新建）：**

| 现有页面 | 扩展内容 |
|---------|---------|
| `BabyLearningPage.vue` | 新增 LearningEffectCard：学科掌握进度条 + 本周亮点 + 薄弱环节 |
| `ChildLearningMapPage.vue` | 薄弱知识点橙红色高亮 |
| `LearningReviewsPage.vue` | 新增题目审核 tab + 批量操作 |

**新增前端组件：**

| 组件 | 技术 | 说明 |
|------|------|------|
| `LearningEffectCard.vue` | Vue 3 + Vant 4 | 学习效果概览卡片 |
| `LearningTrendChart.vue` | ECharts 折线图 | 4-12 周正确率趋势 |
| `GradingExplanationPanel.vue` | Vue 3 + Vant 4 | AI 判分可解释性面板（置信度 + 维度拆解 + 推理摘要） |
| `CoverageTrendChart.vue` | ECharts 折线图 | 覆盖率随时间变化趋势 |

**儿童端唯一改动：** `PracticeAnswerInput.vue` 扩展支持 `multi_fill_blank`（多个输入框）和 `ai_graded`（文本输入 + AI 评分中过渡状态）。

### 8.4 审核队列界面

双 tab 结构：[掌握度审核] | [题目审核]

题目审核 tab 关键交互：
- 按风险等级筛选
- 「批量通过全部低风险」按钮
- 每道题显示：内容 + 答案 + 验证结果 + 风险原因 + 相似题目
- 操作：通过 / 拒绝（附原因）/ 跳过

---

## 9. 分阶段实施计划

### 9.1 总览

```
P7a 评价基础设施 ──→ P7b 数学纵深+出题流水线 ──→ P7c 学习效果+家长可见
                                                        │
                       P7e 持续优化闭环 ←── P7d 学科扩展试点
```

### 9.2 P7a：评价基础设施

**目标：** 覆盖率评价 + 质量评价最小可用集 + 使用频率追踪 + 覆盖率趋势快照。

**交付物：**

| 编号 | 交付物 |
|------|--------|
| P7a-1 | `coverage_service.py`：五维覆盖得分 + 三级聚合 |
| P7a-2 | `quality_service.py`：七维质量得分 + 分题型验证 |
| P7a-3 | `coverage_cache` 表（alembic 迁移） |
| P7a-4 | `question_quality` 表（alembic 迁移） |
| P7a-5 | 覆盖率 + 质量 API 端点（7 个：含 coverage/trend） |
| P7a-6 | `coverage_report` CLI 脚本 |
| P7a-7 | `SUBJECT_EXPECTATIONS` 配置 |
| P7a-8 | P2-2 前置修复：北京 topic subject/ageRange 字段补齐脚本 |
| P7a-9 | 题目使用频率分析：扩展 `coverage_report` 脚本 `--usage` flag + `GET /practice/questions/usage-stats` API（按 topic 聚合 times_used、correct_count、avg_time_spent） |
| P7a-10 | 覆盖率趋势快照：`coverage_cache` 增加 `snapshot_date` 字段，每次全量计算自动追加快照；`coverage_report --diff` 对比两个日期的快照 |

**测试：** coverage_service 15+ 测试，quality_service 20+ 测试，usage_stats 5+ 测试，集成测试验证现有 240 题全量计算不报错。

**验收标准：**
- [ ] 覆盖率脚本输出各学科得分和 gap 清单
- [ ] 质量评价为每道题产出 quality_score
- [ ] 数学覆盖率报告能区分强弱领域
- [ ] 质量分布报告能区分四个等级
- [ ] 使用频率报告能区分高频/低频/零使用题目
- [ ] 覆盖率快照在两次全量计算间可对比，`--diff` 输出改善/恶化 topic 列表
- [ ] 全部测试通过

### 9.3 P7b：数学纵深 + 出题流水线

**目标：** 扩展数学覆盖，验证混合出题流水线，建立 AI 判分可解释性基础。

**交付物：**

| 编号 | 交付物 |
|------|--------|
| P7b-1 | `question_router.py`：配置表 + route() |
| P7b-2 | Math23K 导入适配器 |
| P7b-3 | `llm_generator.py`：prompt + 三层验证 + 风险分级 |
| P7b-4 | 数学新增模板 8-10 个 |
| P7b-5 | `multi_fill_blank` + `ai_graded` 评分支持 |
| P7b-6 | 批量审核 API |
| P7b-7 | `production_run` CLI 脚本 |
| P7b-8 | Question 模型扩展字段 |
| P7b-9 | AI 判分可解释性（后端）：`grading_explanation` JSON 字段（含 confidence、dimension_breakdown、reasoning_summary）；`ai_graded` 评分时自动生成解释数据；`GET /practice/questions/{id}/grading-explanation` API |

**验收标准：**
- [ ] 数学 topic 覆盖率 ≥ 3%
- [ ] 新增 8-10 个数学模板
- [ ] Math23K 导入 ≥ 50 道
- [ ] LLM 生成 ≥ 20 道推理题
- [ ] 批量审核 API 可用
- [ ] 生产脚本可一键执行
- [ ] AI 判分结果附带可解释性数据（confidence + 维度拆解 + 推理摘要）
- [ ] 全部测试通过（新增 25+）

### 9.4 P7c：学习效果评价 + 家长可见

**目标：** L1 规则化学习效果指标 + 家长端展示 + 审核队列扩展。

**交付物：**

| 编号 | 交付物 |
|------|--------|
| P7c-1 | `learning_effect_service.py` |
| P7c-2 | 学习效果 API 端点（3 个） |
| P7c-3 | family API 扩展 |
| P7c-4 | `LearningEffectCard.vue` |
| P7c-5 | `LearningTrendChart.vue` |
| P7c-6 | 审核队列题目审核 tab |
| P7c-7 | PracticeAttempt `is_retry` 字段 |
| P7c-8 | PracticeSession `validity_flag` 字段 |
| P7c-9 | PracticeAnswerInput 新题型支持 |
| P7c-10 | AI 判分可解释性（家长展示）：`GradingExplanationPanel.vue` 组件——展示置信度条形图 + 评分维度拆解（如「知识点匹配 ✓ / 步骤完整性 ✗」）+ AI 推理摘要（1-2 句自然语言） |
| P7c-11 | 覆盖率趋势可视化：`CoverageTrendChart.vue`（ECharts 折线图，展示指定 topic/domain/subject 的覆盖率随时间变化） |

**验收标准：**
- [ ] 掌握度异常检测正确识别虚高/虚低
- [ ] 无效刷题检测正确标记
- [ ] 长期薄弱知识点正确识别
- [ ] 家长端卡片正确显示
- [ ] 趋势图正确展示
- [ ] 审核队列支持批量操作
- [ ] 儿童端新题型可输入
- [ ] AI 判分结果在家长端可查看，解释信息可理解
- [ ] 覆盖率趋势图在家长端可查看
- [ ] 全部测试通过（新增 20+）

### 9.5 P7d：学科扩展试点

**目标：** 语文、英语、科学各一个试点簇。

**交付物：**

| 编号 | 交付物 |
|------|--------|
| P7d-1 | 语文模板 5-8 个 |
| P7d-2 | 英语模板 5-8 个 |
| P7d-3 | 科学模板 5-8 个 |
| P7d-4 | LLM prompt 扩展（阅读理解选择、科学概念解释） |
| P7d-5 | 三学科路由配置 |
| P7d-6 | 儿童端学科切换验证 |

**验收标准：**
- [ ] 语文试点簇覆盖率 ≥ 15%
- [ ] 英语试点簇覆盖率 ≥ 15%
- [ ] 科学试点簇覆盖率 ≥ 15%
- [ ] 每学科至少 1 道 LLM 题目质量分 ≥ 0.6
- [ ] 儿童端能切换学科并看到掌握度
- [ ] 全部测试通过（新增 15+）

### 9.6 P7e：持续优化闭环

**目标：** 自动化优化机制落地 + BKT 单儿童参数校准。

**交付物：**

| 编号 | 交付物 |
|------|--------|
| P7e-1 | `optimization_loop` 全套子命令 |
| P7e-2 | 自动缺口发现 + 生产计划生成 |
| P7e-3 | 难度校准 |
| P7e-4 | 异常监控 |
| P7e-5 | 质量分定期重算 |
| P7e-6 | 路径优化建议 API |
| P7e-7 | 映射质量扫描 |
| P7e-8 | BKT 单儿童参数校准：`calibrate_bkt_params(child_id)` 函数——利用该儿童自身作答数据（≥20 次）做 per-topic 最大似然估计，更新 P(L) 和 P(T)；事件驱动（每 N 次作答触发）；校准结果写入 `bkt_calibration` 缓存表 |

**验收标准：**
- [ ] 一键全流程：发现缺口 → 生成计划 → 执行生产 → 覆盖率更新
- [ ] 难度校准正确检测人为偏差
- [ ] 异常监控正确标记异常题目
- [ ] 路径优化建议正确识别已掌握 topic
- [ ] BKT 校准后掌握度-正确率偏差（P7c 指标）显著缩小
- [ ] 覆盖率趋势快照在优化前后正确记录变化
- [ ] 全部测试通过（新增 10+）

### 9.7 依赖关系与风险

```
P7a ──→ P7b ──→ P7c ──→ P7d ──→ P7e
```

**主要风险：**

| 风险 | 缓解措施 |
|------|---------|
| Math23K 数据格式不符 | P7a 期间提前探查 |
| LLM 出题质量过低 | 调整 prompt + 降低 LLM 占比 |
| 真实数据不足导致效果指标空转 | L1 指标设计为数据不足时返回 null |
| 北京 topic 缺字段（P2-2 遗留） | P7a 第一步修复 |

### 9.8 整体验收标准（对照 Issue #129）

| Issue #129 验收标准 | Phase 7 对应交付 |
|--------------------|-----------------|
| 数学、语文、英语、科学四大学科均有可用的题库和练习 | P7b + P7d |
| 题库覆盖率和题目质量有可量化的评估指标 | P7a |
| 学习效果数据可用于持续改进出题和推荐策略 | P7c + P7e |

---

## 10. 明确不在 Phase 7 范围内的内容（未来候选项）

以下各项在设计过程中被明确排除出 Phase 7 范围，记录了排除原因，供后续阶段评估和选用。

### 10.1 题目生产与审核

| 项目 | 排除原因 | 未来价值 |
|------|---------|---------|
| 智能路由（根据历史数据自动选择生成方式的 ML 模型） | 第一阶段无足够数据训练模型 | 高——数据积累后可显著提升出题效率 |
| 题目版本管理（修改题目时保留历史版本） | 当前题目量不需要，过度工程化 | 中——题目量增长后可能需要 |
| 协作审核（多角色审核工作流、审核员培训/认证） | 仅一人审核 | 中——如果引入外部审核员则需要 |
| 题目生命周期管理（题目下线、题目过期机制） | 数据量不够大 | 中——长期运营后需要 |
| 自动知识点拆分/合并 | taxonomy 层面的调整不在本阶段范围 | 低——taxonomy 已足够稳定 |

### 10.2 覆盖率评价

| 项目 | 排除原因 | 未来价值 |
|------|---------|---------|
| 可视化仪表盘前端 | Phase 7a 只输出 API + 脚本 | 中——未来可能需要给非技术利益相关者展示 |
| 覆盖率目标自动追踪 | 过度工程化 | 低 |
| 复杂语义相似度检测 | 第一阶段靠 Bloom/难度/题型维度间接约束 | 中——能更精确识别同质化题目 |

> **已纳入 Phase 7：** 题目使用频率分析（→ P7a-9）、历史覆盖率趋势快照（→ P7a-10）。原排除理由「覆盖率评价不依赖使用数据」和「第一次上线就是第一次快照」在闭环度量视角下不成立——使用频率是生产投资回报率的衡量，覆盖率趋势是 P7e 优化闭环的效果度量前提。

### 10.3 题目质量评价

| 项目 | 排除原因 | 未来价值 |
|------|---------|---------|
| IRT（项目反应理论）难度/区分度分析 | 需要数千次作答数据，当前不支持 | 高——数据积累后是 gold standard |
| 题目版本对比（diff 历史） | 与题目版本管理一起推迟 | 低 |
| 协作审核（审核员评级/校准机制） | 仅一人审核 | 中 |
| 实时质量监控 dashboard | 不做实时刷新 | 低 |
| 协变量分析（DIF - 题目功能差异分析） | 检测题目是否对不同性别/地区儿童有偏见——当前数据量不支持 | 高——教育公平性的重要工具 |

> **已纳入 Phase 7（最小版）：** AI 判分可解释性框架（→ P7b-9 后端 + P7c-10 家长展示）。原排除理由「用置信度阈值做简单防御」不足以支撑 `ai_graded` 题型的用户信任——Phase 7 的最小版提供 confidence + 维度拆解 + 推理摘要，完整系统性框架仍待后续迭代。

### 10.4 学习效果评价

| 项目 | 排除原因 | 未来价值 |
|------|---------|---------|
| BKT 参数在线自适应（完整 EM 算法） | 需要大规模群体数据 | 高——能显著提升掌握度估计准确性 |
| 前测-后测实验设计 | 需要严格控制 | 中——学术验证价值高 |
| 跨儿童比较（排名、百分位） | 产品设计决策：不做排名 | 低——与隐私优先理念冲突 |
| AI 生成学习报告（叙述性总结） | 可后续用 AI tutor 在 session 内反馈替代 | 中——家长沟通价值 |
| 听力/口语学习效果评估 | 音频相关能力评估需要专门基础设施 | 中——英语学科完整评估需要 |
| L2 离线验证（错题复练前后对比的回顾性分析） | 需要数据积累 3-6 个月 | 高——验证学习效果的核心手段 |
| L3 在线评估（实时模型校准） | 需要大量数据 | 中——长期优化手段 |
| 间隔复习效果长期验证 | 需要数月数据积累 | 高——验证 SM-2 是否真的有效 |
| 元认知能力评估（学习方法与自我监控） | 不适合题目测评，需要情境任务 | 中——需要专门设计 |
| 社会情感能力评估 | 不适合传统测评 | 低——不在核心学科范围 |

> **已纳入 Phase 7（简化版）：** BKT 单儿童参数校准（→ P7e-8）。与完整 EM 算法的区别：仅利用单个儿童自身作答数据（≥20 次）做 per-topic 最大似然估计，不需要群体数据。这是「数据积累后才能做」的最小可行版本——20 次作答的门槛在 Phase 7 数学纵深后即可达到。完整群体级 EM 仍待后续阶段。

### 10.5 学科扩展

| 项目 | 排除原因 | 未来价值 |
|------|---------|---------|
| 作文评分系统 | 开放式评分技术难度大，AI 评分过度自信风险高 | 高——语文核心能力 |
| 英语听力/音频题 | 需要音频基础设施（存储、播放、语音识别） | 高——英语完整评估需要 |
| 科学实验交互题 | 需要交互式设计能力 | 中——科学探究能力评估 |
| 历史与社会 | 不在四核心学科内 | 中 |
| 计算思维 | 需要专门的编程/逻辑题目框架 | 中 |
| 跨学科问题解决 | 需要专门的题目设计方法论 | 中 |
| 口语交际评估 | 需要语音基础设施 | 低 |
| 艺术/体育/劳动 | 不适合标准题库模式 | 低 |

### 10.6 持续优化

| 项目 | 排除原因 | 未来价值 |
|------|---------|---------|
| 自动学习路径生成（非建议） | 路径创建是家长行为 | 中——长期可减轻家长负担 |
| 题目自动淘汰/过期 | suspended 题目的最终处置仍需人工 | 中——长期运营需要 |
| A/B 测试框架 | 当前不需要对比不同出题方式 | 中——优化决策支持 |
| 知识点自动拆分/合并 | taxonomy 层面调整不在范围 | 低 |

### 10.7 用户体验

| 项目 | 排除原因 | 未来价值 |
|------|---------|---------|
| 独立 admin dashboard | 所有内部工具通过 CLI 脚本和 API 访问即可 | 中——非技术运营者需要 |
| 数据可视化大屏（Grafana/BI 集成） | 不做 | 低 |
| 多儿童学习数据对比 | 产品设计决策：不做兄弟姐妹对比 | 低 |
| 移动端适配优化 | 家长端低频使用，不投入额外适配 | 低 |
| AI 叙述性学习报告 | 可后续用 AI tutor session 内反馈替代 | 中 |

### 10.8 儿童安全与合规

| 项目 | 排除原因 | 未来价值 |
|------|---------|---------|
| 完整的儿童数据保护合规审计 | 需要法律专业支持 | 高——法律要求 |
| AI 判分的系统性可解释性框架 | 当前用置信度阈值作为简单防御 | 高——教育公平性要求 |
| 题目数据版权系统性审查 | 逐案处理 | 中——规模增长后需要系统化 |
| 内容安全的多语言/多方言适配 | 当前仅中文 | 中——如果扩展到少数民族地区 |

> **已纳入 Phase 7（最小版）：** AI 判分可解释性框架的最小版本（→ P7b-9 + P7c-10）已在 Phase 7 中实现，提供 per-question 的 confidence + 维度拆解 + 推理摘要。完整系统性框架（跨题目/跨儿童的评分偏差分析、公平性审计）仍待后续阶段。

---

## 附录 A：Phase 0-6 审计报告关键发现（供参考）

- **整体判定：** CONDITIONAL PASS
- **P0 全部修复**，P1 修复 4/5（P1-1 外部题库导入推迟到 Phase 7）
- **知识覆盖率 0.56%**（20/3,598 topics 有题目）
- **仅数学有 25 个程序化模板**
- **BKT 和 SM-2 已接入生产路径**（P1-2, P1-3 修复）
- **141+ 学习测试全部通过**

## 附录 B：各学科知识点分布

| 学科 | 上游 topics | 北京特定 topics | 合计 |
|------|-----------|----------------|------|
| 数学 | 503 | 190 | 693 |
| 科学 | 547 | 10 | 557 |
| 语文 | — | 372 | 372 |
| 英语 | 286 | 48 | 334 |
| 历史 | 90 | 304 | 394 |
| 物理 | — | 199 | 199 |
| 化学 | — | 157 | 157 |
| 生物 | — | 185 | 185 |
| 地理 | — | 120 | 120 |
| 道德与法治 | — | 148 | 148 |
| 信息技术 | — | 48 | 48 |
| 其他 | 164 | 227 | 391 |
| **合计** | **1,590** | **2,008** | **3,598** |

## 附录 C：开源项目调研参考

Epic #121 列出的 15 个候选开源项目中，Phase 7 直接相关的：

| 项目 | 用途 | Phase 7 使用方式 |
|------|------|-----------------|
| Math23K | 小学数学应用题 | P7b Math23K 导入适配器 |
| os-taxonomy-beijing | 知识图谱 | 已集成（Phase 0），Phase 7 使用其 topic 体系 |
| mathgenerator | 数学题目生成器 | 研究参考（MIT 许可），不直接集成 |
| ScienceQA | 科学问答数据集 | 研究参考，未来 P7d 科学扩展时参考 |
| CJEval | 中文评价 | 研究参考 |
| K12-KGraph | K12 知识图谱 | 研究参考 |

**未采用的项目：** EdNet（韩国数据，中国课程适配度低）、C3/CMRC2018（阅读理解数据集，非题目生成工具）、EduData（数据集非工具）。
