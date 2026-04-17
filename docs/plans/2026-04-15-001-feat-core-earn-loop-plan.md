---
date: 2026-04-15
id: 2026-04-15-001
title: 核心赚取循环 (Core Earn Loop)
status: active
origin: docs/brainstorms/2026-04-15-core-earn-loop-requirements.md
---

# 核心赚取循环实现计划

## Problem Frame

儿童身份系统（创意点1）已完成，孩子可以登录但无事可做。本计划实现完整的赚取循环：家务模板 → 按需生成实例 → 孩子标记完成 → 父母审批 → CoinTransaction 入账 → 孩子账本展示。这是后续心愿兑现、连续打卡、宝贝画廊的基础。

(see origin: docs/brainstorms/2026-04-15-core-earn-loop-requirements.md)

## Scope

**In scope:**
- `ChoreTemplate` 模型 + CRUD（父母端）
- `ChoreInstance` 模型 + 按需生成逻辑（幂等）
- `CoinTransaction` 模型（append-only 账本）
- 父母审批队列 + 自动批准（惰性计算，仅父母读取时触发）
- AI 叙事生成（2s 超时 + 固定模板兜底）
- 父母手动奖励（parent_grant）
- `streak_count` 计算存储（不实现加成逻辑）
- `require_parent` 依赖（owner/member，拒绝 child）
- `Family.auto_approve_hours` 配置字段
- 前端：家务页（孩子端）、审批队列（父母端）、账本视图（孩子端）

**Out of scope:**
- 照片上传证明
- 公共模板库
- 连续打卡加成（创意点4）
- 兄弟姐妹积分赠送（创意点7）
- parent_grant 负数扣除

## Prerequisites

- 创意点1（儿童身份系统）已合并：`User.role='child'`、`require_adult` dep、`/child/*` 路由树、子账户 CRUD
- 该计划在 `numina-child-identity` worktree（feat/child-identity-system 分支）的基础上继续开发

## Architecture Decisions

### 1. 新增模型：ChoreTemplate

```
ChoreTemplate
  id: UUID PK
  family_id: FK families.id
  name: str(100) NOT NULL
  emoji: str(10) nullable          # 从预设集选择
  coin_reward: int NOT NULL        # 铜币，正整数
  frequency: str(10) NOT NULL      # 'daily' | 'weekly'
  assignment_type: str(10) NOT NULL # 'assigned' | 'pool'
  is_active: bool default True
  created_by: FK users.id
  created_at: DateTime
  updated_at: DateTime

ChoreTemplateAssignee (关联表)
  template_id: FK chore_templates.id
  child_user_id: FK users.id
  PRIMARY KEY (template_id, child_user_id)
```

### 2. 新增模型：ChoreInstance

```
ChoreInstance
  id: UUID PK
  template_id: FK chore_templates.id
  family_id: FK families.id
  child_user_id: FK users.id
  chore_name: str(100) NOT NULL    # 快照，防止模板删除后丢失名称
  chore_emoji: str(10) nullable    # 快照
  coin_reward: int NOT NULL        # 快照
  date_bucket: str(10) NOT NULL    # YYYY-MM-DD（每日）或 YYYY-Www（每周）
  status: str(20) default 'available'  # available/pending_approval/approved/rejected
  submitted_at: DateTime nullable
  approved_at: DateTime nullable
  streak_count: int default 0      # 批准时更新，供 AI 叙事和创意点4使用
  created_at: DateTime

UNIQUE (template_id, child_user_id, date_bucket)  # 幂等约束
```

### 3. 新增模型：CoinTransaction

```
CoinTransaction
  id: UUID PK
  family_id: FK families.id
  child_user_id: FK users.id
  amount: int NOT NULL             # 正=收入，负=支出，铜币整数
  transaction_type: str(20) NOT NULL  # 'chore_earn' | 'wish_spend' | 'parent_grant'
  ref_id: str(36) nullable         # 关联实例/心愿 ID，无 FK，应用层校验
  narrative: str(200) nullable     # chore_earn: AI生成；parent_grant: 父母填写
  narrative_emoji: str(20) nullable # 1-3个表情符号
  created_at: DateTime

UNIQUE (ref_id, transaction_type)  # 幂等约束，防止并发双写
```

