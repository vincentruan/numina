# Learning OS Optimization Design Spec

> 儿童学习系统任务分派与 UI 交互优化

| 字段 | 值 |
|---|---|
| Date | 2026-09-27 |
| Module | Learning OS (优化) |
| Status | Draft |
| Scope | 全栈: 种子数据 + 数据模型 + API + 前端页面 |
| Parent spec | `docs/superpowers/specs/2026-09-22-learning-os-design.md` |
| Parent plan | `docs/superpowers/plans/2026-09-23-learning-os.md` |

---

## 1. 问题清单

### 1.1 问题 #1：知识地图内容只有英文

**现状：** `learning_topics` 表的 `*_zh` 字段（name_zh, description_zh, evidence_zh, assessment_prompt_zh）在种子导入时全部为 NULL。前端 `useLocalizedTopic` composable 逻辑正确（locale=zh 时优先显示 `_zh` 字段），但因为数据为空，所有用户看到的都是英文。当前唯一的翻译路径是每 topic 手动点击"翻译成中文"按钮，触发 LLM 按需翻译。

**影响范围：**
- 儿童端 LearningTopicPage：标题、描述、学习目标、前置/后续知识全部英文
- 儿童端 LearningMapPage：学科标签中文，topic 名称英文
- 家长端 LearningAssignPage：topic 选择器列表全部英文
- 家长端 ChildLearningMapPage：topic 名称英文

### 1.2 问题 #2：父母指派任务为孤立单任务

**现状：** `LearningAssignment` 是 1:1 关系（一个 assignment 对应一个 topic）。`path_id` 列已预留但始终为 NULL。没有学习路径的概念。

**影响范围：**
- 家长无法一次指派一组相关任务
- 没有多日渐进学习的支持
- 没有梯度奖励机制（里程碑奖励、完成奖励）
- 任务之间没有前后关联的可视化

### 1.3 问题 #3：学习任务必须经指派才能学习

**现状：** 虽然 `onStartLearning()` 在技术上不检查 assignment（直接调用 `createSession`），但没有：
- 年龄难度警告
- `self_selected` 类型的自动 assignment 创建
- 自选学习的积分路径

### 1.4 问题 #4：点击"开始学习"后出现空白提示框并被强制退出登录

**现状：** 点击"开始学习"按钮后，`createSession()` 调用可能触发错误，导致空白 tooltip 显示，随后用户被登出。需要调查根因。

---

## 2. 解决方案设计

### 2.1 方案 #1：种子数据预翻译（Pre-translated Knowledge Map）

#### 2.1.1 种子脚本增强

**文件：** `server/scripts/seed_learning_topics.py`

**新增功能：批量翻译 pass（分层策略）**

在现有 seed 逻辑（导入 topics/deps/clusters）之后，新增翻译 pass。采用**分层翻译策略**：优先翻译高核心度 topic（centrality 高于阈值的约 200-300 个），确保儿童最常接触的知识点优先有中文；其余 topic 在种子阶段也一并翻译，但高核心度 topic 的翻译质量需抽样人工审核。

> **设计决策：复用已有 agent 模块翻译基础设施**
> 种子脚本通过 `apps.agent.services.topic_translate` 的 `LLMClient.complete_json()` 进行翻译，而非新建独立的 `translation_service.py`。这样可复用已有的多 provider 路由、熔断器、结构化输出验证和 `ai_crypto.py` 密钥管理，避免维护两套翻译实现。

