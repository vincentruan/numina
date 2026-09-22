# Learning OS Design Spec

> 面向儿童的 AI Learning Operating System — 基于 os-taxonomy 知识图谱

| 字段 | 值 |
|---|---|
| Date | 2026-09-22 |
| Module | Learning OS (新增模块) |
| Status | Draft — Reviewed × 2 (2026-09-22) |
| Scope | 全栈: 后端数据模型 + API + AI Skill + 前端页面 |

---

## 1. 产品愿景

打造面向儿童的 AI Learning Operating System（儿童学习操作系统）。

通过知识图谱、AI Tutor、游戏化机制和家庭反馈系统，为每个孩子建立一个动态成长模型。

**核心转变：**
- 从 "孩子应该学习什么？" → "这个孩子下一步最适合学习什么？"
- 从 课程完成率 → 能力成长率（基于评估历史 + 能力维度 + 间隔重复的综合模型）
- 从 考试评价 → 长期能力建模

**国际化（i18n）策略：**

os-taxonomy 原始数据为英文。交互信息（topic 名称、描述、evidence、AI 对话）优先支持中文展示：
- 知识图谱层存储英文原文 + 中文翻译（`*_zh` 字段），前端按 locale 选择展示语言
- AI Tutor 对话默认使用中文，学科专业术语保留英文原文（如 "fraction"、"algebra"）
- 前端 UI 文案走现有 i18n 体系（`zh-CN` / `en` locale 文件）

**产品定位：**

| ❌ 不是 | ✅ 是 |
|---|---|
| AI 搜题工具 | 儿童学习基础设施 |
| 在线课程播放器 | Knowledge Graph + Child Model + AI Tutor |
| AI 聊天机器人 | + Content Engine + Gamification + Parent Insight |
| 单纯题库系统 | |

**目标用户：**

- **Persona A — 儿童（6-12岁）：** 有趣地学习、被理解、按自己的速度成长、获得成就感
- **Persona B — 家长：** 理解孩子成长状态、获得科学建议、发现孩子优势

**孩子的典型学习旅程（F-22 修复）：**

> 小明（9 岁）周二下午打开 App。Home 页显示：家务 2 项待完成，学习 1 项推荐（家长派发的"分数加法"）。
> 他先完成家务（15 分钟），然后点击进入学习卡片。
> 进入 LearningTopicPage，看到简介 + 前置知识（✅ 分数概念、✅ 通分），点击 [开始学习]。
> AI 导师用中文和他对话，用披萨分片的比喻解释分数加法（8 分钟）。
> 然后进入 3 道评估题（3 分钟），答对 2/3。
> AI 说 "你掌握得很好！有一小题我们再练习一下"，记录 attempt，mastery_score = 0.67。
> 因为 score < 0.8，状态变为 review，小明看到 "继续学习 📖" 鼓励画面，获得 5 coins。
> 第二天他回来，今日推荐显示 "复习：分数加法"，他再次尝试并通过（score = 1.0），获得 10 coins + 徽章进度更新。
> 家长在 BabyLearningPage 看到小明的学习进度：分数加法已掌握 ✅，本周学习 2 次，共 26 分钟。

---

## 2. 与现有系统的关系

### 2.1 架构定位：并行扩展

Learning OS 作为新的独立学习模块加入 Numina，与现有系统并行：

```
┌─────────────────────────────────────────────────────┐
│                Numina Family App                      │
├──────────┬──────────┬───────────┬────────────────────┤
│  财务    │  家务    │  素养     │  Learning OS       │
│  Dashboard│  Chores  │  Literacy │  (新增模块)        │
├──────────┴──────────┴───────────┴────────────────────┤
│              共享基础设施                               │
│  coins · badges · notifications · AI agent (DeerFlow) │
├──────────────────────────────────────────────────────┤
│              知识图谱层                                │
│  os-taxonomy (全局共享) → topics · dependencies        │
│  Child Model → mastery · progress · readiness          │
└──────────────────────────────────────────────────────┘
```

**为什么并行而非替换：**
- 现有 literacy 系统（财商素养：earning/choosing/waiting/caring 四维度）运行稳定
- os-taxonomy 学科知识图谱与 literacy 财商素养是正交的
- 并行允许独立迭代，未来通过「能力信号」层汇聚

**为什么 Learning OS 在 Numina 内部（而非独立工具）：**
- **共享身份体系：** 孩子已有账号、角色、家庭绑定——零注册成本
- **共享激励基础设施：** coins/badges/streak 已运行，学习奖励即插即用
- **家长审核闭环：** 家长已有日常打开 App 审核家务的习惯，学习任务复用同一审核路径
- **日常整合点：** 学习可以嵌入现有的每日流程（完成家务后解锁学习 → 赚更多 coins → 兑现心愿）
- **长期 Child Model：** chore + literacy + learning 三维度汇聚为统一成长画像，独立工具无法实现
- **收敛接口（Phase 3 准备）：** 定义 `child_capability_signal` 聚合结构，各模块产出兼容输出：

```python
# 能力信号聚合接口（Phase 3 实现，Phase 1 预留数据结构）
class ChildCapabilitySignal:
    child_id: str
    dimensions: dict[str, float]  # {"financial_literacy": 0.7, "mathematics": 0.5, "responsibility": 0.8}
    learning_velocity: float      # 跨模块的学习速度指标
    engagement_score: float       # 综合参与度
    updated_at: datetime
```

### 2.2 任务模型：独立模型 + 共享激励

学习任务不复用 Chore 模型，而是独立设计：

| 维度 | Chore（家务） | Learning（学习） |
|---|---|---|
| 状态机 | available → pending_approval → approved/rejected | locked → available → learning → assessing/parent_review → mastered |
| 评估方式 | 家长审核完成 | AI 评估 or 家长审核 |
| 关联数据 | 无知识图谱 | 关联 topic + prerequisite |
| 激励 | coins + streak | coins + streak + badges + XP |

**共享基础设施：**
- `CoinTransaction` — 掌握度达成时触发 coin 奖励（新增 type: `learning_earn`）
- `LiteracyBadge` 模式 — 学习维度徽章（独立定义）
- 通知系统 — 任务派发/完成通知
- AI Agent — 新增 `learning-tutor` skill

**与现有日常流程的整合契约：**

| 维度 | 整合方式 |
|------|----------|
| 每日流程 | 孩子打开 App → Home 页同时展示家务和学习任务卡片 |
| 奖励互通 | learning_earn 与 chore_earn 共用同一个 coin 池，汇率相同（1 topic = 基础 coins） |
| 心愿兑现 | 学习赚的 coins 可兑现心愿（与家务 coins 无差别） |
| 家长看板 | BabyLearningPage 与家务/素养看板同级展示，一个入口看全部 |
| 非强制 | 学习为 opt-in（不像家务可以设为必须完成），但提供 streak 激励每日回归 |

---

## 3. 数据模型设计

### 3.1 知识图谱层（全局共享）

os-taxonomy 数据为所有家庭共享，不按 family 隔离。

#### `learning_topic` 表