### 4. Family 模型扩展

新增字段：`auto_approve_hours: int default 24`（范围 1-168，仅 owner 可修改）

### 5. 新增 require_parent 依赖

在 `backend/app/auth/deps.py` 新增：
```python
def require_parent(user: User = Depends(get_current_user)) -> User:
    if user.role == "child":
        raise HTTPException(403, "需要父母权限")
    return user
```
（接受 owner/member，拒绝 child。与已有 `require_adult` 语义相同，可复用。）

> 注：child identity worktree 已有 `require_adult`，合并后直接复用，无需新增。

### 6. 按需生成实例（幂等）

服务层逻辑（`services/chores.py`）：
```
def get_or_create_instance(db, template, child_user_id, date_bucket):
    try:
        instance = ChoreInstance(...)
        db.add(instance)
        db.flush()  # 触发唯一约束
        return instance
    except IntegrityError:
        db.rollback()
        return db.query(ChoreInstance).filter_by(
            template_id=template.id,
            child_user_id=child_user_id,
            date_bucket=date_bucket
        ).one()
```

### 7. 自动批准（惰性计算，仅父母读取时触发）

父母读取审批队列时，对每个 `pending_approval` 实例检查：
```
if instance.submitted_at + timedelta(hours=family.auto_approve_hours) <= now:
    _auto_approve(db, instance, family)
```

`_auto_approve` 使用原子状态转换：
```
rows = db.execute(
    UPDATE chore_instances SET status='approved', approved_at=now
    WHERE id=? AND status='pending_approval'
)
if rows.rowcount == 1:
    _write_coin_transaction(db, instance, narrative=fallback_template)
    # 自动批准不调用 AI（无父母上下文，用固定模板）
```

孩子读取自己的实例时：不触发自动批准写入，仅展示"审批中"状态。

### 8. AI 叙事生成（2s 超时 + 兜底）

审批端点为 `async def`，使用：
```python
async with httpx.AsyncClient(timeout=2.0) as client:
    resp = await client.post(
        f"{settings.AGENT_BASE_URL}/narrative/chore",
        json={"child_name": ..., "chore_name": ..., "coins": ..., "streak": ...},
        headers={"X-Agent-Token": settings.AGENT_INTERNAL_TOKEN},
    )
    narrative = resp.json()["narrative"]
    emoji = resp.json()["emoji"]
except (httpx.TimeoutException, Exception):
    narrative = f"你完成了{chore_name}！获得 {coins} 颗星"
    emoji = "⭐"
```

若 `family.ai_enabled=False`，跳过 httpx 调用，直接使用固定模板。

> 注：agent 服务是否已有 `/narrative/chore` 端点需在实现阶段确认；若无，可复用 `/chat/ask` 端点并在 prompt 中指定格式。

### 9. streak_count 计算

批准时（手动或自动）：
```python
prev = db.query(ChoreInstance).filter(
    ChoreInstance.template_id == instance.template_id,
    ChoreInstance.child_user_id == instance.child_user_id,
    ChoreInstance.status == 'approved',
    ChoreInstance.date_bucket < instance.date_bucket,
).order_by(ChoreInstance.date_bucket.desc()).first()

if prev and is_consecutive(prev.date_bucket, instance.date_bucket, template.frequency):
    instance.streak_count = prev.streak_count + 1
else:
    instance.streak_count = 1
```

## Implementation Units

### Unit 1: 数据模型 + 迁移

**Files:**
- `backend/app/models/chore.py` — ChoreTemplate, ChoreTemplateAssignee, ChoreInstance
- `backend/app/models/coin_transaction.py` — CoinTransaction
- `backend/app/models/__init__.py` — 注册新模型
- `backend/alembic/versions/<hash>_add_core_earn_loop.py` — 迁移：新建4张表 + Family.auto_approve_hours