```python
async def seed_topic_translations(session, data_dir: Path, batch_size: int = 50):
    """Batch-translate topics with empty *_zh fields using existing agent LLM infrastructure."""
    from packages.db.models.learning.topic import LearningTopic
    from apps.agent.services.topic_translate import translate_topic  # 复用已有翻译函数

    # Query topics with missing Chinese translations, 高核心度优先
    untranslated = session.query(LearningTopic).filter(
        LearningTopic.name_zh.is_(None) | LearningTopic.name_zh == ""
    ).filter(
        LearningTopic.deprecated == False
    ).order_by(LearningTopic.centrality.desc().nullslast()).all()

    # Skip topics whose English name already contains Chinese chars
    untranslated = [t for t in untranslated if not has_chinese_chars(t.name or "")]

    if not untranslated:
        print("All topics already translated. Skipping.")
        return

    print(f"Translating {len(untranslated)} topics (high-centrality first)...")

    total_translated = 0
    for batch_start in range(0, len(untranslated), batch_size):
        batch = untranslated[batch_start:batch_start + batch_size]
        for topic in batch:
            zh_fields = await translate_topic(topic)  # 复用已有 translate_topic()
            if zh_fields and zh_fields.get("name_zh"):
                # assessment_prompt_zh 校验：非空 + 基础注入检查
                if zh_fields.get("assessment_prompt_zh"):
                    prompt_zh = zh_fields["assessment_prompt_zh"]
                    if len(prompt_zh) > 500 or has_injection_pattern(prompt_zh):
                        print(f"  WARNING: Bad assessment_prompt_zh for {topic.topic_key}, keeping English")
                        zh_fields["assessment_prompt_zh"] = topic.assessment_prompt
                topic.name_zh = zh_fields.get("name_zh")
                topic.description_zh = zh_fields.get("description_zh")
                topic.evidence_zh_json = json.dumps(zh_fields.get("evidence", []), ensure_ascii=False)
                topic.assessment_prompt_zh = zh_fields.get("assessment_prompt_zh")
                total_translated += 1
            else:
                print(f"  WARNING: Translation failed for {topic.topic_key}, keeping English")
        session.commit()
        print(f"  Translated batch {batch_start//batch_size + 1}/{(len(untranslated)-1)//batch_size + 1}")

    print(f"Translation complete: {total_translated}/{len(untranslated)} topics translated.")
```

**新增 CLI 参数：**
- `--skip-translation` — 跳过翻译 pass（用于重新 seed 时避免重复翻译）
- `--batch-size N` — 每批翻译的 topic 数（默认 50）
- `--force-retranslate` — 强制重新翻译已有 `_zh` 数据的 topic
- `--centrality-threshold N` — 仅翻译 centrality >= N 的 topic（用于分层翻译，默认 0 = 全量）

**容错策略：**
- 每批翻译后 `session.commit()`，支持中断后续翻
- 重新运行时自动跳过已有 `_zh` 数据的 topic（幂等），无需额外的 checkpoint 或 retry 机制
- 单条翻译失败不影响批次其他 topic（失败 topic 保留英文，下次重跑自动重试）
- `assessment_prompt_zh` 翻译结果做非空 + 基础注入检查，异常 topic 保留英文原文

> **注意：** 前端"翻译成中文"按钮**保留**（仅对 `*_zh` 为 NULL 的 topic 显示），用于 taxonomy 更新后的补翻和用户触发的质量修复。后续可封装为翻译 skill 实现自动化。

**规模估算：**
- 约 1,500 个 topic 需要翻译（排除已含中文的）
- 高核心度 topic（centrality > 0.5）约 200-300 个优先翻译
- 每批 50 个 = 约 30 批次（全量）
- 复用 agent 模块 `LLMClient`，自动选择可用 provider（含熔断器保护）
- 总计约 0.5M-1M tokens，约 ¥3-5，耗时 3-5 分钟
- 种子脚本后建议抽样审核 20-30 个 topic（每学科 3-4 个）验证翻译质量

#### 2.1.2 Cluster 翻译

**文件：** `seed_learning_topics.py`

为 `learning_clusters` 表新增 `summary_zh` 字段：

```python
# learning_cluster 表新增列
summary_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
```

在 seed 脚本中为 cluster 的 `summary` 字段也生成中文翻译。

**Alembic 迁移：** 为 `learning_clusters` 添加 `summary_zh` 列。

#### 2.1.3 前端变更

**保留"翻译成中文"按钮（条件显示）：**

种子预翻译完成后，翻译按钮**保留**但改为条件显示逻辑：仅当 topic 的 `*_zh` 字段为 NULL 时才显示。这样：
- 已翻译的 topic 不再显示翻译按钮（减少 UI 噪音）
- 未翻译的 topic（taxonomy 新增、翻译失败保留英文的）仍然可以手动触发翻译
- 为后续封装为翻译 skill 保留入口

`LearningTopicPage.vue` — 修改 `showTranslateButton` computed：
- 保留现有逻辑（locale=zh 时显示、topic 名称已含中文时隐藏）
- 新增条件：仅当 `!topic.name_zh` 时显示（已翻译则隐藏）

`ChildLearningMapPage.vue`（家长端） — 同样保留 per-topic translate button（条件显示）。

**后端翻译 API 保留不变：** `POST /learning/topics/{id}/translate` 端点继续使用，用于 taxonomy 更新后的补翻和用户触发的质量修复。

**i18n key 保留：** `learning.translate`、`learning.translating`、`learning.translationComplete`、`learning.translationFailed` 等 key 保留不删除。

