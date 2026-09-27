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

**新增功能：批量翻译 pass**

在现有 seed 逻辑（导入 topics/deps/clusters）之后，新增翻译 pass：

```python
def seed_topic_translations(session, data_dir: Path, batch_size: int = 50):
    """Batch-translate topics with empty *_zh fields using LLM."""
    from packages.db.models.learning.topic import LearningTopic
    from apps.backend.app.services.learning.translation_service import translate_topic_batch

    # Query topics with missing Chinese translations
    untranslated = session.query(LearningTopic).filter(
        LearningTopic.name_zh.is_(None) | LearningTopic.name_zh == ""
    ).filter(
        LearningTopic.deprecated == False
    ).order_by(LearningTopic.subject, LearningTopic.centrality.desc().nullslast()).all()

    # Skip topics whose English name already contains Chinese chars
    untranslated = [t for t in untranslated if not has_chinese_chars(t.name or "")]

    if not untranslated:
        print("All topics already translated. Skipping.")
        return

    print(f"Translating {len(untranslated)} topics...")

    # Group by subject for coherent translation context
    by_subject: dict[str, list[LearningTopic]] = {}
    for t in untranslated:
        by_subject.setdefault(t.subject, []).append(t)

    total_translated = 0
    for subject, topics in by_subject.items():
        for batch_start in range(0, len(topics), batch_size):
            batch = topics[batch_start:batch_start + batch_size]
            results = translate_topic_batch(batch, subject=subject)
            for topic, zh_fields in zip(batch, results):
                topic.name_zh = zh_fields.get("name_zh")
                topic.description_zh = zh_fields.get("description_zh")
                topic.evidence_zh_json = json.dumps(zh_fields.get("evidence_zh", []), ensure_ascii=False)
                topic.assessment_prompt_zh = zh_fields.get("assessment_prompt_zh")
                total_translated += 1
            session.commit()
            print(f"  Translated batch {batch_start//batch_size + 1}/{(len(topics)-1)//batch_size + 1} for {subject}")

    print(f"Translation complete: {total_translated} topics translated.")
```

**新增 CLI 参数：**
- `--skip-translation` — 跳过翻译 pass（用于重新 seed 时避免重复翻译）
- `--batch-size N` — 每批翻译的 topic 数（默认 50）
- `--force-retranslate` — 强制重新翻译已有 `_zh` 数据的 topic

**翻译服务：**

新建 `server/apps/backend/app/services/learning/translation_service.py`：

```python
async def translate_topic_batch(
    topics: list[LearningTopic], subject: str
) -> list[dict]:
    """
    Translate a batch of topics into Chinese.
    Returns list of dicts: [{name_zh, description_zh, evidence_zh, assessment_prompt_zh}, ...]
    """
    # Build batch prompt: send all topics in one LLM call with structured output
    # Use DashScope qwen-plus for cost efficiency
    # Subject term glossary injected into prompt to preserve English for technical terms
    ...
```

**规模估算：**
- 约 1,500 个 topic 需要翻译（排除已含中文的）
- 每批 50 个 × 8 学科 = 约 240 次 API 调用
- 每次约 2000-4000 tokens（input + output）
- 总计约 0.5M-1M tokens
- 使用 DashScope qwen-plus：约 ¥3-5，耗时 3-5 分钟

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

**移除"翻译成中文"按钮：**

`LearningTopicPage.vue` — 移除 translate button 及相关逻辑：
- 删除 `translating` ref
- 删除 `handleTranslate` 函数
- 删除 `showTranslateButton` computed
- 删除 `translateTopic` import
- 删除模板中的 `<van-button class="translate-btn">`

`ChildLearningMapPage.vue`（家长端） — 同样移除 per-topic translate button。

**保留后端翻译 API：** `POST /learning/topics/{id}/translate` 端点保留，用于未来手动修复或 taxonomy 更新后的补翻。

**i18n key 清理：** 从 `zh-CN.ts` 和 `en-US.ts` 中移除 `learning.translate`、`learning.retranslate`、`learning.translating`、`learning.translationComplete`、`learning.translationFailed` 等 key。

#### 2.1.4 受影响的文件

| 文件 | 变更 |
|---|---|
| `server/scripts/seed_learning_topics.py` | 新增批量翻译 pass + CLI 参数 |
| `server/apps/backend/app/services/learning/translation_service.py` | **新建** 批量翻译服务 |
| `server/packages/db/models/learning/topic.py` | 无变更（`*_zh` 字段已存在） |
| `server/packages/db/models/learning/cluster` | 新增 `summary_zh` 列 |
| `server/apps/backend/alembic/versions/` | 新增 migration（cluster summary_zh） |
| `frontend/apps/child/src/pages/learning/LearningTopicPage.vue` | 移除 translate button |
| `frontend/apps/main/src/pages/ChildLearningMapPage.vue` | 移除 translate button |
| `frontend/apps/child/src/i18n/locales/zh-CN.ts` | 移除翻译相关 key |
| `frontend/apps/child/src/i18n/locales/en-US.ts` | 移除翻译相关 key |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | 移除翻译相关 key |
| `frontend/apps/main/src/i18n/locales/en-US.ts` | 移除翻译相关 key |

---

### 2.2 方案 #2：学习路径（Learning Path — 任务组）

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
    milestone_scores_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    from packages.db.mixins.json_text import json_text
    milestone_scores: dict = json_text("milestone_scores_json")
    # Example: {"at_3": 10, "at_6": 20, "at_10": 30}
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

