# Phase 4：智能提醒 — 设计文档

**日期：** 2026-04-26  
**状态：** 已确认，待实现

---

## 概述

为 Numina 添加智能提醒系统，支持四类提醒规则、多渠道推送（Telegram Bot、邮件）、总览页提醒模块。

---

## 功能范围

### 四类提醒规则

| 类型 | `reminder_type` | 触发时机 | 触发条件 |
|------|----------------|---------|---------|
| 大额消费冷静期 | `large_purchase` | 资产写入时实时触发 | `purchase_price` 超过固定阈值 OR 超过家庭近3个月月均支出 × 倍数（满足任一） |
| 资产配置失衡 | `allocation_drift` | 每日 09:20 定时 | 各大类资产占比与 `ai_allocation_target` 目标偏差超过 15% |
| 保险/保修到期 | `expiring_soon` | 每日 09:20 定时 | `warranty_expiry_date` 提前 30 天 warning，提前 7 天 critical |
| 理财产品到期 | `maturity` | 每日 09:20 定时 | `maturity_date` 提前 30 天 warning，提前 7 天 critical |

### 通知渠道

- Telegram Bot（`httpx` 调用 Bot API）
- 邮件（`smtplib` SMTP）
- 渠道配置在设置页管理，支持多渠道、每渠道独立订阅事件类型

---

## 数据模型

### `notification_channel` — 发送渠道

```sql
id              TEXT PRIMARY KEY   -- Snowflake ID
family_id       TEXT NOT NULL      -- 关联家庭
channel_type    TEXT NOT NULL      -- telegram | email
name            TEXT NOT NULL      -- 用户自定义名称，如「家庭群」
config          TEXT NOT NULL      -- JSON 加密存储渠道参数
                                   -- telegram: {bot_token, chat_id}
                                   -- email: {smtp_host, smtp_port, smtp_user, smtp_password, smtp_from, to}
is_enabled      BOOLEAN DEFAULT TRUE
created_at      DATETIME
updated_at      DATETIME
```

### `notification_subscription` — 渠道事件订阅

```sql
id              TEXT PRIMARY KEY
channel_id      TEXT NOT NULL      -- 关联 notification_channel
reminder_type   TEXT NOT NULL      -- large_purchase | allocation_drift | expiring_soon | maturity
created_at      DATETIME
UNIQUE(channel_id, reminder_type)
```

### `reminder` — 提醒记录

```sql
id              TEXT PRIMARY KEY
family_id       TEXT NOT NULL
reminder_type   TEXT NOT NULL      -- large_purchase | allocation_drift | expiring_soon | maturity
title           TEXT NOT NULL
body            TEXT NOT NULL
severity        TEXT NOT NULL      -- info | warning | critical
asset_id        TEXT               -- 可空，关联资产
status          TEXT DEFAULT 'active'  -- active | dismissed | resolved
dismissed_at    DATETIME
resolved_at     DATETIME
notified_channels TEXT DEFAULT '[]'   -- JSON 数组，已推送的 channel_id 列表
created_at      DATETIME
updated_at      DATETIME
```

### `asset` 表新增字段（Alembic 迁移）

```sql
warranty_expiry_date   DATE   -- 保修到期日，可空
maturity_date          DATE   -- 理财产品到期日，可空
```

### `notification_config` 表（大额消费阈值配置，家庭级）

```sql
id                                  TEXT PRIMARY KEY
family_id                           TEXT NOT NULL UNIQUE
large_purchase_threshold_fixed      NUMERIC        -- 固定金额阈值，可空
large_purchase_threshold_multiplier NUMERIC        -- 月均支出倍数，可空
created_at                          DATETIME
updated_at                          DATETIME
```

---

## 后端架构

### 通知模板

发送内容通过模板渲染，模板存储在 `backend/app/services/notification/templates/` 目录，每个 `reminder_type` 对应一个模板文件，支持变量插值。

**模板文件结构：**

```
backend/app/services/notification/templates/
├── large_purchase.json
├── allocation_drift.json
├── expiring_soon.json
└── maturity.json
```

每个模板文件格式：

```json
{
  "telegram": {
    "text": "🛒 *大额消费提醒*\n\n你正在考虑购买 *{asset_name}*，金额 ¥{amount}。\n建议冷静 48 小时再决定。\n\n_Numina 家庭资产管理_"
  },
  "email": {
    "subject": "【Numina】大额消费冷静期提醒",
    "body": "你好，\n\n你正在考虑购买「{asset_name}」，金额 ¥{amount}，超过你设定的大额消费阈值。\n\n建议冷静 48 小时后再做决定。\n\nNumina 家庭资产管理"
  }
}
```