**未来演进：** 当翻译 skill 封装完成并验证可靠后，可考虑移除 per-topic 翻译按钮，由 skill 自动处理增量翻译。

#### 2.1.4 受影响的文件

| 文件 | 变更 |
|---|---|
| `server/scripts/seed_learning_topics.py` | 新增批量翻译 pass + CLI 参数（复用 agent 模块翻译能力） |
| `server/packages/db/models/learning/topic.py` | 新增 LearningCluster `summary_zh` 列（LearningCluster 定义在此文件） |
| `server/apps/backend/alembic/versions/` | 新增 migration（cluster summary_zh） |
| `frontend/apps/child/src/pages/learning/LearningTopicPage.vue` | 翻译按钮改为条件显示（仅 `*_zh` 为 NULL 时显示） |
| `frontend/apps/main/src/pages/ChildLearningMapPage.vue` | 翻译按钮改为条件显示 |

---

### 2.2 方案 #2：学习路径（Learning Path — 任务组）

> **Scope note:** 父 spec 将 `learning_path` 表标记为 Phase 2（MVP 阶段不实现，预留字段）。本优化 spec 将其提升为当前迭代范围，因为问题 #2（孤立单任务）的完整解决需要学习路径支持。涉及 2 新表 + 6 新端点 + ~17 文件。
>
> **简化替代方案（建议先验证）：** 在实施完整路径系统前，可先实现轻量级"任务分组"：在现有 `learning_assignments` 表加 `group_id` 列，家长多选 topic 创建一组 assignment，前端按 group_id 分组显示，使用现有 `learning_earn` 奖励机制。这只需约 5 个文件变更，无需新表、新 coin 类型或拓扑排序。如果验证家长确实频繁使用分组指派，再升级为完整路径系统。**当前 spec 仍描述完整路径方案，但建议实施时先评估简化方案。**

#### 2.2.1 数据模型

**新增 `learning_path` 表：**

```python
# server/packages/db/models/learning/path.py

class LearningPath(Base):
    __tablename__ = "learning_paths"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("families.id"), nullable=False, index=True)
    child_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False, index=True)
    created_by: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_zh: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description_zh: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    per_task_score: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    bonus_score: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    milestone_scores_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    from packages.db.mixins.json_text import json_text
    milestone_scores: list = json_text("milestone_scores_json")
    # Example: [{"threshold": 3, "bonus": 10}, {"threshold": 6, "bonus": 20}]
```

**新增 `learning_path_item` 表：**

```python
class LearningPathItem(Base):
    __tablename__ = "learning_path_items"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    path_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_paths.id"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("learning_topics.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    # pending / in_progress / completed / skipped
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
```

**修改 `LearningAssignment`：** 将现有 `path_id` 列加 FK 约束（迁移时处理）。当通过路径创建 assignment 时，`path_id` 指向所属 path。

**Coin 奖励关联：** 路径任务的 coin 交易使用 `ref_id = learning_path_item.id`，`transaction_type = "path_earn"`（新增类型，避免与 assessment_attempt 的 `"learning_earn"` 在 `UniqueConstraint("ref_id", "transaction_type")` 上冲突），与现有 assessment_attempt 的幂等性模式一致。路径完成奖励使用 `ref_id = path.id`，`transaction_type = "path_completion"`。

#### 2.2.2 评分规则

```python
def compute_path_rewards(
    path: LearningPath,
    completed_count: int,
    total_count: int,
) -> dict:
    """
    Compute reward breakdown for a path item completion.
    Returns: {
        "per_task": int,         # per_task_score
        "milestone": int | None, # milestone bonus if threshold hit
        "completion": int | None # bonus_score if all done
    }
    """
    rewards = {"per_task": path.per_task_score, "milestone": None, "completion": None}

    # Check milestone thresholds (typed array, no string parsing)
    for entry in path.milestone_scores:  # [{"threshold": 3, "bonus": 10}, ...]
        if completed_count == entry["threshold"]:
            rewards["milestone"] = entry["bonus"]
            break

    # Check full completion
    if completed_count == total_count:
        rewards["completion"] = path.bonus_score

    return rewards
```

**Coin 发放流程：**