**Coin 奖励关联：** 路径任务的 coin 交易使用 `ref_id = learning_path_item.id`，`transaction_type = "learning_earn"`，与现有 assessment_attempt 的幂等性模式一致。

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

    # Check milestone thresholds
    milestones = path.milestone_scores  # {"at_3": 10, "at_6": 20}
    for key, bonus in milestones.items():
        threshold = int(key.replace("at_", ""))
        if completed_count == threshold:
            rewards["milestone"] = bonus
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
3. 发放 per_task coins（ref_id = path_item.id, type = "learning_earn"）
4. 如果 milestone 命中 → 额外发放 milestone coins（ref_id = path_item.id, type = "path_milestone"）
5. 如果全部完成 → 额外发放 bonus coins（ref_id = path.id, type = "path_completion"）
6. 更新 path.status → "completed"（如果全部 done）
7. 发送通知给家长
```

**新增 transaction_type：**
- `"learning_earn"` — 已存在，复用（per-task 奖励）
- `"path_milestone"` — 新增，里程碑奖励
- `"path_completion"` — 新增，路径完成奖励

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
    milestone_scores: dict | None = None,
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
    db: Session, path_id: int
) -> dict:
    """
    Get path progress: items with status, completed count, 
    total count, next milestone, cumulative score.
    """
    ...

def get_child_active_paths(
    db: Session, child_id: int
) -> list[LearningPath]:
    """List all active paths for a child."""
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

**孩子端（`learning_child.py` 新增）：**

| Method | Path | 说明 |
|---|---|---|
| GET | `/child/learning/paths` | 我的活跃学习路径 |
| GET | `/child/learning/paths/{path_id}` | 路径详情 + 进度 |

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
    milestone_scores: dict[str, int] | None = None  # {"at_3": 10}
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
    milestone_scores: dict[str, int]
    due_date: date | None
    created_at: datetime
    completed_at: datetime | None
    items: list[PathItemResponse] = []
    # Computed fields
    completed_count: int = 0
    total_count: int = 0
    next_milestone: dict | None = None  # {"at": 3, "bonus": 10, "progress": "2/3"}
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
| `server/apps/backend/app/services/learning/path_service.py` | **新建** |
| `server/apps/backend/app/services/learning/coin_service.py` | **新建或修改** 路径奖励逻辑 |
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

    # 2. Age difficulty check
    topic = get_topic_by_id(db, req.topic_id)
    child_age = compute_child_age(current_child)  # from birth_date
    child_age_group = compute_age_group(child_age)
    
    difficulty_warning = None
    AGE_GROUP_ORDER = {"low": 0, "mid": 1, "high": 2}
    if AGE_GROUP_ORDER.get(topic.age_group, 1) > AGE_GROUP_ORDER.get(child_age_group, 1):
        # Topic is above child's level
        suggested = find_recommended_topic(db, current_child.id, topic.subject)
        difficulty_warning = {
            "level": topic.age_group,
            "child_level": child_age_group,
            "message": f"这个任务属于{AGE_GROUP_LABELS[topic.age_group]}难度，对你来说可能有点挑战。",
            "suggested_topic_id": str(suggested.id) if suggested else None,
            "suggested_topic_name": suggested.name_zh or suggested.name if suggested else None,
        }

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

复用 `progress_service.find_recommended_topic()` — 返回同 subject 中 available/in_progress 且 age_group 匹配 child 的 topic。

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
    ─ Yes → 显示难度提示弹窗
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

#### 2.4.1 调查计划

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

#### 2.4.2 预期修复方向

根据调查结果，可能涉及：
- `session_service.py` 的错误处理增强
- `learning_child.py` 的异常中间件处理
- `LearningTopicPage.vue` 的 `onStartLearning` 错误处理
- `LearningSessionPage.vue` 的连接失败降级

此部分将在实施阶段通过 systematic-debugging 确定具体修复方案。

---

## 3. 实施优先级

| 优先级 | 问题 | 理由 |
|---|---|---|
| P0 | #1 预翻译 | 最快修复，用户影响最大（所有中文用户看到的都是英文） |
| P1 | #4 Bug 修复 | 阻断性问题（开始学习 → 被登出），但需先调查 |
| P2 | #3 自选学习 | 依赖 #1 的数据（需要 `_zh` 字段显示推荐 topic 名称） |
| P3 | #2 学习路径 | 最大变更（新模型 + UI），但独立于其他问题 |

---

## 4. 全局约束

- 继承父 spec 的全部约束：Snowflake ID、`redirect_slashes=False`、`SnowflakeBase`、`UTCDateTime` 等
- 新增 transaction_type 需在 `CoinTransaction` 注释中记录（现有为 String(20)，应用层约定）
- 前端所有用户可见字符串使用 `t('key')`，无硬编码中文
- 新增 API 路由 root-path 使用 `""` 非 `"/"`
- Alembic 迁移使用 `_table_exists` guard 保证幂等性
- `*_zh` 字段遵循现有模式：`json_text` mixin for JSON 字段

---

## 5. 验收标准

### #1 预翻译
- [ ] `seed_learning_topics.py --skip-translation` 正常运行
- [ ] `seed_learning_topics.py` 默认执行翻译 pass，所有 topic 的 `*_zh` 字段被填充
- [ ] 中文 locale 用户进入 LearningTopicPage，标题/描述/evidence 显示中文
- [ ] 英文 locale 用户看到英文原文
- [ ] "翻译成中文"按钮已从 UI 移除
- [ ] 家长端 topic 选择器显示中文 topic 名称

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
- [ ] 难度高于年龄组时显示非阻塞提示
- [ ] 提示包含同科目推荐 topic
- [ ] 自选学习自动创建 `self_selected` assignment
- [ ] 自选学习完成后正常获得 coins

### #4 Bug 修复
- [ ] 点击"开始学习"正常进入 AI 对话页面
- [ ] 不再出现空白 tooltip
- [ ] 不再被强制退出登录
- [ ] 根因已确定并记录