来源：os-taxonomy `topics.json`（1,590 条）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger | Snowflake ID (主键) |
| `topic_key` | String(50), unique | os-taxonomy ID，如 `mt_xxx` |
| `topic_type` | String(20) | `CONCEPTUAL` / `PROCEDURAL` / `META` / `LANGUAGE` / `REPRESENTATIONAL` |
| `subject` | String(50) | `science` / `mathematics` / `english` / `history` / `personal_social` / `life_skills` / `computing` / `learning_to_learn` |
| `domain` | String(100), nullable | 子领域，如 "Addition & Subtraction", "Algebra" |
| `name` | String(200), nullable | 人类可读名称（英文原文） |
| `name_zh` | String(200), nullable | 中文翻译名称 |
| `description` | Text | 知识点描述（英文原文） |
| `description_zh` | Text, nullable | 中文翻译描述 |
| `age_range_start` | Integer, nullable | 起始年龄（4-13） |
| `age_range_end` | Integer, nullable | 结束年龄 |
| `centrality` | Float, nullable | 图谱中心度（越高越基础/关键） |
| `evidence` | JSON | 掌握度证据列表（英文原文） `["can do X", "understands Y"]` |
| `evidence_zh` | JSON, nullable | 中文翻译证据列表 |
| `assessment_prompt` | Text, nullable | AI 评估提示语，含 `{{name}}` 占位符 |
| `assessment_prompt_zh` | Text, nullable | 中文版 AI 评估提示语 |
| `standards` | JSON | 关联的课程标准编码 `["uk-nc-2013:AD.KS1.1"]`（来源 os-taxonomy `standards` 必填字段） |
| `ability_dimensions` | JSON, nullable | 该 topic 关联的能力维度标签 `["numerical_reasoning", "spatial"]`（**seed 阶段由 LLM 从 topic 元数据推导生成**，非 os-taxonomy 原始字段。推导规则见下方说明） |
| `deprecated` | Boolean, default False | 数据版本管理标记：os-taxonomy 更新时已删除的 topic 标记为 true（不物理删除，保护 learning_progress 引用） |
| `age_group` | String(10) | 计算字段：`low`(5-7) / `mid`(8-10) / `high`(11+) |

**`ability_dimensions` 推导规则：**

os-taxonomy 不提供此字段。seed 脚本使用 LLM 批量分析 topic 的 `subject` + `domain` + `description` + `type`，映射到预定义能力维度列表：

```python
ABILITY_DIMENSIONS = [
    "numerical_reasoning",    # 数学推理
    "spatial_reasoning",      # 空间推理
    "verbal_reasoning",       # 语言推理
    "scientific_inquiry",     # 科学探究
    "computational_thinking", # 计算思维
    "social_emotional",       # 社交情感
    "creative_thinking",      # 创造性思维
    "physical_kinesthetic",   # 身体运动
    "memory_recall",          # 记忆回忆
    "metacognition",          # 元认知
]
```

推导结果缓存在 `ability_dimensions` 字段中，seed 后人工抽检每学科 5 个 topic 验证合理性。

#### `learning_dependency` 表

来源：os-taxonomy `dependencies.json`（3,221 条）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger | Snowflake ID |
| `topic_id` | BigInteger, FK → learning_topic.id | 依赖者（需要先学这个） |
| `prerequisite_id` | BigInteger, FK → learning_topic.id | 被依赖者（先修知识） |
| `strength` | String(10) | `hard`（必须掌握）/ `soft`（有益） |
| `reason` | Text | 自然语言解释为什么需要这个前置知识 |

#### `learning_cluster` 表

来源：os-taxonomy `clusters.json`（183 条）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger | Snowflake ID |
| `subject` | String(50) | 学科 |
| `domain` | String(100) | 子领域 |
| `age_range_start` | Integer, nullable | 原始起始年龄（来源 os-taxonomy `ageRangeStart`） |
| `age_group` | String(10) | 计算字段：基于 `age_range_start` → `low`(≤7) / `mid`(8-10) / `high`(≥11) |
| `summary` | Text | 家长友好的学习描述 |

**Cluster 用途说明（R-08 修复）：**

os-taxonomy 的 clusters 是纯描述性摘要，通过 `(subject, domain, age_range_start)` 间接关联 topic，**不持有 topic ID 引用**。因此：
- **前端 LearningMapPage 的 domain 分组**直接从 `learning_topic` 表按 `(subject, domain)` 聚合，不依赖 cluster 表
- **cluster 表的用途**：为家长提供"学科概览"文案（如"数学 > 分数 > 8-10 岁：学习分数的基本概念和运算"），以及辅助 AI 推荐时理解领域结构
- **cluster → topics 关联**：在 service 层通过 `WHERE subject = ? AND domain = ? AND age_group 匹配` 动态查询，不建 FK

### 3.2 学习进度层（per-family）

#### `learning_progress` 表

每个孩子在每个 topic 上的掌握度。

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger | Snowflake ID |
| `child_id` | BigInteger, FK → user.id | 孩子 |
| `topic_id` | BigInteger, FK → learning_topic.id | 知识节点 |
| `mastery_level` | String(20) | 状态（见下方状态机） |
| `mastery_score` | Float, nullable | 0.0 - 1.0 掌握度分数 |
| `completed_via` | String(20), nullable | `ai_assessment` / `parent_approval` |
| `attempts` | Integer, default 0 | 尝试次数 |
| `xp_earned` | Integer, default 0 | 累计获得的 XP |
| `last_practice_at` | DateTime, nullable | 最近练习时间 |
| `first_mastered_at` | DateTime, nullable | 首次掌握时间 |
| `stability` | Float, nullable | 记忆稳定性参数（间隔重复算法，初始 1.0） |
| `next_review_at` | DateTime, nullable | 下次复习日期（由间隔重复算法计算，见下方说明） |
| `ability_dimensions_score` | JSON, nullable | 各能力维度得分 `{"numerical_reasoning": 0.8, "spatial": 0.6}` |

**唯一约束：** `(child_id, topic_id)`

**`next_review_at` 计算机制（R-05 修复）：**

当 `mastery_level` 转为 `mastered` 时，由 service 层基于简化间隔重复算法计算：

```python
def compute_next_review(progress: LearningProgress) -> datetime:
    """基于 stability 计算下次复习日期（简化 SM-2）"""
    stability = progress.stability or 1.0
    # 间隔天数 = 基础间隔 × stability（首次 = 3 天，之后递增）
    interval_days = max(1, int(3 * stability))
    return datetime.utcnow() + timedelta(days=interval_days)

def update_stability(progress: LearningProgress, score: float) -> float:
    """复习后更新 stability：高分提升，低分降低"""
    current = progress.stability or 1.0
    if score >= 0.8:
        return min(current * 1.3, 10.0)  # 上限 10 倍（~30 天间隔）
    else:
        return max(current * 0.6, 1.0)   # 下限重置为 1（3 天间隔）
```

触发时机：
- AI 评估通过（`assessing → mastered`）：计算 `next_review_at`，更新 `stability`
- 家长审核通过（`parent_review → mastered`）：同上
- 复习通过（`review → mastered`）：`stability` 递增，`next_review_at` 延长
- 复习未通过（`review → learning`）：`stability` 重置

#### `mastery_level` 状态机

```
                    ┌─────────────────────────────────────────────┐
                    │                                             │
locked ──→ available ──→ learning ──→ assessing ──→ mastered ──[next_review_at 到期]──→ review
                        │              │            │                                        │
                        │              ↓            ↓                                        │
                        │        [score < threshold] review ←────────────────────────────────┘
                        │              │            │
                        │              └──→ learning ┘
                        │
                        └──→ parent_review ──→ mastered
                                │                  │
                                ↓                  ↓
                          [reject]            [review 期到]
                                │                  │
                                └──→ learning      └──→ learning
```

| 状态 | 含义 | 进入条件 |
|---|---|---|
| `locked` | 前置知识未满足 | 初始状态；hard prerequisite 未 mastered |
| `available` | 可以开始学习 | 所有 hard prerequisite 已 mastered |
| `learning` | 正在学习中 | 孩子开始学习 / 评估未通过 / 家长退回 |
| `assessing` | AI 评估中 | 仅当 family 启用 AI 助手 + 孩子确认进入评估模式（见 R-06 触发说明） |
| `parent_review` | 等待家长审核 | 无 AI 时的评估路径 / AI 关闭时的降级路径 |
| `mastered` | 已掌握 | AI 评估通过 / 家长 approve |
| `review` | 需要复习 | 评估未通过 / next_review_at 到期（由 lazy evaluation 检测） |

