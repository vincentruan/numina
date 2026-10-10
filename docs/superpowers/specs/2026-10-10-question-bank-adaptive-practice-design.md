# 儿童题库与自适应练习系统设计

> **状态**: 设计确认，待实施
> **日期**: 2026-10-10
> **方案**: 模板引擎 + LLM 增强（双轨模式，先 A 后 B）
> **MVP 学科**: 小学数学

## 1. 背景与目标

### 1.1 现状

Numina 已集成 os-taxonomy-beijing 知识图谱，具备完整的学习系统基础设施：

- **知识图谱**: 1,590 + 2,008 知识点，3,221+ 先修边，183 聚类，教育部 2022 课标映射
- **掌握状态机**: locked → available → learning → assessing → mastered → review → parent_review
- **间隔复习**: 简化 SM-2 算法（stability-based），next_review_at 已入库
- **AI 导师**: learning-tutor 技能，对话式教学 + 评估
- **游戏化**: XP 7 级、星星币、连续学习天数、失败提醒

**核心缺失**: 无结构化题库、无逐题作答记录、无程序化出题、无诊断测评、推荐系统初级。

### 1.2 目标

在已有知识图谱和学习系统基础上，建设：

1. 围绕 os-taxonomy 微知识点组织的标准化题库（MVP 聚焦小学数学）
2. 按学科特点分层的题目获取与生成能力
3. 基于掌握状态和作答表现的自适应选题引擎
4. 与现有 AI 导师、游戏化系统深度整合的练习体验

### 1.3 定位：双轨模式

**MVP 阶段（Track A）**: 练习系统作为 AI 导师的补充。AI 导师讲解概念后，提供结构化练习巩固。测评结果反馈给现有状态机。

**扩展阶段（Track B）**: 架构上预留独立练习系统的能力。题目数据模型独立于 AI 导师，自适应引擎可替换升级。后续根据使用反馈决定是否升级为双轨并行。

### 1.4 设计原则

- **增量建设**: 复用现有状态机、XP 系统、知识图谱，不重复造轮子
- **质量优先**: 题目质量优先于数量，答案正确性必须可验证
- **版权安全**: 不直接导入非商业许可的开源数据集
- **渐进式**: MVP 先交付端到端闭环，再逐步扩展学科和自适应深度

## 2. 数据模型

### 2.1 新增模型

所有模型位于 `server/packages/db/models/learning/` 下。

#### Question（题目）

```python
class Question(Base):
    __tablename__ = "questions"

    id: int                          # Snowflake ID
    topic_id: int                    # FK → learning_topics.id (主知识点, NOT NULL)
    question_type: str               # multiple_choice / true_false / fill_blank / calculation / application
    stem: str                        # 题干 (Markdown 子集)
    stem_zh: str | None              # 中文题干
    options_json: str                # JSON: [{key, text, text_zh}] (选择题)
    answer_json: str                 # JSON: 标准答案，结构因题型而异
    solution_json: str | None        # JSON: 解析步骤
    difficulty: int                  # 1-5
    bloom_level: str                 # remember / understand / apply / analyze
    source: str                      # template / llm_generated / human_created / imported
    source_version: str | None       # 模板版本号或 LLM 模型版本
    review_status: str               # pending / approved / rejected / deprecated
    review_notes: str | None
    age_group: str                   # low / mid / high (冗余，方便查询)
    parameters_json: str | None      # JSON: 模板参数（变体追踪）
    times_used: int                  # 使用次数
    correct_count: int               # 正确次数
    created_at: datetime
    updated_at: datetime
```

**索引**: topic_id (查询主路径), question_type + age_group + difficulty (选题过滤), review_status (审核队列)

#### QuestionKnowledgePoint（题目-知识点关联，多对多）

```python
class QuestionKnowledgePoint(Base):
    __tablename__ = "question_knowledge_points"

    id: int
    question_id: int                 # FK → questions.id
    topic_id: int                    # FK → learning_topics.id
    role: str                        # primary / secondary

    __table_args__ = (
        UniqueConstraint("question_id", "topic_id"),
    )
```

**MVP 策略**: 创建题目时自动填充 primary role 行。多对多扩展在 Phase 2+ 使用。

#### PracticeSession（练习会话）

```python
class PracticeSession(Base):
    __tablename__ = "practice_sessions"

    id: int                          # Snowflake ID
    child_id: int                    # FK → users.id
    topic_id: int                    # FK → learning_topics.id (主要知识点)
    session_mode: str                # practice / diagnostic / review / challenge
    question_ids_json: str           # JSON: [id, ...] 有序题目列表
    started_at: datetime
    ended_at: datetime | None
    total_score: float | None        # 最终得分 (0.0-1.0)
    completed_count: int             # 已完成题目数
    source: str                      # adaptive / parent_assigned / self_selected
    learning_progress_id: int | None # FK → learning_progress.id (关联的掌握记录更新)
```