```
Path item 完成 (topic mastered)
    ↓
path_service.advance_path_item(path_id, topic_id)
    ↓
1. 更新 item status → "completed"
2. 计算 rewards = compute_path_rewards(path, new_completed_count, total_count)
3. 发放 per_task coins（ref_id = path_item.id, type = "path_earn", narrative = "路径任务：{topic_name}"）
4. 如果 milestone 命中 → 额外发放 milestone coins（ref_id = path_item.id, type = "path_earn", narrative = "里程碑奖励：完成 {n}/{total}"）
5. 如果全部完成 → 额外发放 bonus coins（ref_id = path.id, type = "path_completion"）
6. 更新 path.status → "completed"（如果全部 done）
7. 检查每日 coin 上限，超额部分进入 pending
8. 发送通知给家长
```

**新增 transaction_type（精简为 2 种）：**
- `"path_earn"` — 路径任务奖励（ref_id = path_item.id），涵盖 per_task 和 milestone 奖励，通过 narrative 字段区分（如 "路径任务：分数加法" / "里程碑奖励：完成 3/5"）
- `"path_completion"` — 路径完成奖励（ref_id = path.id）

> **设计决策：** 将原先的 3 种类型（path_task_earn / path_milestone / path_completion）精简为 2 种。`path_milestone` 和 `path_task_earn` 共享同一 ref_id（path_item.id），合并为 `path_earn` 后，`UniqueConstraint("ref_id", "transaction_type")` 仍提供幂等性保证，同时减少 ref_type_map 条目和 coin ledger 查询复杂度。

**注意：** 需在 `coin_transaction.py` 的 `ref_type` property 的 `_MAP` dict 中新增对应条目：`path_earn → learning_path_item`、`path_completion → learning_path`。

**路径×自选学习交叉行为：** 当 child 通过自选学习（方案 #3）mastered 一个 topic 时，系统需检查该 topic 是否属于 child 的某个活跃路径。如果是，调用 `advance_path_item` 推进路径进度；如果不是，跳过路径逻辑。这确保自选学习和路径学习不冲突，但 milestone 奖励依赖 `completed_count` 递增，乱序完成可能使里程碑触发时机不符合预期。

#### 2.2.3 路径自动排序

创建路径时，系统根据 topic 之间的 `learning_dependency` 关系自动排序：

```python
def sort_topics_by_prerequisites(
    db: Session, topic_ids: list[int]
) -> list[int]:
    """
    Topological sort of topics based on prerequisite dependencies.
    Topics with no unmet prerequisites come first.
    """
    # Build subgraph from selected topics
    # Topological sort using Kahn's algorithm
    # Return ordered list of topic_ids
    ...
```

#### 2.2.4 Service 层

**新建 `server/apps/backend/app/services/learning/path_service.py`：**

```python
def create_path(
    db: Session,
    family_id: int,
    child_id: int,
    created_by: int,
    name: str,
    name_zh: str | None,
    topic_ids: list[int],
    per_task_score: int = 5,
    bonus_score: int = 10,
    milestone_scores: list | None = None,
    due_date: date | None = None,
) -> LearningPath:
    """Create a learning path with auto-sorted items."""
    # 1. Create LearningPath record
    # 2. Sort topics by prerequisite order
    # 3. Create LearningPathItem records with sort_order
    # 4. Create LearningAssignment records for each item (for notification/queue)
    # 5. Return path
    ...

def advance_path_item(
    db: Session, path_id: int, topic_id: int
) -> dict:
    """
    Mark a path item as completed, compute rewards, emit coins.
    Returns: {item, rewards, path_progress}
    """
    ...

def get_path_progress(
    db: Session, path_id: int, family_id: int
) -> dict:
    """
    Get path progress: items with status, completed count, 
    total count, next milestone, cumulative score.
    Validates family_id for tenant isolation.
    """
    ...

def get_child_active_paths(
    db: Session, child_id: int, family_id: int
) -> list[LearningPath]:
    """List all active paths for a child. Validates family_id for tenant isolation."""
    ...
```

#### 2.2.5 API 端点

**家长端（`learning_family.py` 新增）：**

| Method | Path | 说明 |
|---|---|---|
| POST | `/family/learning/paths` | 创建学习路径 |
| GET | `/family/learning/paths` | 列出路径（可按 child 过滤） |
| GET | `/family/learning/paths/{path_id}` | 路径详情 + items |
| POST | `/family/learning/paths/{path_id}/archive` | 归档路径 |

> **Access control:** 所有路径端点必须验证 `LearningPath.family_id == current_user.family_id`，与现有 `learning_family.py` 的 `.filter(User.family_id == user.family_id)` 模式一致。`path_service` 的 `get_path_progress` / `get_child_active_paths` 等函数需接受 `family_id` 参数用于隔离。

**孩子端（`learning_child.py` 新增）：**