**`learning → assessing` 触发方式（R-06 修复）：**

转换不是自动的，需要两步：
1. **AI 提议：** 在 tutorial 对话中，AI tutor 根据对话轮次（≥4 轮交互）和 topic 复杂度判断准备度，向孩子发出评估邀请："你觉得准备好了吗？我们来试试几道小测验！"
2. **孩子确认：** 前端显示评估邀请卡片，孩子点击 [开始测验] → 后端调用 `POST /child/learning/sessions/{id}/start-assessment` → `mastery_level: learning → assessing`

如果孩子点击 [我还想再学学] → 保持 `learning`，AI 继续教学。
对于 `parent_review` 路径：孩子在学习完成后点击 [提交审核] → `learning → parent_review`。

**MVP 可达状态子集（F-23 修复）：** Phase 1 实际可达的状态路径：
- 无 AI 路径：`locked → available → learning → parent_review → mastered`
- AI 路径：`locked → available → learning → assessing → mastered`
- 评估未通过：`assessing → review → learning → assessing`（循环直到通过）
- `review` 的遗忘触发路径（`mastered → review`）需要调度器支持，Phase 1 实现为 lazy evaluation（在下次访问 progress 时检查 next_review_at 是否到期）

#### AI 助手启用条件逻辑

```python
def get_available_assessment_paths(family: Family) -> list[str]:
    """根据 family 的 AI 配置返回可用的评估路径"""
    paths = ["parent_approval"]  # 始终可用
    
    if family.ai_assistant_enabled:
        paths.append("ai_assessment")
    
    return paths


def can_use_ai_assessment(child_id: int, topic_id: int) -> bool:
    """
    判断是否可以使用 AI 评估：
    1. family 当前启用了 AI 助手，OR
    2. 该 progress 记录的 completed_via == "ai_assessment"（历史数据保护）
    """
    family = get_family_by_child(child_id)
    if family.ai_assistant_enabled:
        return True
    
    # 历史数据保护：曾经通过 AI 评估的，可以查看和复习
    progress = get_progress(child_id, topic_id)
    return progress and progress.completed_via == "ai_assessment"
```

### 3.3 学习任务层

#### `learning_assignment` 表

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger | Snowflake ID |
| `family_id` | BigInteger, FK → family.id | 家庭 |
| `child_id` | BigInteger, FK → user.id | 目标孩子 |
| `topic_id` | BigInteger, FK → learning_topic.id | 关联知识节点 |
| `path_id` | BigInteger, nullable | 所属学习路径（Phase 1 无 FK；Phase 2 创建 learning_path 后加 FK 约束） |
| `created_by` | BigInteger, FK → user.id | 创建者（家长 or system） |
| `assignment_type` | String(20) | `parent_assigned` / `ai_recommended` / `self_selected` |
| `status` | String(20) | `pending` / `in_progress` / `completed` / `skipped` |
| `priority` | Integer, default 0 | 优先级 |
| `due_date` | Date, nullable | 截止日期 |
| `created_at` | DateTime | 创建时间 |
| `completed_at` | DateTime, nullable | 完成时间 |

#### `learning_path` 表（Phase 2）

家长或 AI 创建的学习路径（topic 有序序列）。MVP 阶段不实现，预留字段。

#### `learning_session` 表

单次学习会话，关联 AI thread。

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger | Snowflake ID |
| `assignment_id` | BigInteger, FK → learning_assignment.id, nullable | 关联任务（自选学习时为 null） |
| `child_id` | BigInteger, FK → user.id | 孩子 |
| `topic_id` | BigInteger, FK → learning_topic.id | 知识节点 |
| `thread_id` | String(100), nullable | 关联的 DeerFlow AI thread ID |
| `session_type` | String(20) | `tutorial` / `assessment` |
| `ai_evaluation` | JSON, nullable | AI 评估结果 |
| `score` | Float, nullable | 本次得分 |
| `duration_seconds` | Integer, nullable | 学习时长 |
| `started_at` | DateTime | 开始时间 |
| `ended_at` | DateTime, nullable | 结束时间 |

**`ai_evaluation` JSON 结构：**

```json
{
    "evidence_results": [
        { "evidence": "Can add two-digit numbers", "met": true, "notes": "..." },
        { "evidence": "Understands carrying", "met": false, "notes": "..." }
    ],
    "overall_score": 0.8,
    "recommendation": "needs_review"
}
```

#### `learning_assessment_attempt` 表（Child Model 补充）

每次评估的详细记录，支撑纵向能力建模和间隔重复算法。

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | BigInteger | Snowflake ID |
| `child_id` | BigInteger, FK → user.id | 孩子 |
| `topic_id` | BigInteger, FK → learning_topic.id | 知识节点 |
| `session_id` | BigInteger, FK → learning_session.id, nullable | 关联学习会话 |
| `assessment_type` | String(20) | `ai_assessment` / `parent_approval` |
| `score` | Float, nullable | 本次评估得分 0.0-1.0 |
| `passed` | Boolean | 是否通过 |
| `ai_confidence` | Float, nullable | AI 评估置信度 0.0-1.0（家长审核时为 null） |
| `evidence_results` | JSON, nullable | 本次评估的 evidence 逐条结果 |
| `ability_dimensions_delta` | JSON, nullable | 本次评估对能力维度的增量 `{"numerical_reasoning": +0.1}` |
| `duration_seconds` | Integer, nullable | 评估耗时 |
| `created_at` | DateTime | 评估时间 |

**索引：** `(child_id, topic_id, created_at)` — 支持按时间线查询评估历史

---

## 4. API 设计

### 4.1 知识图谱查询（全局，无需 family 上下文）

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/learning/topics` | 查询 topics（支持 subject/domain/age_group 过滤） |
| GET | `/api/v1/learning/topics/{id}` | 单个 topic 详情 |
| GET | `/api/v1/learning/topics/{id}/graph` | 局部子图（前驱+后继节点） |
| GET | `/api/v1/learning/clusters` | 领域聚类摘要 |
| GET | `/api/v1/learning/subjects` | 学科列表 + 各学科 topic 数量 |

### 4.2 家长端（Main App，需 `require_adult`）

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/family/learning/children` | 列出所有孩子 + 学习概览 |
| GET | `/api/v1/family/learning/children/{child_id}/map` | 孩子的知识地图（含 mastery_level） |
| GET | `/api/v1/family/learning/children/{child_id}/progress` | 学习进度详情 |
| POST | `/api/v1/family/learning/assignments` | 派发学习任务 |
| GET | `/api/v1/family/learning/assignments` | 列出学习任务 |
| GET | `/api/v1/family/learning/reviews` | 待审核列表（parent_review 状态） |
| POST | `/api/v1/family/learning/reviews/{id}/approve` | 确认掌握 |
| POST | `/api/v1/family/learning/reviews/{id}/reject` | 退回重学 |

### 4.3 孩子端（Child App，需 `get_current_child_user`）

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/v1/child/learning/map` | 我的知识地图 |
| GET | `/api/v1/child/learning/assignments` | 我的学习任务 |
| GET | `/api/v1/child/learning/topics/{id}` | Topic 详情（含我的掌握度） |
| POST | `/api/v1/child/learning/sessions` | 创建学习会话（→ 触发 AI thread） |
| GET | `/api/v1/child/learning/sessions/{id}` | 查看学习会话 |
| POST | `/api/v1/child/learning/assignments/{id}/submit` | 提交任务（走 parent_review 路径） |
| POST | `/api/v1/child/learning/sessions/{id}/start-assessment` | 确认进入评估模式（`learning → assessing`，R-06 触发） |
| GET | `/api/v1/child/learning/progress` | 总体进度概览 |

### 4.4 后端路由注册（R-09 修复）

新增路由文件：

```
server/apps/backend/app/routers/learning.py          # 全局知识图谱查询
server/apps/backend/app/routers/learning_family.py   # 家长端学习管理
server/apps/backend/app/routers/learning_child.py    # 孩子端学习
```

Numina 路由为手动注册（无自动发现）。需在 `server/apps/backend/app/main.py` 中添加：

```python
from apps.backend.app.routers import learning as learning_router
from apps.backend.app.routers import learning_family as learning_family_router
from apps.backend.app.routers import learning_child as learning_child_router