#### PracticeAttempt（逐题作答记录）

```python
class PracticeAttempt(Base):
    __tablename__ = "practice_attempts"

    id: int                          # Snowflake ID
    session_id: int                  # FK → practice_sessions.id
    question_id: int                 # FK → questions.id
    child_id: int                    # FK → users.id
    topic_id: int                    # FK → learning_topics.id (冗余，方便查询)
    user_answer_json: str            # JSON: 用户作答
    is_correct: bool
    time_spent_seconds: int | None
    attempt_number: int              # 第几次尝试此题
    created_at: datetime

    __table_args__ = (
        Index("ix_practice_attempt_child_topic_created", "child_id", "topic_id", "created_at"),
    )
```

### 2.2 与现有模型的关系

```
Question ──→ LearningTopic (topic_id, 主知识点)
Question ──→ QuestionKnowledgePoint ──→ LearningTopic (多对多)
PracticeSession ──→ User (child_id)
PracticeSession ──→ LearningTopic (topic_id)
PracticeSession ──→ LearningProgress (可选, 结果更新的目标记录)
PracticeAttempt ──→ PracticeSession (session_id)
PracticeAttempt ──→ Question (question_id)
PracticeAttempt ──→ LearningTopic (topic_id, 冗余)
```

### 2.3 答案 JSON 结构约定

| 题型 | answer_json | user_answer_json |
|------|-------------|-----------------|
| multiple_choice | `{"key": "B"}` | `{"key": "B"}` |
| true_false | `{"value": true}` | `{"value": false}` |
| fill_blank | `{"value": "分数"}` | `{"value": "分数"}` |
| calculation | `{"answer": 95, "steps": [...]}` | `{"answer": 95}` |
| application | `{"answer": "见解析", "acceptable": [...]}` | `{"answer": "..."}` |

## 3. 题目生成引擎

### 3.1 三层生成策略

**Layer 1: 程序化模板生成（数学主力）**

- 模板定义：参数化 Python 函数，输入参数范围 → 输出题目 + 答案
- 验证：Python 内置求解器 / sympy 验证答案正确性
- 变体：同模板不同参数 = 不同题目（自然去重）
- 存储：parameters_json 记录参数，用于追溯

**Layer 2: LLM 辅助生成（高认知层级题目）**

- 触发：知识点的 evidence / assessment_prompt 需要开放式或应用题
- 输入：topic.description + evidence + age_group + difficulty + bloom_level
- 输出：结构化 JSON（stem + answer + solution + topic_ids + difficulty）
- 验证：LLM 交叉验证 + 知识点覆盖检查 + 年龄适配检查 + 内容安全
- 初始状态：review_status = "pending"（需人工审核）

**Layer 3: 人工创建**

- 入口：家长/教育者在管理后台手动创建
- 直接标记为 review_status = "approved"

### 3.2 质量关卡

所有题目必须通过以下自动验证才能入库：

1. **答案正确性**: 数学题用程序化求解器验证；非计算题用 LLM 交叉验证
2. **知识点映射有效性**: topic_id 必须存在于 learning_topics
3. **年龄适配**: age_group 与 topic.age_group 匹配
4. **格式完整性**: stem 非空、answer 结构合法、选择题有 ≥2 选项
5. **重复检测**: 相同 stem + answer 视为重复，标记
6. **内容安全**: 复用现有 content_safety_filter

LLM 生成题目额外需人工审核（审核队列在 Phase 2 实现）。

### 3.3 模板系统设计

自建简单模板注册机制（不集成 mathgenerator，其 API 不够灵活）：

```python
# server/packages/domain/question_templates/

@register_template("math.arithmetic.addition_2digit")
def generate_addition(params: dict) -> GeneratedQuestion:
    a = random.randint(params.get("min", 10), params.get("max", 99))
    b = random.randint(params.get("min", 10), params.get("max", 99))
    return GeneratedQuestion(
        stem=f"计算：{a} + {b} = ?",
        answer={"answer": a + b},
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_xxx",
    )

# 注册表 API:
# - list_templates(subject) → 可用模板列表
# - generate(template_id, params) → GeneratedQuestion
# - verify(question) → bool
```

### 3.4 MVP 模板清单（小学数学）

| 知识点域 | 模板示例 | 覆盖知识点 |
|---------|---------|-----------|
| 数的运算 | 两位数加减、乘除法、竖式计算、估算 | ~15 |
| 分数/小数 | 比较、运算、转换 | ~5 |
| 几何基础 | 周长、面积、角度计算 | ~5 |
| 应用题 | 行程、价格、比例 | ~5 |
| **合计** | | **~30** |