| Method | Path | 说明 |
|---|---|---|
| GET | `/child/learning/paths` | 我的活跃学习路径 |
| GET | `/child/learning/paths/{path_id}` | 路径详情 + 进度 |

> **Child access control:** 孩子端路径端点必须验证 `path.child_id == current_child.id` AND `path.family_id == current_child.family_id`，防止 IDOR。`get_child_active_paths` 内部同时按 child_id 和 family_id 过滤。

#### 2.2.6 Pydantic Schemas

**新增 `server/apps/backend/app/schemas/learning.py`：**

```python
class PathCreate(BaseModel):
    child_id: int
    name: str
    name_zh: str | None = None
    description: str = ""
    topic_ids: list[int]
    per_task_score: int = 5
    bonus_score: int = 10
    milestone_scores: list[dict] | None = None  # [{"threshold": 3, "bonus": 10}]
    due_date: date | None = None

class PathItemResponse(SnowflakeBase):
    id: int
    path_id: int
    topic_id: int
    sort_order: int
    status: str
    topic_name: str | None
    topic_name_zh: str | None
    completed_at: datetime | None

class PathResponse(SnowflakeBase):
    id: int
    family_id: int
    child_id: int
    created_by: int
    name: str
    name_zh: str | None
    description: str
    status: str
    per_task_score: int
    bonus_score: int
    milestone_scores: list[dict]
    due_date: date | None
    created_at: datetime
    completed_at: datetime | None
    items: list[PathItemResponse] = []
    # Computed fields
    completed_count: int = 0
    total_count: int = 0
    next_milestone: dict | None = None  # {"threshold": 3, "bonus": 10, "progress": "2/3"}
```

#### 2.2.7 前端变更

**家长端 LearningAssignPage.vue：**

新增"创建学习路径"模式：
- Tab 切换："单个任务" / "学习路径"
- 路径模式：多选 topic（checkbox）、设置 per_task_score、bonus_score、可选 deadline
- 预览卡片："N 个任务 · 每个 N 分 · 里程碑: 3个+10分 · 完成额外+N分"
- 系统自动按前置关系排序 topic

**孩子端 LearningTopicPage.vue：**

- 如果 topic 属于某个 path → 显示路径上下文条："📋 学习路径: 分数入门 (2/5)"
- 路径进度 mini bar

**孩子端 TodayLearningCard.vue：**

- 如果有活跃路径 → 显示路径进度卡片（替代单个推荐 topic）
- "今日路径任务: 分数加法 (3/5)"

**孩子端（可选新页面）LearningPathPage.vue：**

- 路由: `/learning/path/:id`
- 显示路径详情、所有 items 及状态、进度条、奖励预览

#### 2.2.8 Alembic 迁移

新增迁移文件：
1. 创建 `learning_paths` 表
2. 创建 `learning_path_items` 表
3. 为 `learning_assignments.path_id` 添加 FK 约束（指向 `learning_paths.id`）

#### 2.2.9 受影响的文件

| 文件 | 变更 |
|---|---|
| `server/packages/db/models/learning/path.py` | **新建** |
| `server/packages/db/models/learning/__init__.py` | 注册新模型 |
| `server/packages/db/models/learning/assignment.py` | path_id 加 FK |
| `server/apps/backend/app/services/learning/path_service.py` | **新建**（含路径奖励逻辑，不单独建 coin_service） |
| `server/apps/backend/app/schemas/learning.py` | 新增 Path 相关 schema |
| `server/apps/backend/app/routers/learning_family.py` | 新增路径 CRUD 端点 |
| `server/apps/backend/app/routers/learning_child.py` | 新增路径查询端点 |
| `server/apps/backend/app/errors/codes.py` | 新增路径相关错误码 |
| `server/apps/backend/alembic/versions/` | 新增 migration |
| `server/tests/backend/test_learning_path_service.py` | **新建** 测试 |
| `frontend/apps/main/src/api/learning.ts` | 新增路径 API 函数 |
| `frontend/apps/main/src/pages/LearningAssignPage.vue` | 新增路径创建模式 |
| `frontend/apps/child/src/api/learning.ts` | 新增路径 API 函数 |
| `frontend/apps/child/src/pages/learning/LearningTopicPage.vue` | 显示路径上下文 |
| `frontend/apps/child/src/components/TodayLearningCard.vue` | 显示路径进度 |
| `frontend/apps/child/src/pages/learning/LearningPathPage.vue` | **新建** 路径详情页 |

---

### 2.3 方案 #3：自选学习 + 年龄难度提示

#### 2.3.1 后端变更

