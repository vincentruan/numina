---
date: 2026-05-19
topic: blindbox-trigger-expansion
status: confirmed
---

# BlindBox Trigger Expansion — Milestone & Challenge Grants

## Problem Frame

**用户痛点：** 孩子目前只能通过手动花费金币或固定的 `base_draw_prob` 概率获得盲盒抽奖机会。这错过了两个关键激励时刻：
1. 庆祝持续努力模式（连续打卡、累计任务量）
2. 家长主动设置目标激励（而非被动响应心愿）

**核心机会：** 
- 连续打卡里程碑已有 `_compute_streak()` 和 `streak_count` 基础设施，扩展成本低
- 挑战授予建立家长→孩子的主动激励通道，与心愿进度模式互补

**设计约束：**
- 复用现有 milestone 系统结构，不新建调度器
- 挑战进度更新在审批事务内原子执行
- 失败不阻塞审批主流程（try/except 包裹）

**现有基础设施：**
- `User.total_approved_count` — 累计完成任务数
- `_STREAK_MILESTONES = {7, 14, 30}` — 连续打卡阈值
- `_ONCE_PER_CHILD` — 一次性里程碑集合
- `should_upgrade_surprise()` — 惊喜池升级判断
- `ChildMilestone` — 里程碑记录表
- `BonusDraw` — 免费抽奖机会

---

## Requirements

### R1. 扩展连续打卡里程碑（streak_3）

**新增阈值：** `{3: "streak_3"}` 加入 `_STREAK_MILESTONES`
**复触发规则：** 加入 `_PER_CYCLE` 集合，每次新周期可再次触发
**奖励：** 创建 `BlindBoxDraw`，`is_surprise=True`，使用惊喜池（value_score >= 7）

### R2. 新增累计任务里程碑（tasks_10/25/50/100）

**新增阈值：** `_TASK_MILESTONES = {10: "tasks_10", 25: "tasks_25", 50: "tasks_50", 100: "tasks_100"}`
**一次性规则：** 加入 `_ONCE_PER_CHILD`，每个孩子终身只触发一次
**数据来源：** 每次审批时 `child.total_approved_count += 1`，检查阈值
**奖励：** 同 streak 里程碑，惊喜池抽奖

### R3. 里程碑触发抽奖统一逻辑

**触发时机：** 在 `check_and_record_milestones()` 中，里程碑记录后调用 `_create_milestone_draw()`
**抽奖参数：**
- `coins_spent=0`
- `is_surprise=True`
- `is_auto_triggered=True`
- `status="pending_fulfillment"`
**错误处理：** 失败记录审计日志，不阻塞审批

### R4. ChallengeGrant 数据模型

**新增表 `challenge_grants`：**
```
id: BigInteger PK (Snowflake)
family_id: BigInteger FK families.id
child_user_id: BigInteger FK users.id
target_type: str(20) — 'task_count' | 'streak_length' | 'specific_chore' | 'star_earnings'
target_value: Integer
chore_template_id: BigInteger FK chore_templates.id (nullable, specific_chore 类型必填)
current_progress: Integer default 0
deadline: DateTime
message: str(100) nullable
status: str(20) — 'active' | 'completed' | 'expired' | 'cancelled'
completed_at: DateTime nullable
created_at, updated_at: DateTime
```

**约束：**
- `CheckConstraint(status IN ('active', 'completed', 'expired', 'cancelled'))`
- `CheckConstraint(target_type IN ('task_count', 'streak_length', 'specific_chore', 'star_earnings'))`

### R5. 挑战类型与进度逻辑

| target_type | 进度更新逻辑 |
|------------|-------------|
| task_count | 每次审批 `current_progress += 1` |
| streak_length | 检查 `instance.streak_count >= target_value` |
| specific_chore | 仅匹配 `chore_template_id` 时 `+= 1` |
| star_earnings | 累加 `coin_reward + streak_bonus` |

### R6. 挑战完成奖励

**触发条件：** `current_progress >= target_value` 且状态为 `active`
**奖励内容：** 创建 `BonusDraw`，`expires_at = now + 7 days`，`source_challenge_id = challenge.id`
**状态变更：** `status = "completed"`，`completed_at = now()`

### R7. 挑战过期处理

**懒检查：** 在 `check_challenge_progress()` 中，审批前检查 `deadline < now()`
**过期操作：** `status = "expired"`，不发放奖励
**不阻塞：** 所有挑战操作包裹 try/except

### R8. 挑战取消

**端点：** `POST /api/v1/challenges/{id}/cancel`
**权限：** 仅家长
**限制：** 仅 `active` 状态可取消

### R9. 同时活跃挑战数

**限制：** 每个孩子同时最多 3 个 `active` 状态挑战
**创建检查：** 创建前验证 `count(active challenges for child) < 3`

### R10. BonusDraw 扩展

**新增字段：** `source_challenge_id: BigInteger FK challenge_grants.id nullable`
**来源追踪：** 与现有 `source_wish_id` 并存

---

## Scope Boundaries

### In Scope
- streak_3 里程碑
- tasks_10/25/50/100 里程碑
- 里程碑触发抽奖（惊喜池）
- 四种类型的家长挑战
- 进度追踪与完成奖励
- 过期与取消处理
- 子端挑战进度展示
- 家长端挑战创建界面

### Deferred for Follow-Up
- 挑战完成推送通知（等待通知基础设施）
- 挑战模板/预设
- 家庭多人挑战

### Outside Identity
- 直接金币奖励（仅抽奖）
- 徽章/成就系统

---

## Success Criteria

1. 孩子连续打卡3天后触发里程碑抽奖
2. 孩子累计完成10/25/50/100个任务时触发里程碑抽奖
3. 家长可创建4种类型的挑战，设置截止时间和鼓励消息
4. 孩子可看到活跃挑战进度条
5. 挑战完成时获得7天有效期的免费抽奖机会
6. 过期挑战不发放奖励
7. 所有操作不阻塞审批主流程