## 4. 自适应练习引擎

### 4.1 核心组件

```python
class PracticeEngine:
    def select_questions(self, topic_id, child_id, mode, count) -> list[Question]:
        """选题：根据知识点、儿童、模式、数量选择题目"""

    def evaluate_attempt(self, question_id, user_answer) -> AttemptResult:
        """评分：自动判断作答正确性"""

    def update_mastery(self, session_id) -> ProgressUpdate:
        """状态更新：练习结果推动掌握状态机"""
```

### 4.2 选题策略（规则引擎 MVP）

| 模式 | 策略 |
|------|------|
| practice | 根据 mastery_level 匹配难度范围 |
| diagnostic | 从易到难 spread，定位掌握水平 |
| review | 优先 overdue + 历史错题 |
| challenge | 高于当前水平的难度 |

**难度-mastery 映射**:

| mastery_level | 选题难度 |
|---------------|---------|
| available / learning | 1-2 |
| assessing | 2-3 |
| mastered | 3-4 |
| review | 1-2 |

**去重规则**: 同一题目 7 天内不重复（基于 PracticeAttempt.created_at）。同模板不同参数视为不同题目。

### 4.3 作答结果 → 掌握状态

```
PracticeSession 完成 → 计算得分 → 更新 LearningProgress

score >= 0.8:
  learning → assessing
  assessing → mastered
  review → learning (重新评估)

score < 0.5:
  assessing → learning (回退)
  检查失败连续次数 → 通知

0.5 <= score < 0.8:
  更新 mastery_score，不转换状态
```

新增 `completed_via = "practice_session"` 路径，接入现有 progress_service。现有值为 `"ai_assessment"` 和 `"parent_approval"`，新增值 `"practice_session"` 需在 `transition_to_mastered` 的校验逻辑中同步添加。

### 4.4 扩展预留：MasteryEstimator 接口

```python
class MasteryEstimator(Protocol):
    def estimate(self, child_id, topic_id, attempts: list[PracticeAttempt]) -> float:
        """返回 0.0-1.0 的掌握度估计"""

class RuleBasedMasteryEstimator(MasteryEstimator):
    """MVP：基于最近 N 次正确率"""

# Phase 2+ 可替换为:
class BayesianKnowledgeTracingEstimator(MasteryEstimator):
    """需要足够历史数据后启用"""
```

## 5. 用户体验

### 5.1 儿童端练习流程

**入口**: LearningMapPage 知识点卡片新增练习按钮。

**PracticeSessionPage 流程**:
1. 选择模式（快速 5 题 / 标准 10 题 / 诊断 8 题 / 挑战 5 题）
2. 逐题作答（即时反馈：正确动画 / 错误 + 解析）
3. 结果汇总（得分、用时、错题回顾、XP/星星币获得）
4. 后续操作：再来一组 / AI 辅导错题 / 返回地图

**题型交互**:
- 选择题：点选按钮
- 判断题：✓/✗ 按钮
- 填空题：输入框
- 计算题：输入框 + 可选步骤展示

### 5.2 AI 导师协作

```
练习后 → AI 辅导错题（传入错题上下文，针对性讲解）
AI 导师讲解后 → 推荐练习（传入知识点 + 建议难度）
```

### 5.3 家长端（Phase 2）

- 练习报告（得分、用时、错题）
- 知识点维度汇总（正确率趋势）
- 题目审核队列
- 手动布置练习

## 6. API 设计

### 6.1 新增路由

路由文件: `server/apps/backend/app/routers/practice.py`
前缀: `/api/v1/practice`

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | /practice/questions | 题目列表（按知识点/难度筛选） |
| POST | /practice/sessions | 创建练习会话（选题+开始） |
| GET | /practice/sessions/{id} | 练习会话详情 |
| POST | /practice/sessions/{id}/answer | 提交单题答案 |
| POST | /practice/sessions/{id}/finish | 完成会话（得分+状态更新） |
| GET | /practice/stats/{child_id} | 练习统计（家长端） |
| GET | /practice/coverage | 知识点覆盖率（管理端） |

### 6.2 复用现有路由

- GET /learning/topics → 知识点列表
- GET /learning/child/map → 掌握状态
- POST /learning/child/sessions → AI 导师会话（错题辅导）

## 7. 代码组织

### 7.1 后端新增文件