**修改 `POST /child/learning/sessions`（`learning_child.py`）：**

```python
@router.post("/sessions", response_model=SessionResponse)
def create_session(
    req: SessionCreate,
    current_child: User = Depends(get_current_child_user),
    db: Session = Depends(get_db),
):
    # 1. Get or create progress
    progress = get_or_create_progress(db, current_child.id, req.topic_id)

    # 1b. Self-selected bypass: override locked → available for self-selected learning
    # 注意：这绕过了前置知识链检查。结合年龄难度警告（step 2）一起使用，
    # 如果 topic 的前置知识未满足，也在 difficulty_warning 中提示。
    if progress.mastery_level == "locked":
        progress.mastery_level = "available"
        db.commit()

    # 2. Age difficulty check + prerequisite warning
    topic = get_topic_by_id(db, req.topic_id)
    child_age = compute_child_age(current_child)  # from birthday
    child_age_group = compute_age_group(child_age)
    
    difficulty_warning = None
    AGE_GROUP_ORDER = {"low": 0, "mid": 1, "high": 2}
    
    # 年龄难度检查
    age_warning = None
    if AGE_GROUP_ORDER.get(topic.age_group, 1) > AGE_GROUP_ORDER.get(child_age_group, 1):
        suggested = find_age_appropriate_topic(db, current_child.id, topic.subject)
        age_warning = {
            "level": topic.age_group,
            "child_level": child_age_group,
            "suggested_topic_id": str(suggested.id) if suggested else None,
            "suggested_topic_name_zh": suggested.name_zh if suggested else None,
            "suggested_topic_name": suggested.name if suggested else None,
        }
    
    # 前置知识检查（自选学习绕过了 locked 状态，需要额外提醒）
    prereq_warning = None
    unmet_prereqs = get_unmet_prerequisites(db, req.topic_id, current_child.id)
    if unmet_prereqs:
        prereq_warning = {
            "unmet_count": len(unmet_prereqs),
            "suggested_topic_id": str(unmet_prereqs[0].id) if unmet_prereqs else None,
        }
    
    # 合并警告（年龄 > 前置知识）
    if age_warning:
        difficulty_warning = {"type": "age", **age_warning}
    elif prereq_warning:
        difficulty_warning = {"type": "prerequisite", **prereq_warning}

    # 3. Auto-create self_selected assignment if none exists
    assignment = get_active_assignment(db, current_child.id, req.topic_id)
    if not assignment:
        assignment = create_assignment(
            db, current_child.family_id, current_child.id,
            req.topic_id, assignment_type="self_selected", created_by=current_child.id
        )

    # 4. Create session
    session = create_session_record(db, current_child.id, req.topic_id, assignment_id=assignment.id)

    return {**session, "difficulty_warning": difficulty_warning}
```

**修改 `SessionResponse` schema：**

```python
class SessionResponse(SnowflakeBase):
    # ... existing fields ...
    difficulty_warning: dict | None = None  # NEW
```

**推荐 topic 查找：**

新建 `find_age_appropriate_topic(db, child_id, subject)` — 返回同 subject 中 age_group 匹配 child 且 progress 为 `available` 或 `learning` 的 topic（不复用 `find_recommended_topic`，后者返回 `locked` 状态的 topic）。

新建 `get_unmet_prerequisites(db, topic_id, child_id)` — 返回 topic 的前置知识中 progress 不为 `mastered` 的 topic 列表，用于自选学习的前置知识警告。

**速率限制（Coin 防刷）：**

自选学习新增了无指派直接赚 coin 的路径。当前代码库中**不存在**每日 coin 上限机制（需新建），必须在实施自选学习时同步实现：

- 在 `create_session` 的 coin 发放路径添加每日 earning cap（如每日最多 50 coins from learning）
- 超出上限的奖励进入 pending 状态，次日自动发放
- 路径任务的 coin 发放（`advance_path_item`）也需受此 cap 约束
- 具体 cap 值可通过环境变量 `DAILY_LEARNING_COIN_CAP` 配置，默认 50

#### 2.3.2 前端变更

**LearningTopicPage.vue：**

点击"开始学习"后的流程变更：

```
点击 [开始学习]
    ↓
POST /child/learning/sessions
    ↓
响应包含 difficulty_warning?
    ├─ No → 直接 router.push(`/learning/session/${session.id}`)
    ─ Yes → 显示难度提示弹窗（使用 t('learning.difficulty_warning') 构造消息）
              "这个任务属于高难度，对你来说可能有点挑战。
               要不要先试试 [推荐任务名]？"
              [继续学习这个] [去看看推荐的]
                  ↓                    ↓
              进入 session         导航到推荐 topic
```