app.include_router(learning_router.router, prefix="/api/v1")
app.include_router(learning_family_router.router, prefix="/api/v1")
app.include_router(learning_child_router.router, prefix="/api/v1")
```

同时需在 `server/packages/db/models/__init__.py` 的 `__all__` 中注册所有新模型（LearningTopic, LearningDependency, LearningCluster, LearningProgress, LearningAssignment, LearningSession, LearningAssessmentAttempt）。

---

## 5. AI Agent 集成

### 5.1 新增 AI Skill: `learning-tutor`

文件：`server/apps/agent/skills/builtin/public/learning-tutor/SKILL.md`

```yaml
---
name: learning-tutor
description: |
  AI learning tutor for children. Conducts tutorial sessions and 
  assessments based on knowledge graph topics. Uses the topic's 
  description, evidence criteria, and assessment prompt to guide 
  the conversation.
trigger_phrases:
  - /learn
  - /tutor
allowed-tools:
  - get_learning_topic
  - get_child_learning_profile
  - record_learning_result
thinking: true
max_tokens: 8000
---

## Role

You are a friendly, patient AI learning tutor for children aged 6-12.

## Behavior

1. Read the topic details (name, description, evidence, assessment_prompt)
2. Start with a warm greeting using the child's name
3. Explain the concept in age-appropriate language
4. Use examples, analogies, and interactive questions
5. For assessment mode: evaluate each evidence criterion through conversation
6. Provide encouraging feedback throughout
7. At the end, output a structured evaluation result

## Output Format (Assessment)

After completing the session, output the evaluation as JSON:

```json
{
    "evidence_results": [
        { "evidence": "<evidence text>", "met": true/false, "notes": "..." }
    ],
    "overall_score": 0.0-1.0,
    "recommendation": "mastered" | "needs_review" | "keep_learning"
}
```

## Tone

- Warm, encouraging, never condescending
- Use simple words appropriate for the child's age
- Celebrate effort, not just correctness
- When wrong, guide don't tell
```

### 5.2 新增 MCP Tools

Backend 提供给 Agent 的工具：

```python
# get_learning_topic
async def get_learning_topic(topic_id: str, child_id: str) -> dict:
    """获取 topic 详情 + 孩子的掌握度"""
    
# get_child_learning_profile  
async def get_child_learning_profile(child_id: str, subject: str = None) -> dict:
    """获取孩子学习画像：已掌握/进行中/待解锁的 topic 统计"""

# record_learning_result
async def record_learning_result(
    session_id: str, 
    evaluation: dict
) -> dict:
    """记录 AI 评估结果，更新 learning_progress，触发奖励"""
```

### 5.3 AI 对话流程

```
孩子点击 topic → POST /child/learning/sessions
    ↓
Backend:
  1. 创建 learning_session 记录
  2. 构建 metadata: { app: "learning-tutor", topic_id, child_id, session_id, mode }
  3. 调用 Agent stream_run(metadata=...)
  4. 返回 AI thread_id 给前端
    ↓
Frontend:
  复用现有 useThreadChat composable
  通过 SSE 接收 DeerFlow 流式对话
    ↓
对话结束后:
  Agent 输出结构化评估 JSON（通过 DeerFlow 最终消息解析）
  → Backend 在 stream 结束时提取评估结果
  → 更新 learning_progress (mastery_level, mastery_score)
  → 创建 learning_assessment_attempt 记录
  → 创建 CoinTransaction (type: learning_earn)
  → 发送通知给家长
```

**AI 教学内容策略（F-24 修复）：**

Phase 1 中 AI tutor 需要同时承担"教"和"评"两个角色。教学素材来源：
1. **topic.description + description_zh** — 概念解释的基础
2. **topic.evidence + evidence_zh** — 评估标准，也是教学重点
3. **topic.assessment_prompt + assessment_prompt_zh** — 评估引导语
4. **AI 自身知识** — LLM 基于 topic 元数据生成示例、类比、互动问题

为提升教学质量，SKILL.md 中要求 AI：
- 每节课至少包含 2 个具体示例（由 AI 根据 topic 动态生成）
- 使用孩子年龄匹配的语言和比喻（披萨分片、积木分组等）
- 评估前明确告知 "现在来做几道练习题"（模式切换信号）

### 5.4 非 AI 路径（家长审核）

```
孩子完成学习 → POST /child/learning/assignments/{id}/submit
    ↓
Backend: mastery_level → "parent_review"
    ↓
通知家长
    ↓
家长在审核页面看到（F-16 修复：增强决策支持）:
  - topic 名称 + 中文描述
  - evidence 列表（掌握度证据，中文翻译）
  - 孩子学习时长 + 尝试次数
  - 💡 家长友好的掌握度说明（如："您的孩子是否能独立完成以下任务？"）
  - 📋 参考问题（2-3 个家长可以用来口头测试孩子的问题）
    ↓
家长 approve → mastery_level = "mastered", completed_via = "parent_approval"
             → 创建 learning_assessment_attempt (assessment_type="parent_approval")
             → 触发 coin 奖励 + 通知
家长 reject  → mastery_level = "learning"
             → 通知孩子退回