```
server/
├── packages/db/models/learning/
│   ├── question.py                  # Question + QuestionKnowledgePoint
│   └── practice.py                  # PracticeSession + PracticeAttempt
├── packages/domain/question_templates/
│   ├── __init__.py                  # 模板注册表
│   ├── base.py                      # GeneratedQuestion, QuestionTemplate base
│   ├── math_arithmetic.py           # 算术模板
│   ├── math_fractions.py            # 分数模板
│   ├── math_geometry.py             # 几何模板
│   └── math_word_problems.py        # 应用题模板
├── apps/backend/app/routers/
│   └── practice.py                  # 练习 API 路由
├── apps/backend/app/schemas/
│   └── practice.py                  # 练习 Pydantic schemas
├── apps/backend/app/services/learning/
│   ├── question_service.py          # 题目 CRUD + 查询
│   ├── practice_service.py          # 练习会话管理
│   ├── scoring_service.py           # 自动评分
│   ├── adaptive_service.py          # 选题引擎 + MasteryEstimator
│   └── question_generator.py        # 模板生成 + LLM 生成入口
├── apps/backend/app/services/learning/
│   └── (新增 quality_gate.py)       # 质量关卡验证
└── apps/backend/alembic/versions/
    └── xxx_add_questions_and_practice.py
```

### 7.2 前端新增文件

```
frontend/apps/child/src/
├── api/practice.ts                  # 练习 API
├── pages/learning/
│   └── PracticeSessionPage.vue      # 练习会话页面
├── components/learning/
│   ├── PracticeQuestionCard.vue     # 题目渲染
│   ├── PracticeAnswerInput.vue      # 答题输入（按题型切换）
│   ├── PracticeResultSummary.vue    # 结果汇总
│   └── PracticeProgressBar.vue      # 进度条
```

### 7.3 前端修改文件

```
frontend/apps/child/src/
├── pages/learning/LearningMapPage.vue  # 新增练习入口按钮
├── api/learning.ts                     # 可能需要新增 practice 相关类型
└── router/index.ts                     # 新增 PracticeSessionPage 路由
```

## 8. 开源数据源核查结论

| 数据源 | 题目完整性 | 许可证 | 适合商业产品 | 决策 |
|--------|----------|--------|------------|------|
| Math23K | 23K 中文应用题 | 数据授权不明 | ❌ | 借鉴格式，不直接入库 |
| mathgenerator | 程序化生成 | MIT | ✅ | 借鉴设计，自建模板 |
| K12-KGraph | 图谱+练习 | 非商业 | ❌ | 仅借鉴设计思路 |
| C3 / CMRC2018 | 阅读理解 | 非商业 | ❌ | 语文 Phase 3 参考 |
| ScienceQA | 多学科 | CC BY-NC-SA | ❌ | 借鉴 skill tag 设计 |
| CJEval | 初中多学科 | 研究用途 | ❌ | 借鉴题目结构 |
| EdNet | 作答行为 | 研究用途 | ❌ | 知识追踪模型参考 |

**结论**: 大多数开源教育数据集仅限非商业研究。采用程序化生成 + LLM 生成 + 人工审核的组合策略。

## 9. 分阶段路线图

### Phase 1 (MVP): 小学数学结构化练习

**目标**: 儿童能完成一次有效的数学练习闭环

**范围**:
- 后端: 数据模型 + Alembic 迁移 + 10-15 个数学模板 + 模板注册机制 + 自动评分 + 练习 API + 规则选题 + 状态机打通 + 练习统计
- 前端: PracticeSessionPage + 题目渲染 + 答题输入 + 即时反馈 + 结果汇总 + 知识地图入口

**验收标准**:
- 8 岁儿童能选择"两位数加法"知识点
- 完成 5 道参数化计算题
- 获得即时反馈和得分
- 80% 正确率后状态推进
- 获得 XP/星星币
- 错题可查看解析

### Phase 2: 题目丰富 + 智能选题 + 家长管理

- LLM 题目生成 + 审核队列
- 诊断测评模式
- 间隔复习推荐
- 知识点覆盖率仪表盘
- 应用题模板扩展
- 练习历史趋势

**进入条件**: ≥30 数学知识点各有 ≥5 题，≥10 个模板稳定运行

### Phase 3: 多学科扩展 + 知识追踪

- 英语、语文、科学学科
- BKT/知识追踪模型
- 自适应难度调整
- 跨知识点诊断

### Phase 4: 高级能力

- 外部题目导入框架
- 题目质量自动评估
- AI 导师深度整合
- 互动题/图文题
- 班级/群组分析

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 模板覆盖不足 | MVP 先聚焦高频知识点，LLM 生成补充 |
| LLM 答案幻觉 | 交叉验证 + 人工审核关卡 |
| 知识点映射错误 | 模板绑定时直接指定 topic_key，非事后标注 |
| 儿童体验单调 | 即时反馈动画、多样题型、AI 导师协作 |
| 与现有系统冲突 | 新增独立模型/API，通过 topic_id 关联而非修改现有逻辑 |
