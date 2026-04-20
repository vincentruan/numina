# Observability Design

**Date:** 2026-04-20
**Status:** Approved
**Scope:** 可观测性系统，记录操作历史和资产状态快照

---

## Problem

系统缺乏操作历史记录和资产状态快照，无法追溯资产变更、审计用户操作、对比历史数据。用户无法查看"上周净资产是多少"、"这笔资产什么时候买的"等历史信息。

---

## Goals

1. 记录关键操作历史（资产/负债 CRUD）
2. 定期生成净资产快照
3. 支持历史数据查询和对比
4. 提供审计追溯能力

---

## Architecture

### 双层记录机制

**Activity 日志**：记录用户操作（create/update/delete/sell/retire/payment）
**Snapshot 快照**：记录系统状态（总资产/总负债/净资产）

```
用户操作 → 触发 Activity 记录 → 存储操作日志
定时任务 → 生成 Snapshot → 存储净资产快照
```

---

## Implementation Details

### Activity 日志

**触发时机**

| 操作类型 | 实体类型 | 触发时机 |
|----------|----------|----------|
| create | asset | 资产创建 |
| update | asset | 资产更新（价值变更） |
| delete | asset | 资产删除 |
| sell | asset | 资产出售 |
| retire | asset | 资产退役 |
| create | liability | 负债创建 |
| payment | liability | 负债还款 |

**Activity 模型**

```python
class Activity(Base):
    __tablename__ = "activities"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    family_id: Mapped[str]  # FK -> families.id
    user_id: Mapped[str]    # FK -> users.id
    type: Mapped[str]       # 'create' | 'update' | 'delete' | 'sell' | 'retire' | 'payment'
    entity_type: Mapped[str]  # 'asset' | 'liability'
    entity_id: Mapped[str]  # FK -> assets.id or liabilities.id
    title: Mapped[str]      # 操作描述
    amount: Mapped[float | None]  # 金额（如有）
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

**日志记录函数**

```python
def log_activity(
    user: User,
    type: str,
    entity_type: str,
    entity_id: str,
    title: str,
    amount: float | None = None,
    db: Session
):
    activity = Activity(
        family_id=user.family_id,
        user_id=user.id,
        type=type,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        amount=amount
    )
    db.add(activity)
    db.commit()
```

**使用示例**

```python
# 资产创建后记录
log_activity(
    user=current_user,
    type="create",
    entity_type="asset",
    entity_id=asset.id,
    title=f"创建资产：{asset.name}",
    amount=asset.purchase_price,
    db=db
)

# 资产出售后记录
log_activity(
    user=current_user,
    type="sell",
    entity_type="asset",
    entity_id=asset.id,
    title=f"出售资产：{asset.name}",
    amount=asset.sell_price,
    db=db
)
```

### Snapshot 快照

**触发方式**

| 方式 | 触发时机 | 说明 |
|------|----------|------|
| 手动 | 用户点击"生成快照" | 按需生成 |
| 自动 | 每日 00:00 | 定时任务生成 |

**Snapshot 模型**

```python
class AssetSnapshot(Base):
    __tablename__ = "asset_snapshots"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    family_id: Mapped[str]  # FK -> families.id
    total_assets: Mapped[float]  # 总资产
    total_liabilities: Mapped[float]  # 总负债
    net_worth: Mapped[float]  # 净资产
    snapshot_type: Mapped[str]  # 'manual' | 'auto'
    user_id: Mapped[str | None]  # 手动快照记录操作用户
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

**快照生成函数**

```python
def generate_snapshot(family_id: str, snapshot_type: str, user_id: str | None, db: Session):
    # 计算当前净资产
    assets = db.query(Asset).filter(Asset.family_id == family_id).all()
    liabilities = db.query(Liability).filter(Liability.family_id == family_id).all()
    
    total_assets = sum(a.current_value for a in assets if a.status not in ['sold', 'retired'])
    total_liabilities = sum(l.remaining_amount for l in liabilities if l.is_active)
    net_worth = total_assets - total_liabilities
    
    snapshot = AssetSnapshot(
        family_id=family_id,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        net_worth=net_worth,
        snapshot_type=snapshot_type,
        user_id=user_id
    )
    db.add(snapshot)
    db.commit()
    return snapshot
```

**定时任务配置**

```python
# scheduler.py
scheduler.add_job(
    generate_auto_snapshots,
    trigger='cron',
    hour=0,
    minute=0,
    id='daily_snapshot'
)

def generate_auto_snapshots():
    db = next(get_db())
    families = db.query(Family).all()
    for family in families:
        generate_snapshot(family.id, 'auto', None, db)
```

### 活动日志查询

**API 端点**：`GET /api/v1/activities`

**查询参数**

| 参数 | 说明 |
|------|------|
| entity_type | 过滤实体类型（asset/liability） |
| type | 过滤操作类型 |
| start_date | 开始日期 |
| end_date | 结束日期 |
| limit | 返回数量（默认 50） |

**响应格式**

```json
{
  "items": [
    {
      "id": "uuid",
      "type": "create",
      "entity_type": "asset",
      "entity_id": "uuid",
      "title": "创建资产：MacBook Pro",
      "amount": 15000,
      "created_at": "2026-04-20T10:30:00Z"
    }
  ],
  "total": 100
}
```

---

## Verification

- 资产创建后，Activity 表新增记录
- 资产出售后，Activity 记录 sell 类型
- 手动生成快照成功，Snapshot 表新增记录
- 定时任务每日生成快照
- 活动日志查询返回正确结果

---

## Code Pointers

| 功能 | 文件路径 |
|------|----------|
| Activity 模型 | `backend/app/models/activity.py` |
| Activity 服务 | `backend/app/services/activity.py` |
| Snapshot 模型 | `backend/app/models/snapshot.py` |
| Snapshot 服务 | `backend/app/services/snapshot.py` |
| Activity 端点 | `backend/app/routers/activities.py` |
| 定时任务 | `backend/app/scheduler.py` |

---

## Related Specs

- **数据模型设计**：`2026-04-20-data-models-design.md` — Activity、Snapshot 实体
- **架构设计**：`2026-04-20-architecture-design.md` — 定时任务调度