**Key constraints:**
- `UNIQUE (template_id, child_user_id, date_bucket)` on ChoreInstance
- `UNIQUE (ref_id, transaction_type)` on CoinTransaction
- `chore_name`/`chore_emoji`/`coin_reward` 快照字段（防模板删除后丢失）

**Test file:** `backend/tests/test_chore_models.py`

**Test scenarios:**
- ChoreInstance 唯一约束：同一 template+child+date_bucket 插入两次，第二次抛 IntegrityError
- CoinTransaction 唯一约束：同一 ref_id+transaction_type 插入两次，第二次抛 IntegrityError
- ChoreInstance.streak_count 默认为 0

---

### Unit 2: 家务模板 CRUD（父母端）

**Files:**
- `backend/app/schemas/chore.py` — ChoreTemplateCreate, ChoreTemplateUpdate, ChoreTemplateResponse
- `backend/app/services/chores.py` — create_template, list_templates, update_template, delete_template, toggle_template
- `backend/app/routers/chores.py` — POST/GET/PATCH/DELETE /family/chore-templates
- `backend/app/main.py` — 注册 chores router

**Auth:** 所有端点使用 `require_adult`（已在 child identity 中实现）

**Key behaviors:**
- 创建时验证 assignee user_id 均属于同一 family 且 role='child'
- 删除模板：软删除（`is_active=False`）或硬删除均可，但不影响已有 ChoreInstance 记录
- 禁用模板：`is_active=False`，孩子端不再生成新实例

**Test file:** `backend/tests/test_chore_templates.py`

**Test scenarios:**
- 创建模板（daily/weekly，assigned/pool）
- 创建模板时 assignee 不属于同一 family → 422
- 创建模板时 assignee role != 'child' → 422
- 列出模板按频率分组
- 更新模板名称/奖励
- 删除模板后历史实例 chore_name 快照不变
- child 角色调用创建端点 → 403

---

### Unit 3: 家务实例按需生成

**Files:**
- `backend/app/services/chores.py` — get_or_create_instances(db, child_user, local_date)
- `backend/app/routers/chores.py` — GET /child/chores?date=YYYY-MM-DD

**Key behaviors:**
- 客户端传入 `date` 查询参数（YYYY-MM-DD），服务器不自行推算时区
- 每周模板的 date_bucket 格式：`YYYY-Www`（ISO week，从 date 计算）
- 禁用模板（`is_active=False`）不生成新实例，已有 available 实例隐藏
- 并发安全：INSERT OR IGNORE（IntegrityError catch + SELECT fallback）
- 返回该孩子当日所有实例（含 available/pending_approval/approved/rejected）

**Test file:** `backend/tests/test_chore_instances.py`

**Test scenarios:**
- 首次打开：生成当日实例
- 再次打开：返回已有实例，不重复创建
- 并发模拟：两次调用同一 template+child+date，只有一个实例
- 禁用模板后不生成新实例
- 每周模板：同一自然周内只生成一个实例
- child 角色只能查看自己的实例（不能查看兄弟姐妹）

---

### Unit 4: 孩子标记完成 + 父母审批队列

**Files:**
- `backend/app/schemas/chore.py` — ChoreInstanceResponse, ApproveRequest, RejectRequest
- `backend/app/services/chores.py` — mark_complete, approve_instance, reject_instance, list_pending_approvals
- `backend/app/routers/chores.py`:
  - POST /child/chores/{instance_id}/complete — 孩子标记完成
  - GET /family/chore-approvals — 父母审批队列（触发自动批准检查）
  - POST /family/chore-approvals/{instance_id}/approve — 父母批准
  - POST /family/chore-approvals/{instance_id}/reject — 父母拒绝（含 return_to_redo 选项）

**Auth:**
- `/child/chores/*/complete` → `get_current_child_user`（仅 child）
- `/family/chore-approvals/*` → `require_adult`（owner/member，拒绝 child）

**Key behaviors:**
- `mark_complete`：`available` → `pending_approval`，设置 `submitted_at=now`
- `approve_instance`：原子 UPDATE WHERE status='pending_approval'，rowcount==1 才写 CoinTransaction
- `reject_instance`：`pending_approval` → `rejected`；若 `return_to_redo=True` 则重置为 `available`
- 审批队列读取时触发自动批准（见 Architecture Decision 7）