```

**防止橡皮图章机制：**
- 审核页面默认折叠 "快速通过" 按钮，需要先展开 evidence 详情才能操作
- 如果孩子 learning 时间 < 3 分钟就提交，显示提醒："学习时长较短，建议先和孩子聊聊这个知识点"

**并发安全保障（R-12 修复）：**

镜像现有 chore approval 的原子 CAS 模式（`services/chores.py` 中的 `approve_instance_async`）：
- approve/reject 使用 raw SQL `UPDATE ... WHERE mastery_level = 'parent_review'` 实现 compare-and-swap
- 状态已变更时返回 409 Conflict（避免重复审核）
- 副作用（coin 奖励、通知、assessment_attempt 创建）采用 best-effort 模式（try/except 包裹，不阻塞主流程）
- 所有操作在单个 `db.commit()` 中原子提交

---

## 6. 前端设计

### 6.1 Child App 页面

#### 入口

在 Child App 现有 5 tab 基础上，在 Home 页面增加「今日学习」卡片入口。
点击进入学习地图页面 `/learning`。

（Phase 2 考虑增加独立 tab）

#### 页面清单

| Route | Page | 说明 |
|---|---|---|
| `/learning` | LearningMapPage | 知识地图（学科 tabs + 节点可视化） |
| `/learning/topic/:id` | LearningTopicPage | Topic 详情 + 开始学习 |
| `/learning/session/:id` | LearningSessionPage | AI 对话（复用 AI chat 组件） |
| `/learning/progress` | LearningProgressPage | 我的学习进度 |

#### LearningMapPage

**MVP 可视化策略：** 按 domain 分组的 grid 视图（非节点图）。节点图作为 Phase 2 增强。

```
┌──────────────────────────────────────────┐
│  学科横滑选择器                            │
│  [数学] [科学] [英语] [历史] [生活] ...    │
│  (仅展示该孩子有 available/mastered topic 的学科) │
├──────────────────────────────────────────┤
│                                          │
│  📐 分数 (3/5 已掌握)                     │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐    │
│  │✅ 通分│ │✅ 约分│ │🔵 加法│ │🔒 减法│    │
│  └──────┘ └──────┘ └──────┘ └──────┘    │
│                                          │
│  📐 小数 (1/4 已掌握)                     │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐    │
│  │⭐ 概念│ │🔒 加法│ │🔒 减法│ │🔒 乘法│    │
│  └──────┘ └──────┘ └──────┘ └──────┘    │
│                                          │
│  图例: ✅available 🔵learning ⭐mastered   │
│        🔒locked 🟡review                  │
│                                          │
├──────────────────────────────────────────┤
│  📋 今日推荐                              │
│  ┌────────────────────────────────┐      │
│  │ 📖 分数加法 (家长派发)    开始 → │      │
│  └────────────────────────────────┘      │
└──────────────────────────────────────────┘
```

**空状态：** 首次进入时显示 "🎉 开始你的学习之旅！家长可以为你指派任务，或者选择一个学科自由探索。" + [去选择学科] 按钮。

#### LearningTopicPage

```
┌──────────────────────────────────────────┐
│  ← 分数加法                               │
│  数学 > 分数                                │
├──────────────────────────────────────────┤
│                                          │
│  掌握度: ████████░░ 80%                   │
│  状态: 学习中                              │
│                                          │
├──────────────────────────────────────────┤
│  📝 简介                                  │
│  学习如何将两个分数相加...                   │
│                                          │
│  🔓 前置知识                               │
│  ✅ 分数的概念                              │
│  ✅ 通分                                   │
│                                          │
│  🔒 解锁后                                 │
│  🔜 带分数加法                              │
│  🔜 分数减法                               │
│                                          │
├──────────────────────────────────────────┤
│  [ 🎓 开始学习 ]  [ 📝 提交审核 ]          │
└──────────────────────────────────────────┘
```

#### 页面状态覆盖（F-17/F-18 修复）

| 页面 | 空状态 | 加载状态 | 错误状态 |
|------|--------|----------|----------|
| LearningMapPage | "开始你的学习之旅！" + 引导按钮 | Skeleton grid（domain 分组骨架） | "加载失败，点击重试" |
| LearningTopicPage | N/A（必须有 topic 才能进入） | 详情页骨架屏 | "该知识点暂不可用" |
| LearningSessionPage | N/A | "正在连接 AI 导师…" 动画 | "AI 连接超时，请稍后重试或选择家长审核模式" |
| LearningProgressPage | "还没有学习记录哦，快去学习吧！" | 进度骨架屏 | "加载失败，点击重试" |
| BabyLearningPage | "添加孩子后即可查看学习进度" | 孩子卡片骨架 | "加载失败" |
| LearningReviewsPage | "🎉 没有待审核的任务" | 列表骨架 | "加载失败" |

#### 学科 Tab 行为（F-19 修复）

- **隐藏规则：** 当孩子在该学科无任何 available/learning/mastered topic 时，隐藏该学科 tab
- **计数徽章：** 每个 tab 显示该学科 available topic 数量（如 `数学 (5)`）
- **首次进入：** 默认选中孩子有最多 available topic 的学科

#### 年龄分层 UX（F-11 修复）

基于 `age_group` 字段（由孩子年龄计算）适配 UI：

| 层级 | 年龄 | 适配策略 |
|------|------|----------|
| Low | 5-7 | 大图标 + 大按钮（最小触摸目标 48px）、最小字号 18px、语音辅助（可选）、最少文字、纯视觉进度指示（颜色/图标） |
| Mid | 8-10 | 引导式文字 + 视觉辅助、最小字号 16px、触摸目标 44px、可阅读 evidence 描述 |
| High | 11+ | 近成人文字 UI、最小字号 14px、标准触摸目标、可查看所有详情和统计 |

#### AI 会话流程设计（F-13 修复）

```
孩子点击 [开始学习] 
    ↓
LearningSessionPage 加载
    ↓
┌────────────────────────────────────┐
│  🎓 分数加法 — 学习模式              │ ← 蓝色顶栏标识
│                                      │
│  AI: "嗨 {name}！今天我们一起来学     │
│       分数加法吧！你听说过分数吗？"     │ ← 辅导阶段（tutorial）
│                                      │
│  [对话交互...]                        │
│                                      │
│  ── AI 检测到准备好评估 ──            │ ← 过渡信号
│                                      │
│  ┌──────────────────────────────┐    │
│  │  📝 现在来几个小测验吧！       │    │ ← 视觉切换：顶栏变橙色
│  │  （共 3 题，加油！）           │    │
│  └──────────────────────────────┘    │
│                                      │
│  [评估交互...]                        │ ← 评估阶段（assessment）
│                                      │
│  ── 评估结束 ──                       │
│                                      │
│  ┌──────────────────────────────┐    │
│  │  🎉 太棒了！你完成了！         │    │
│  │  得分: 4/5  ⭐ +10 coins      │    │ ← 结果画面
│  │  [查看下一题] [返回地图]       │    │
│  └──────────────────────────────┘    │
└────────────────────────────────────┘
```

**评估失败体验设计（F-20 修复）：**
- AI 不说 "你错了"，而是说 "这个我们再想想？" — 成长心态措辞
- 结果页面显示 "继续学习中 📖" 而非分数（低龄组）/ 显示具体得分（高龄组）
- 失败不通知家长（避免压力），只记录到 assessment_attempt 供家长主动查看
- 连续 3 次未通过 → 建议家长介入（推送通知）

### 6.2 Main App 页面（家长端）

| Route | Page | 说明 |
|---|---|---|
| `/baby/learning` | BabyLearningPage | 孩子学习概览 |
| `/baby/learning/:childId/map` | ChildLearningMapPage | 孩子的知识地图 |
| `/baby/learning/assign` | LearningAssignPage | 派发学习任务 |
| `/baby/learning/reviews` | LearningReviewsPage | 审核队列 |

#### BabyLearningPage

```
┌──────────────────────────────────────────┐
│  学习管理                                  │
├──────────────────────────────────────────┤
│                                          │
│  ┌─ 小明 (10岁) ──────────────────────┐  │
│  │ 已掌握: 42  学习中: 5  待开始: 12   │  │
│  │ [查看地图]  [派发任务]              │  │
│  └────────────────────────────────────┘  │
│                                          │
│  ┌─ 小红 (7岁) ───────────────────────┐  │
│  │ 已掌握: 18  学习中: 3  待开始: 8    │  │
│  │ [查看地图]  [派发任务]              │  │
│  └────────────────────────────────────┘  │
│                                          │
│  📋 待审核 (2)                            │
│  ┌────────────────────────────────────┐  │
│  │ 小明: 分数加法 → 待审核             │  │
│  │ 小红: 乘法口诀 → 待审核             │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

---

## 7. Gamification 整合

### 7.1 Coin 奖励

复用现有 `CoinTransaction` 系统，新增 transaction type：

```python
# 新增 transaction_type 枚举值（实际为 String(20)，应用层约定，无需 migration）
"learning_earn"  # 掌握度达成时奖励
```

**幂等性保障（R-04 修复）：**

现有 `CoinTransaction` 有唯一约束 `UniqueConstraint("ref_id", "transaction_type")`。学习场景：
- `ref_id = learning_assessment_attempt.id`（每次评估尝试产生最多一笔 coin 交易）
- 通过 `parent_approval` 路径时同理：`ref_id = learning_assessment_attempt.id`
- 这确保同一评估结果不会因重试/并发导致重复发币

**`ref_type` 属性扩展：**

现有 `CoinTransaction.ref_type` property 映射 `transaction_type → entity_type`。需新增：
```python
"learning_earn" → "learning_assessment_attempt"
```

奖励规则（可配置）：
- 首次掌握一个 topic: 基础 coins（按 topic 难度/类型）
- streak bonus: 连续学习天数加成
- AI 评估高分 bonus: score > 0.9 额外奖励

### 7.2 学习徽章（F-21 修复：复用现有模型）