**弹窗设计：**
- 使用 `van-dialog` 或自定义 modal
- 图标：⚠️ 或 
- 友好措辞，不阻止学习
- 推荐 topic 名称 clickable，点击后导航到该 topic

#### 2.3.3 受影响的文件

| 文件 | 变更 |
|---|---|
| `server/apps/backend/app/routers/learning_child.py` | 添加年龄检查 + 自选 assignment |
| `server/apps/backend/app/services/learning/session_service.py` | 添加年龄检查逻辑 |
| `server/apps/backend/app/schemas/learning.py` | SessionResponse 添加 difficulty_warning |
| `server/apps/backend/app/services/learning/progress_service.py` | 暴露 find_recommended_topic |
| `frontend/apps/child/src/api/learning.ts` | SessionResponse 类型更新 |
| `frontend/apps/child/src/pages/learning/LearningTopicPage.vue` | 难度提示弹窗 |
| `frontend/apps/child/src/i18n/locales/zh-CN.ts` | 新增难度提示文案 |
| `frontend/apps/child/src/i18n/locales/en-US.ts` | 新增难度提示文案 |

---

### 2.4 方案 #4：Session 创建 Bug 修复

#### 2.4.1 P1 — 调查（限时 spike）

**可能原因分析：**

1. **Auth token 问题：** 儿童 token 过期 → `createSession()` 返回 401 → 前端 auth 中间件触发 logout
2. **Session 创建异常：** `session_service.create_session()` 内部异常（如 prerequisite 检查失败）→ 未捕获 → 500 → 空白 tooltip
3. **DeerFlow 集成问题：** Session 创建成功但 DeerFlow thread 创建失败 → 前端 LearningSessionPage 连接 SSE 失败 → 错误冒泡
4. **前端状态问题：** `starting` ref 状态管理导致重复点击或状态不一致

**调查步骤：**
1. 查看后端日志中 `/child/learning/sessions` 的 error traceback
2. 检查 `session_service.create_session()` 的错误处理
3. 检查 `learning_child.py` 的 auth middleware 行为
4. 浏览器 DevTools Network 面板捕获实际 HTTP 请求/响应
5. 检查 `LearningSessionPage.vue` 的 onMounted 错误处理

**产出：** 根因确定并记录，修复方案写入 P2 修复单元。

#### 2.4.2 P2 — 修复（调查完成后实施）

根据 P1 调查结果，可能涉及：
- `session_service.py` 的错误处理增强
- `learning_child.py` 的异常中间件处理
- `LearningTopicPage.vue` 的 `onStartLearning` 错误处理
- `LearningSessionPage.vue` 的连接失败降级

---

## 3. 实施优先级

| 优先级 | 问题 | 理由 |
|---|---|---|
| P0 | #1 预翻译 | 用户影响最大（所有中文用户看到的都是英文），种子脚本改动范围可控 |
| P0 | #4 Bug 调查+修复 | 阻断性问题（开始学习 → 被登出），核心功能完全不可用，应与预翻译并行调查 |
| P2 | #3 自选学习 | 受益于 #1 的数据（中文 topic 名称），`_zh` 为 NULL 时回退英文；需同步实现 coin 每日上限 |
| P3 | #2 学习路径 | 最大变更（新模型 + UI），但独立于其他问题；建议先评估简化方案（任务分组） |

---

## 4. 全局约束

- 继承父 spec 的全部约束：Snowflake ID、`redirect_slashes=False`、`SnowflakeBase`、`UTCDateTime` 等
- 新增 transaction_type 需在 `CoinTransaction` 注释中记录（现有为 String(20)，应用层约定）
- 前端所有用户可见字符串使用 `t('key')`，无硬编码中文
- 新增 API 路由 root-path 使用 `""` 非 `"/"`
- Alembic 迁移使用 `_table_exists` guard 保证幂等性
- `*_zh` 字段中，JSON 结构化字段（如 `evidence_zh_json`）使用 `json_text` mixin；纯文本翻译字段（`name_zh`、`description_zh`、`assessment_prompt_zh`、`summary_zh`）使用 `String`/`Text` 列

---

## 5. 验收标准