**Test file:** `backend/tests/test_chore_approvals.py`

**Test scenarios:**
- 孩子标记完成：available → pending_approval
- 孩子重复标记完成 → 422（已在 pending_approval）
- 父母批准：写入 CoinTransaction，实例变 approved
- 父母拒绝（默认）：实例变 rejected，孩子端显示"今日已被拒绝"
- 父母拒绝（退回重做）：实例重置为 available
- 自动批准：submitted_at + 24h <= now，父母读取队列时触发，写入 CoinTransaction
- 自动批准幂等：同一实例两次触发，只写一条 CoinTransaction（唯一约束保证）
- 孩子读取自己的超时实例：不触发自动批准，仅显示"审批中"
- child 角色调用审批端点 → 403

---

### Unit 5: CoinTransaction 账本 + AI 叙事

**Files:**
- `backend/app/schemas/coin_transaction.py` — CoinTransactionResponse, GrantRequest
- `backend/app/services/coin_transactions.py` — write_chore_earn, write_parent_grant, get_balance, list_transactions
- `backend/app/services/chore_narrative.py` — generate_narrative(family, child_name, chore_name, coins, streak) → (narrative, emoji)
- `backend/app/routers/coins.py`:
  - GET /child/coins/ledger — 孩子账本（仅查自己）
  - GET /child/coins/balance — 孩子余额
  - POST /family/children/{child_id}/grant — 父母手动奖励

**Auth:**
- `/child/coins/*` → `get_current_child_user`，强制 `child_user_id == current_user.id`
- `/family/children/*/grant` → `require_adult`

**Key behaviors:**
- `get_balance`：`SELECT SUM(amount) FROM coin_transactions WHERE child_user_id=?`，返回 0 若无记录
- `generate_narrative`：若 `family.ai_enabled=False` 直接返回固定模板；否则 httpx 2s 超时，TimeoutException/Exception 均降级为固定模板
- `write_chore_earn`：INSERT OR IGNORE（唯一约束 ref_id+transaction_type）
- 账本视图：按 created_at 倒序，相对时间（今天/昨天/N天前），不显示 ref_id

**Test file:** `backend/tests/test_coin_transactions.py`

**Test scenarios:**
- 批准后 CoinTransaction 写入，余额增加
- 余额计算：多笔交易 SUM 正确
- 孩子只能查自己的账本（查他人 → 403）
- 父母可查家庭内任意孩子账本
- parent_grant：直接写入，不经审批
- parent_grant 金额超出 1-100 范围 → 422
- AI 叙事：family.ai_enabled=False → 固定模板
- AI 叙事：httpx 超时 → 固定模板，不阻塞批准
- CoinTransaction 幂等：同一 ref_id+transaction_type 重复写入，只有一条记录

---

### Unit 6: streak_count 计算

**Files:**
- `backend/app/services/chores.py` — `_compute_streak(db, instance, template)` 内联在 approve 流程中

**Key behaviors:**
- 批准时查询同一 template+child 的最近一次 approved 实例
- 每日模板：前一天有 approved 实例 → streak+1，否则 streak=1
- 每周模板：前一自然周有 approved 实例 → streak+1，否则 streak=1
- 自动批准也更新 streak_count

**Test file:** `backend/tests/test_chore_approvals.py`（追加到 Unit 4 测试文件）

**Test scenarios:**
- 首次完成：streak_count=1
- 连续两天完成：streak_count=2
- 中断一天后完成：streak_count=1（重置）
- 每周模板连续两周：streak_count=2

---

### Unit 7: Family.auto_approve_hours 配置

**Files:**
- `backend/app/models/family.py` — 新增 `auto_approve_hours: int default 24`
- `backend/alembic/versions/<hash>_add_core_earn_loop.py` — 包含此字段（与 Unit 1 同一迁移）
- `backend/app/routers/family.py` — PATCH /family/settings 新增 auto_approve_hours 字段（仅 owner 可修改）