**直接扩展现有 `LiteracyBadgeDefinition` 模型**（而非新建独立徽章系统），让孩子看到统一的徽章墙：

```python
# 在现有 LiteracyBadgeDefinition 中新增学术维度
# 现有: dimension = "earning" | "choosing" | "waiting" | "caring"
# 新增: dimension = "mathematics" | "science" | "english" | "history" | ... | "comprehensive"

NEW_BADGE_DEFINITIONS = [
    # 大科目（topic 数 > 200）：阈值 10/30/60
    # 数学 (503 topics)
    { "dimension": "mathematics", "level": 1, "name": "小数学家", "criteria_summary": "掌握 10 个数学 topic" },
    { "dimension": "mathematics", "level": 2, "name": "数学达人", "criteria_summary": "掌握 30 个数学 topic" },
    { "dimension": "mathematics", "level": 3, "name": "数学大师", "criteria_summary": "掌握 60 个数学 topic" },
    # 科学 (547 topics)
    { "dimension": "science", "level": 1, "name": "小科学家", "criteria_summary": "掌握 10 个科学 topic" },
    { "dimension": "science", "level": 2, "name": "科学达人", "criteria_summary": "掌握 30 个科学 topic" },
    { "dimension": "science", "level": 3, "name": "科学大师", "criteria_summary": "掌握 60 个科学 topic" },
    # 英语 (286 topics)
    { "dimension": "english", "level": 1, "name": "小文学家", "criteria_summary": "掌握 10 个英语 topic" },
    { "dimension": "english", "level": 2, "name": "英语达人", "criteria_summary": "掌握 25 个英语 topic" },
    { "dimension": "english", "level": 3, "name": "英语大师", "criteria_summary": "掌握 50 个英语 topic" },
    # 中科目（topic 数 50-200）：阈值 5/15/30
    # 历史 (90 topics)
    { "dimension": "history", "level": 1, "name": "小历史学家", "criteria_summary": "掌握 5 个历史 topic" },
    { "dimension": "history", "level": 2, "name": "历史达人", "criteria_summary": "掌握 15 个历史 topic" },
    { "dimension": "history", "level": 3, "name": "历史大师", "criteria_summary": "掌握 30 个历史 topic" },
    # 个人与社会 (88 topics)
    { "dimension": "personal_social", "level": 1, "name": "社交小达人", "criteria_summary": "掌握 5 个社交 topic" },
    { "dimension": "personal_social", "level": 2, "name": "社交达人", "criteria_summary": "掌握 15 个社交 topic" },
    { "dimension": "personal_social", "level": 3, "name": "社交大师", "criteria_summary": "掌握 30 个社交 topic" },
    # 小科目（topic 数 < 50）：阈值 3/8/15（R-07 修复）
    # 生活技能 (37 topics)
    { "dimension": "life_skills", "level": 1, "name": "生活小能手", "criteria_summary": "掌握 3 个生活技能 topic" },
    { "dimension": "life_skills", "level": 2, "name": "生活达人", "criteria_summary": "掌握 8 个生活技能 topic" },
    { "dimension": "life_skills", "level": 3, "name": "生活大师", "criteria_summary": "掌握 15 个生活技能 topic" },
    # 计算 (21 topics)
    { "dimension": "computing", "level": 1, "name": "小编程师", "criteria_summary": "掌握 3 个计算 topic" },
    { "dimension": "computing", "level": 2, "name": "编程达人", "criteria_summary": "掌握 8 个计算 topic" },
    { "dimension": "computing", "level": 3, "name": "编程大师", "criteria_summary": "掌握 15 个计算 topic" },
    # 学习方法 (18 topics)
    { "dimension": "learning_to_learn", "level": 1, "name": "学习新手", "criteria_summary": "掌握 3 个学习方法 topic" },
    { "dimension": "learning_to_learn", "level": 2, "name": "学习达人", "criteria_summary": "掌握 8 个学习方法 topic" },
    { "dimension": "learning_to_learn", "level": 3, "name": "学习大师", "criteria_summary": "掌握 15 个学习方法 topic" },
    # 综合维度（跨学科）
    { "dimension": "comprehensive", "level": 1, "name": "学习新星", "criteria_summary": "总掌握 20 个 topic" },
    { "dimension": "comprehensive", "level": 2, "name": "学习达人", "criteria_summary": "总掌握 50 个 topic" },
    { "dimension": "comprehensive", "level": 3, "name": "学习之王", "criteria_summary": "总掌握 100 个 topic" },
]

# LiteracyBadge 的 source 字段记录来源: "learning" (新增) vs "scenario" / "passive" (现有)
```

**好处：** 孩子在一个徽章页面看到所有成就（财商 + 学术），而非在多个独立系统中碎片化。

**Phase 1/2 分界：** Phase 1 中 mastery 达成时仅记录 badge 进度数据（不实际颁发）；Phase 2 新增 badge 自动评估逻辑 + 前端徽章墙展示。

### 7.3 XP 系统（Phase 2）

预留 XP 字段，Phase 1 暂不实现等级系统。

---

## 8. 种子数据导入

### 8.1 导入脚本

`server/scripts/seed_learning_topics.py`

从 os-taxonomy JSON 文件导入到数据库，并生成中文翻译：

```python
# 伪代码
def seed_learning_topics():
    topics_data = json.load(open("os-taxonomy/data/topics.json"))
    deps_data = json.load(open("os-taxonomy/data/dependencies.json"))
    clusters_data = json.load(open("os-taxonomy/data/clusters.json"))
    
    # 1. 导入 topics（全局，family_id = NULL）
    for t in topics_data:
        # 生成中文翻译（LLM 辅助，批量处理）
        zh_translations = await translate_topic(t)  # → {name_zh, description_zh, evidence_zh, assessment_prompt_zh}
        
        LearningTopic.upsert(
            topic_key=t["id"],
            topic_type=t["type"],
            subject=t["subject"],
            domain=t.get("domain"),
            name=t.get("name"),
            name_zh=zh_translations["name_zh"],
            description=t.get("description", ""),
            description_zh=zh_translations["description_zh"],
            age_range_start=t.get("ageRangeStart"),
            age_range_end=t.get("ageRangeEnd"),
            centrality=t.get("centrality"),
            evidence=t.get("evidence", []),
            evidence_zh=zh_translations["evidence_zh"],
            assessment_prompt=t.get("assessmentPrompt"),
            assessment_prompt_zh=zh_translations["assessment_prompt_zh"],
            standards=t.get("standards", []),  # R-03 修复：保留课程标准关联
            ability_dimensions=ability_dims[t["id"]],  # R-02 修复：LLM 推导
            age_group=compute_age_group(t.get("ageRangeStart")),
        )
    
    # 2. 导入 dependencies
    for d in deps_data:
        topic = LearningTopic.get_by_key(d["topicId"])
        prereq = LearningTopic.get_by_key(d["prerequisiteId"])
        LearningDependency.insert(
            topic_id=topic.id,
            prerequisite_id=prereq.id,
            strength=d["strength"],
            reason=d.get("reason", ""),
        )
    
    # 3. 导入 clusters
    for c in clusters_data:
        LearningCluster.upsert(
            subject=c["subject"],
            domain=c["domain"],
            age_range_start=c["ageRangeStart"],  # R-10 修复：保留原始年龄
            age_group=compute_age_group(c["ageRangeStart"]),
            summary=c["summary"],
        )
```

**翻译管线说明（R-11 修复：规模估算）：**

- 使用 LLM（DashScope/OpenAI）批量翻译 topic name、description、evidence、assessment_prompt
- 翻译结果缓存在 `*_zh` 字段中，避免运行时翻译开销
- 学科专业术语保留英文（如 fraction、algebra），在翻译 prompt 中指定
- 翻译质量由开发者人工抽检（至少每个学科抽样 10%）