**各模板可用变量：**

| `reminder_type` | 可用变量 |
|----------------|---------|
| `large_purchase` | `{asset_name}`, `{amount}`, `{threshold}` |
| `allocation_drift` | `{category}`, `{current_pct}`, `{target_pct}`, `{drift_pct}` |
| `expiring_soon` | `{asset_name}`, `{expiry_date}`, `{days_left}` |
| `maturity` | `{asset_name}`, `{maturity_date}`, `{days_left}`, `{amount}` |

`sender.py` 加载对应模板文件，用 Python `str.format_map()` 渲染后发送。模板文件可直接编辑，无需改代码。

---

### 新增文件

```
backend/app/
├── models/
│   ├── notification_channel.py
│   ├── notification_subscription.py
│   ├── notification_config.py
│   └── reminder.py
├── schemas/
│   ├── notification_channel.py
│   ├── notification_config.py
│   └── reminder.py
├── services/
│   └── notification/
│       ├── __init__.py
│       ├── sender.py        # Telegram + SMTP 发送封装，加载模板渲染
│       ├── rules.py         # 四类提醒规则引擎
│       ├── dispatcher.py    # 触发入口（定时 + 实时）
│       └── templates/       # 通知模板 JSON 文件
│           ├── large_purchase.json
│           ├── allocation_drift.json
│           ├── expiring_soon.json
│           └── maturity.json
├── routers/
│   ├── notification_channels.py   # CRUD /api/v1/notification-channels
│   ├── notification_config.py     # GET/PUT /api/v1/notification-config
│   └── reminders.py               # GET /api/v1/reminders, PATCH /{id}/dismiss
```

### 触发时机

- **定时触发：** `dispatcher.run_scheduled_checks(db)` — APScheduler 每日 09:20，检测到期类 + 配置失衡
- **实时触发：** `dispatcher.check_on_asset_write(db, asset)` — 资产创建/更新时调用，检测大额消费冷静期

### 幂等保证

规则引擎创建 reminder 前先查询 `family_id + reminder_type + asset_id + status=active` 是否已存在，存在则跳过，不重复创建。

### 发送重试

- 发送失败静默记录日志，`notified_channels` 不更新
- 下次 APScheduler 运行时重试未推送的 `active` reminder，最多重试 3 次后放弃推送（reminder 记录保留）

---

## 前端架构

### 新增文件

```
frontend/src/
├── api/
│   ├── reminders.ts
│   └── notificationChannels.ts
├── stores/
│   └── reminders.ts
├── pages/
│   └── NotificationConfigPage.vue   # 通知渠道配置页
└── components/
    └── dashboard/
        └── SmartRemindersCard.vue   # 总览页智能提醒折叠模块
```

### 总览页智能提醒模块

插入位置：`DashboardPage.vue` AlertCards 下方。

**默认折叠状态（摘要）：**
```
🔔 智能提醒   到期 2 · 失衡 1 · 冷静期 1   ▶
```

**展开后（异步加载，`@change` 触发）：**
- 使用 `van-swipe-cell` 右滑显示「忽略」按钮（与资产列表交互一致）
- 每条提醒显示：图标 + 标题 + 副标题（资产名 · 日期）

### 设置页

`SettingsPage.vue` 新增「通知设置」cell，跳转 `NotificationConfigPage.vue`：
- 渠道列表（支持新增多个渠道）
- 每个渠道：类型选择、名称、参数配置、事件订阅开关
- 密码/token 字段回显为 `••••••`
- 保存前校验：Telegram chat_id 必须为数字，SMTP port 必须为数字

---

## 资产表单变更

- 保险/保修类资产：新增「保修到期日」日期选择器（`warranty_expiry_date`）
- 金融资产类：新增「到期日」日期选择器（`maturity_date`）

---

## 边界情况

| 情况 | 处理方式 |
|------|---------|
| 渠道未配置或 `is_enabled=false` | 跳过该渠道推送，不报错 |
| `ai_allocation_target` 无用户目标 | 跳过配置失衡规则 |
| 大额消费冷静期 48 小时后 | APScheduler 每日自动将超时的 `large_purchase` reminder 置为 `resolved` |
| 同一条件已有 `active` reminder | 幂等跳过，不重复创建 |
| `warranty_expiry_date` / `maturity_date` 为空 | 跳过该资产的到期检测 |
| 发送失败超过 3 次 | 放弃推送，reminder 记录保留，日志记录 |