**Test scenarios:**
- owner 修改 auto_approve_hours → 成功
- member 修改 auto_approve_hours → 403
- 超出范围（0 或 169）→ 422

---

### Unit 8: 前端 — 孩子端家务页

**Files:**
- `frontend/src/api/chores.ts` — getMyChores(date), markComplete(instanceId)
- `frontend/src/pages/child/ChildChoresPage.vue` — 当日家务列表，标记完成按钮
- `frontend/src/pages/child/ChildLedgerPage.vue` — 账本视图（emoji + 叙事 + 相对时间）

**Key behaviors:**
- 打开时传入 `new Date().toISOString().slice(0,10)` 作为 date 参数
- 实例状态展示：available（可完成）/ pending_approval（审批中）/ approved（已获得星星）/ rejected（今日已被拒绝）
- 账本：按时间倒序，+N颗星 / -N颗星，不显示货币金额

---

### Unit 9: 前端 — 父母端审批队列

**Files:**
- `frontend/src/api/chores.ts` — getPendingApprovals(), approveChore(id), rejectChore(id, returnToRedo)
- `frontend/src/api/coins.ts` — grantCoins(childId, amount, reason)
- `frontend/src/pages/ChoreApprovalsPage.vue` — 审批队列，批准/拒绝/退回重做
- `frontend/src/pages/ChildDetailPage.vue`（或现有页面）— 手动奖励入口

---

## Sequencing

```
Unit 1 (模型+迁移)
  ↓
Unit 2 (模板 CRUD) ──┐
Unit 3 (实例生成)  ──┤
                     ↓
              Unit 4 (审批队列)
                     ↓
              Unit 5 (账本+AI叙事)
                     ↓
              Unit 6 (streak_count) ← 可与 Unit 5 并行
                     ↓
              Unit 7 (auto_approve_hours 配置)
                     ↓
              Unit 8 (前端孩子端)
                     ↓
              Unit 9 (前端父母端)
```

Unit 2 和 Unit 3 可并行开发（均依赖 Unit 1）。Unit 6 可与 Unit 5 并行（均在 approve 流程中）。

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Agent 服务无 `/narrative/chore` 端点 | 实现时先确认；若无，复用 `/chat/ask` 并在 prompt 中指定输出格式 |
| SQLite 并发写入（IntegrityError 竞态） | INSERT OR IGNORE + SELECT fallback 已在设计中；测试用 StaticPool 单线程，生产用 WAL 模式 |
| child identity 分支未合并到 main | 本计划在 feat/child-identity-system 分支上继续开发，合并时需 rebase |
| streak_count 跨时区边界计算 | v1 使用客户端传入的 date_bucket，不做服务器时区推算；Family.timezone 字段留给后续 |

## Test Coverage Summary

| Unit | Test File | Scenarios |
|------|-----------|-----------|
| 1 | test_chore_models.py | 唯一约束、默认值 |
| 2 | test_chore_templates.py | CRUD、权限、assignee 校验 |
| 3 | test_chore_instances.py | 按需生成、幂等、禁用模板 |
| 4 | test_chore_approvals.py | 状态流转、自动批准、幂等、权限 |
| 5 | test_coin_transactions.py | 账本写入、余额计算、AI 降级、权限 |
| 6 | test_chore_approvals.py | streak 连续/中断/重置 |
| 7 | test_family_settings.py | auto_approve_hours 权限和范围 |

## Existing Patterns to Follow

- **模型定义**：参考 `backend/app/models/asset.py` — `Mapped[str]`、`mapped_column`、`uuid4` 主键
- **路由结构**：参考 `backend/app/routers/wishes.py` — service 层分离，`get_current_user` dep 注入
- **测试 fixture**：参考 `backend/tests/conftest.py` — in-memory SQLite，`client` + `auth_headers` fixture
- **AI 调用**：参考 `backend/app/routers/ai_chat.py:58` — `httpx.AsyncClient`，但本模块捕获 TimeoutException 降级而非抛 504
- **auth dep**：`require_adult`（已在 child identity 分支实现）直接复用，无需新增 `require_parent`