**规模估算：**
- 1,590 topics × 4 个翻译字段 = ~6,360 次翻译
- 每次约 200-500 tokens（input + output），总计约 1.3M - 3.2M tokens
- 按学科分批处理（8 批），每批 ~200 topics
- 预计耗时：使用 DashScope qwen-plus 约 5-10 分钟（batch 并发），成本 < ¥10
- `ability_dimensions` 推导同上，每 topic ~300 tokens

**批处理策略：**
```python
async def translate_batch(topics: list[dict], batch_size: int = 50):
    """按批次翻译，避免 rate limit"""
    for i in range(0, len(topics), batch_size):
        batch = topics[i:i+batch_size]
        results = await asyncio.gather(*[translate_topic(t) for t in batch])
        save_translations(results)
        await asyncio.sleep(1)  # rate limit 保护
```

### 8.2 知识图谱质量验证（F-25 修复）

os-taxonomy 数据导入后需验证质量，避免错误依赖链影响学习路径：

**验证步骤：**
1. **依赖完整性检查：** 确保所有 dependency 引用的 topic_key 都存在（孤儿边检测）
2. **年龄范围合理性：** 抽样每个学科 10 个 topic，验证 age_range 是否符合中国小学课标
3. **依赖方向抽检：** 每个学科随机 5 条 dependency，人工验证 "prerequisite → topic" 方向是否正确
4. **标记验证状态：** 可选添加 `quality_reviewed: Boolean` 字段，未验证 topic 在前端标记 "未审核"

**版本管理（F-16 修复）：**
- 种子数据记录 os-taxonomy 版本（release tag 或 commit hash）
- 提供 `reseed_learning_topics --version <tag>` 命令支持增量更新
- 更新策略：upsert（topic_key 匹配则更新字段，新增则 insert，已删除的 topic 标记 `deprecated=True` 而非物理删除，保护已有 learning_progress 引用）

### 8.3 Alembic Migration

新增 migration 文件创建所有新表。种子数据导入作为 migration 的 `upgrade()` 一部分或独立 CLI 命令。

---

## 9. MVP 实施范围

### Phase 1 (MVP)

| 组件 | 内容 | 优先级 |
|---|---|---|
| DB Migration | 7 张新表（topic, dependency, cluster, progress, assignment, session, assessment_attempt）+ learning_topic 中文翻译字段 | P0 |
| Seed Script | os-taxonomy → DB 导入 + LLM 辅助中文翻译管线 | P0 |
| Backend: 知识图谱 API | topics 查询、子图查询 | P0 |
| Backend: 学习任务 API | 派发、进度、提交 | P0 |
| Backend: 家长审核 API | approve/reject | P0 |
| Backend: worker.py runner | 新增 learning-tutor runner 分支 + RESERVED_NAMES 注册 | P0 |
| AI Skill | `learning-tutor` + MCP tools（中文对话优先） | P0 |
| Frontend: Child App | useThreadChat 适配/提取 + 学习地图 + topic 详情 + AI 对话 | P0 |
| Frontend: Main App | 学习概览 + 任务派发 + 审核 | P0 |
| i18n | 前端 locale 文件（zh-CN / en）+ API 返回翻译字段 | P0 |
| Coin 奖励 | learning_earn transaction | P1 |
| 通知 | 任务派发/完成/审核通知 | P1 |

### Phase 2

| 组件 | 内容 |
|---|---|
| 自适应推荐 | 基于 prerequisite DAG + 掌握度的路径推荐 |
| 学习徽章 | 学习维度徽章定义 + 自动评估 |
| 家长洞察 | 能力雷达图、成长趋势、学习时长统计 |
| learning_path | 学习路径创建和管理 |
| XP 系统 | 经验值 + 等级 |

### Phase 3

| 组件 | 内容 |
|---|---|
| 内容生成引擎 | AI 根据 topic 自动生成练习题、故事、实验 |
| 兴趣驱动探索 | 孩子自由选择探索方向（非指派模式） |
| 跨模块 Child Model | chore + literacy + learning → 统一成长模型 |
| 社交学习 | 家庭间分享、学习小组 |

---

## 10. 文件结构

### Backend

```
server/
  packages/
    db/models/
      learning/
        __init__.py
        topic.py          # LearningTopic, LearningDependency, LearningCluster
        progress.py       # LearningProgress
        assignment.py     # LearningAssignment, LearningPath
        session.py        # LearningSession, LearningAssessmentAttempt
  apps/
    backend/
      app/
        routers/
          learning.py           # 全局知识图谱查询
          learning_family.py    # 家长端
          learning_child.py     # 孩子端
        schemas/
          learning.py           # 请求/响应 schema
        services/
          learning/
            __init__.py
            topic_service.py    # 知识图谱查询逻辑
            progress_service.py # 进度计算、状态机转换
            assignment_service.py
            session_service.py  # 学习会话管理
            seed.py             # os-taxonomy 导入 + 翻译管线
            translation.py      # LLM 辅助中文翻译服务
  apps/
    agent/
      skills/
        builtin/
          public/
            learning-tutor/
              SKILL.md
```

### Frontend

```
frontend/
  apps/
    child/
      src/
        pages/
          learning/
            LearningMapPage.vue
            LearningTopicPage.vue
            LearningSessionPage.vue
            LearningProgressPage.vue
        api/
          learning.ts
        components/
          learning/
            SubjectTabs.vue
            TopicNode.vue       # 知识地图中的节点
            KnowledgeMap.vue    # 知识地图可视化
            MasteryBadge.vue
    main/
      src/
        pages/
          baby/
            BabyLearningPage.vue
            ChildLearningMapPage.vue
            LearningAssignPage.vue
            LearningReviewsPage.vue
        api/
          learning.ts
```

---

## 11. 关键设计决策记录

| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| 1 | 与 literacy 系统的关系 | 并行扩展 | 正交功能，独立迭代 |
| 2 | 与 chore 系统的关系 | 独立模型 + 共享激励 | 不同状态机，共享 gamification |
| 3 | 知识图谱存储 | 全局共享（非 per-family） | 公共知识，节省存储 |
| 4 | AI 评估条件 | 根据 family AI 开关动态路由 | 未启用 AI 的家庭走家长审核 |
| 5 | AI 对话通道 | 复用 DeerFlow SSE | 避免重复造轮子 |
| 6 | 评估双路径 | AI assessment + parent review | 覆盖有无 AI 的场景 |
| 7 | 历史数据保护 | 曾启用 AI 的历史记录保留 | 关闭 AI 不影响已有数据 |
| 8 | 语言策略 | 英文原文 + 中文翻译字段 + i18n | 学科术语保留英文，交互信息优先中文 |
| 9 | Child Model 数据支撑 | assessment_attempt + stability + ability_dimensions | 纵向建模需要评估历史和间隔重复参数 |
| 10 | path_id FK 时机 | Phase 1 无 FK，Phase 2 加约束 | learning_path 表 Phase 2 才创建 |
| 11 | 范围策略 | 不裁剪，分段实施 | 接受较长实施周期，保持完整愿景 |

---

## 12. 风险和开放问题

| 风险 | 影响 | 缓解 |
|---|---|---|
| ~~os-taxonomy 仅英文~~ | ~~中文用户需要翻译~~ | ✅ 已决策：Phase 1 包含 LLM 辅助翻译管线 + i18n 支持 |
| 知识地图可视化复杂 | MVP 可能无法实现漂亮的图 | MVP 用简化列表/网格视图（按 domain 分组的 grid） |
| AI 评估质量 | 错误的评估影响学习体验 | assessmentPrompt 精心设计 + 家长可覆盖 + ai_confidence 置信度字段 |
| 1,590 topics 导入性能 | 首次导入可能慢 | 批量 INSERT，一次性操作 |
| AI 评估可靠性无实证 | LLM 可能系统性误判掌握度 | 新增 `ai_confidence` 字段 + `learning_assessment_attempt` 历史追踪，Phase 1 后评估 AI-专家一致率 |