### #1 预翻译
- [ ] `seed_learning_topics.py --skip-translation` 正常运行
- [ ] `seed_learning_topics.py` 默认执行翻译 pass，高核心度 topic 的 `*_zh` 字段被填充
- [ ] 中文 locale 用户进入 LearningTopicPage，高频 topic 标题/描述/evidence 显示中文
- [ ] 英文 locale 用户看到英文原文
- [ ] 翻译按钮仅对 `*_zh` 为 NULL 的 topic 显示（条件显示）
- [ ] 家长端 topic 选择器显示中文 topic 名称（已翻译的）
- [ ] `assessment_prompt_zh` 翻译异常时保留英文原文，记录日志
- [ ] 抽样审核 20-30 个 topic 翻译质量（每学科 3-4 个）

### #2 学习路径
- [ ] 家长可以创建包含多个 topic 的学习路径
- [ ] 路径内 topic 按前置关系自动排序
- [ ] 子路径进度可视化（N/M 完成）
- [ ] 完成单个 topic → 自动发放 per_task coins
- [ ] 达到里程碑 → 额外发放 milestone coins
- [ ] 全部完成 → 额外发放 bonus coins
- [ ] 儿童端可以看到路径进度
- [ ] 所有新增端点通过测试

### #3 自选学习
- [ ] 儿童可以直接从知识地图进入任何 topic 学习
- [ ] 年龄高于 child 水平时显示非阻塞提示
- [ ] 前置知识未满足时显示非阻塞提示（推荐先学习前置 topic）
- [ ] 提示包含同科目推荐 topic
- [ ] 自选学习自动创建 `self_selected` assignment
- [ ] 自选学习完成后正常获得 coins
- [ ] 每日 learning coin 上限已实现（默认 50 coins），超额奖励次日发放
- [ ] 自选学习 mastered 的 topic 如果属于活跃路径，路径 item 自动推进

### #4 Bug 修复
- [ ] 点击"开始学习"正常进入 AI 对话页面
- [ ] 不再出现空白 tooltip
- [ ] 不再被强制退出登录
- [ ] 根因已确定并记录

### 补充约束验收
- [ ] `PathCreate.milestone_scores` 验证器拒绝畸形配置（非正整数、threshold 越界、重复）
- [ ] 自选学习每日 coin earning cap 已新建（默认 50，可通过 DAILY_LEARNING_COIN_CAP 配置）
- [ ] 种子翻译对 `assessment_prompt_zh` 做非空 + 基础注入检查，异常 topic 保留英文

---

## 6. 补充约束（Review 补充）

以下三项为文档审查中识别的遗留风险，附解决方案：

### 6.1 `milestone_scores` Schema 验证

**风险：** `PathCreate` 的 `milestone_scores` 字段无验证，畸形配置（如字段缺失或类型错误、threshold 超出范围、负数 bonus）会静默产生零奖励。

**方案：** 在 `PathCreate` schema 中添加 `@validator("milestone_scores")`：
- 每个 entry 必须包含 `threshold`（正整数）和 `bonus`（正整数）
- `threshold` 必须在 `[1, len(topic_ids)]` 范围内
- 不允许重复 threshold

### 6.2 自选学习 Coins 防刷

**风险：** 儿童可通过程序化快速创建 session 来自动获得 coins，无速率限制。

**方案：** 新建每日 coin 上限机制（当前代码库中不存在）。在 `create_session`（自选学习）和 `advance_path_item`（路径任务）的 coin 发放逻辑中添加每日 earning cap（如每日最多 50 coins），超出的奖励进入 pending 状态次日发放。通过环境变量 `DAILY_LEARNING_COIN_CAP` 配置。

### 6.3 LLM 翻译输出校验

**风险：** `assessment_prompt_zh` 等 LLM 输出直接写入 DB 并用于评估流程，若 LLM 产生异常内容可能影响评估。复用 agent 模块的 `LLMClient.complete_json()` 提供结构化输出验证，但语义正确性无法自动保证。

**方案：** 种子翻译时添加基础校验（已集成在 2.1.1 代码中）：
- `name_zh` / `description_zh`：非空、长度合理（< 500 chars）
- `assessment_prompt_zh`：非空、不包含明显 prompt injection 模式（如 "ignore previous instructions"、Unicode 同形字混淆）
- 校验失败的 topic 保留英文原文，记录到日志供人工复查
- 种子翻译后建议抽样审核 20-30 个 topic（每学科 3-4 个）验证翻译质量
- 翻译按钮保留为 fallback：家长可对特定 topic 触发重新翻译

**未来演进：** 将翻译能力封装为 skill，支持批量翻译 + 增量翻译 + 质量校验，自动化 taxonomy 更新后的补翻流程。