**开放问题：**
- [x] ~~是否需要支持中文知识图谱？~~ → 已决策：Phase 1 翻译 + i18n
- [ ] 学习时长统计是否需要？（防沉迷考虑）
- [ ] 多个孩子之间是否需要学习 PK/协作？
- [ ] os-taxonomy 许可证是否允许嵌入自托管产品？

---

## 13. 审查决策记录（2026-09-22 Review）

以下决策来自多角色文档审查（ce-doc-review，7 persona + 代码库验证）：

| # | 发现 | 决策 | 影响 |
|---|------|------|------|
| F-01 | os-taxonomy 英文阻断中文用户 | Phase 1 包含翻译管线 + i18n | 新增 `*_zh` 字段、翻译管线、i18n 工作项 |
| F-02 | 产品类别冲突（学习嵌入财务 App） | 论证在 Numina 内的合理性 | 新增 "为什么在 Numina 内部" 段落 + 收敛接口定义 |
| F-03 | Child Model 愿景与数据模型脱节 | 补充数据模型 | 新增 `learning_assessment_attempt` 表、`stability`/`next_review_at`/`ability_dimensions_score` 字段 |
| F-04 | AI 评估可靠性无实证 | 新增置信度追踪 | `ai_confidence` 字段 + attempt 历史 |
| F-05 | 知识地图可视化未定 | MVP = grid（按 domain 分组） | 重绘 LearningMapPage 线框图，节点图推迟到 Phase 2 |
| F-06 | review 状态遗忘路径缺失 | 补充状态图 | `mastered →[next_review_at 到期]→ review` 转换 + lazy evaluation |
| F-07 | 表数量 5 vs 6 不一致 | 修正为实际数量 | Phase 1 共 7 张表（含 assessment_attempt） |
| F-08 | path_id FK 引用 Phase 2 表 | Phase 1 无 FK | `path_id` 改为 plain nullable BigInteger |
| F-09 | useThreadChat 不存在于 Child App | 明确工作项 | Phase 1 包含 useThreadChat 适配/提取 |
| F-10 | worker.py runner 分支未提及 | 明确工作项 | Phase 1 包含 worker.py + RESERVED_NAMES 注册 |
| F-11 | 6-12 岁无 UX 分层 | 三层年龄适配 | 新增 Low/Mid/High UI 适配表（字号、触摸目标、文字密度） |
| F-12 | MVP 范围膨胀 | 不裁剪，分段实施 | 用户决策接受完整范围 |
| F-13 | AI 会话→评估转换无设计 | 补充会话流程设计 | 新增 tutorial→assessment 模式切换视觉设计 |
| F-14 | 学习未融入日常流程 | 定义整合契约 | 新增 "与现有日常流程的整合契约" 表 |
| F-15 | Coin 触发时机矛盾 | 统一为"掌握度达成时" | Section 2.2 + 7.1 对齐 |
| F-16 | 家长审核缺决策支持 | 增强审核页面 | 新增参考问题、掌握度说明、防橡皮图章机制 |
| F-17/18 | 页面缺空状态/加载/错误 | 补充全部页面状态 | 新增 "页面状态覆盖" 表（6 页面 × 3 状态） |
| F-19 | 学科 tab 空行为未定义 | 隐藏空学科 + 计数徽章 | 新增 "学科 Tab 行为" 段落 |
| F-20 | 评估失败缺情感设计 | 成长心态 + 分层展示 | 低龄不显示分数、失败不主动通知家长、3 次失败才建议介入 |
| F-21 | 徽章系统碎片化 | 复用 LiteracyBadgeDefinition | 学术维度扩展现有模型而非新建独立系统 |
| F-22 | 未定义孩子实际体验 | 补充典型旅程 | 新增 "孩子的典型学习旅程" 完整 walkthrough |
| F-23 | 7 状态机过度设计 | 文档化 MVP 可达子集 | 新增 "MVP 可达状态子集" 段落，lazy evaluation 实现 review |
| F-24 | 系统能评估不能教 | 定义教学素材来源 | AI 教学内容策略段落 + SKILL.md 要求 |
| F-25 | 知识图谱质量未验证 | 新增验证步骤 | Section 8.3 质量验证 + 版本管理 + reseed 命令 |
| F-26 | 并行架构→未来返工 | 定义收敛接口 | 新增 `ChildCapabilitySignal` 结构定义（Phase 3 准备） |

---

## 14. 二轮审查记录（Second-Pass Review, 2026-09-22）

基于 os-taxonomy 实际数据验证 + Numina 代码库模式对照，发现并修复 12 项问题：

| # | 发现 | 严重程度 | 修复 | 影响位置 |
|---|------|---------|------|---------|
| R-01 | 表数量 "8 张" 实为 7 张 | 🔴 正确性 | 修正为 7 | Section 9, Section 13 F-07 |
| R-02 | `ability_dimensions` 无数据来源 | 🔴 正确性 | 定义 LLM 推导规则 + 10 个预定义维度 | Section 3.1 learning_topic 表 + seed 伪代码 |
| R-03 | `standards` 必填字段未映射 | 🔴 正确性 | 新增 `standards` JSON 列 | Section 3.1 learning_topic 表 + seed 伪代码 |
| R-04 | CoinTransaction 幂等 ref_id 未定义 | 🔴 正确性 | 定义 `ref_id = learning_assessment_attempt.id` | Section 7.1 |
| R-05 | `next_review_at` 设置机制缺失 | 🟡 设计缺口 | 补充简化 SM-2 算法 + 触发时机 | Section 3.2 progress 表后 |
| R-06 | `learning → assessing` 触发未定义 | 🟡 设计缺口 | 定义 AI 提议 + 孩子确认两步触发 | Section 3.2 状态机表后 |
| R-07 | 徽章阈值不适配小科目 | 🟡 设计缺口 | 按科目规模分三档阈值（大/中/小） | Section 7.2 完整列出 8 学科 + 综合 |
| R-08 | Cluster 与 Topic 无直接映射 | 🟡 设计缺口 | 明确 cluster 用途 + 动态关联策略 | Section 3.1 cluster 表后 |
| R-09 | 缺少 main.py 路由注册步骤 | 🟢 补充 | 补充注册代码 + model registry 注册 | Section 4.4 |
| R-10 | cluster 表缺 `age_range_start` 原始字段 | 🟢 补充 | 新增列 + seed 更新 | Section 3.1 cluster 表 + seed 伪代码 |
| R-11 | 翻译管线缺规模估算 | 🟢 补充 | 补充 token 估算 + 批处理策略 | Section 8.1 |
| R-12 | 学习审核缺原子 CAS 模式 | 🟢 补充 | 镜像 chore approval CAS 模式 | Section 5.4 |

**综合检查附加修复：**

| # | 发现 | 严重程度 | 修复 |
|---|------|---------|------|
| R-13 | Section 8 编号错乱（8.3 在 8.2 前） | 🟢 格式 | 重排为 8.2 质量验证 → 8.3 Alembic Migration |
| R-14 | `start-assessment` API 端点遗漏 | 🟡 设计缺口 | 补充到 Section 4.3 孩子端 API 表 |
| R-15 | CoinTransaction `ref_type` 属性未扩展 | 🟢 补充 | 新增 `learning_earn → learning_assessment_attempt` 映射 |
| R-16 | `deprecated` 字段在版本管理中引用但表定义缺失 | 🔴 正确性 | 新增 `deprecated` Boolean 列到 learning_topic 表 |
| R-17 | 徽章 Phase 2 vs Phase 1 mastery 流程矛盾 | 🟡 设计缺口 | 明确 Phase 1 仅记录进度，Phase 2 实际颁发 |
