# ER 模型重设计规范

**日期：** 2026-04-29  
**分支：** feat/child-frontend-module-split  
**状态：** 待实现

## 背景

当前 schema 存在多处关注点混合问题：Family 表承载了 AI 配置、测试缓存、子经济配置等与家庭实体无关的字段；Asset 表混合了生命周期事件；Reminder 表用 JSON 存储通知渠道；ChildWish 用 JSON 存储历史记录；NotificationChannel 用 JSON 存储渠道配置。

目标：每张表只表达一个清晰的概念，关联关系为逻辑关联（不创建数据库外键约束）。

---

## 改动 1：Family 表瘦身

### 现状

Family 表包含 20+ 个与家庭实体无关的字段：AI 配置（6 个）、AI 测试缓存（16 个）、子经济配置（3 个）。

### 目标

Family 表只保留家庭身份信息：

```
families
  id
  name
  custom_title
  invite_code
  created_by
  created_at
```

### 新增表：ai_provider_configs

支持多配置并存（一个家庭可保存多套 AI 配置，不同功能使用不同配置）。

```
ai_provider_configs
  id
  family_id          -- 逻辑关联 families.id
  name               -- 配置名称，如"Claude 主力"、"GPT-4o 视觉"
  provider           -- 'anthropic' | 'openai'
  api_key_encrypted  -- AES-256 Fernet 加密
  base_url           -- 自定义 API 端点，可为空
  model_id           -- 主模型 ID
  vision_model_id    -- 视觉模型 ID，可为空
  is_active          -- 是否为当前激活配置
  created_at
  updated_at
```

### 新增表：ai_provider_test_results

AI 连通性测试结果缓存，按测试类型分行存储（替代原来 16 个扁平字段）。

```
ai_provider_test_results
  id
  config_id    -- 逻辑关联 ai_provider_configs.id
  test_type    -- 'main' | 'thinking' | 'vision' | 'vision_text'
  success      -- Boolean
  message      -- 测试结果描述
  latency_ms   -- 延迟毫秒数
  tested_at    -- 测试时间戳
```

### 新增表：child_economy_configs

子经济系统配置，一对一关联 Family。

```
child_economy_configs
  id
  family_id            -- 逻辑关联 families.id（唯一）
  auto_approve_hours   -- 自动审批小时数，1-168，默认 24
  coin_copper_to_silver  -- 铜币换银币比例，默认 10
  coin_silver_to_gold    -- 银币换金币比例，默认 10
  created_at
  updated_at
```

---

## 改动 2：Asset 生命周期事件拆分

### 现状

Asset 表包含 5 个生命周期字段：`sell_price`、`sell_date`、`sell_fee`、`sell_channel`、`retire_date`。这些是事件数据，不是资产属性。

### 目标

从 Asset 表删除上述 5 个字段，新增 append-only 事件表。

### 新增表：asset_lifecycle_events

```
asset_lifecycle_events
  id
  asset_id      -- 逻辑关联 assets.id
  event_type    -- 'sold' | 'retired'
  event_date    -- 事件发生日期
  sell_price    -- 出售价格，仅 sold 类型有值
  sell_fee      -- 出售手续费，仅 sold 类型有值
  sell_channel  -- 出售渠道，仅 sold 类型有值
  notes         -- 备注
  created_at
```

---

## 改动 3：Reminder 通知渠道规范化

### 现状

`Reminder.notified_channels` 是 JSON 字符串，存储已通知渠道列表。`send_retry_count` 是运营状态字段。

### 目标

从 Reminder 表删除 `notified_channels` 和 `send_retry_count`，新增关联表。

### 新增表：reminder_notifications

```
reminder_notifications
  id
  reminder_id  -- 逻辑关联 reminders.id
  channel_id   -- 逻辑关联 notification_channels.id
  status       -- 'sent' | 'failed'
  sent_at
```

---

## 改动 4：ChildWish 费用历史规范化

### 现状

`ChildWish.star_coin_cost_history` 是 JSON 数组，存储星币费用变更历史。

### 目标

从 ChildWish 表删除 `star_coin_cost_history`，新增 append-only 历史表。

### 新增表：child_wish_cost_history

```
child_wish_cost_history
  id
  wish_id              -- 逻辑关联 child_wishes.id
  old_cost             -- 变更前费用
  new_cost             -- 变更后费用
  changed_by_user_id   -- 逻辑关联 users.id
  changed_at
```

---

## 改动 5：NotificationChannel 配置规范化

### 现状

`NotificationChannel.config` 是加密 JSON 字段，存储不同渠道类型（telegram/email）的配置。

### 目标

从 NotificationChannel 表删除 `config` 字段，新增通用 KV 配置表（灵活支持新渠道类型，无需改 schema）。

### 新增表：notification_channel_configs

```
notification_channel_configs
  id
  channel_id       -- 逻辑关联 notification_channels.id
  key              -- 配置键，如 'bot_token'、'chat_id'、'smtp_server'
  value_encrypted  -- AES-256 Fernet 加密的配置值
  created_at
  updated_at
```

---

## 设计原则

- **无数据库外键约束**：所有关联为逻辑关联，由应用层保证一致性。
- **Append-only 事件表**：`asset_lifecycle_events`、`child_wish_cost_history`、`reminder_notifications` 只追加，不修改。
- **多配置并存**：`ai_provider_configs` 支持一个家庭保存多套 AI 配置，`is_active` 标记当前激活配置。
- **测试结果按行存储**：`ai_provider_test_results` 用 `test_type` 区分测试类型，替代原来 16 个扁平字段。

---

## 影响范围

| 改动 | 涉及模型文件 | 涉及 API 路由 | 迁移复杂度 |
|------|-------------|--------------|-----------|
| Family 拆分 | family.py + 3 个新文件 | /api/families, /api/ai-config | 高（字段多） |
| Asset 生命周期 | asset.py + 1 个新文件 | /api/assets | 中 |
| Reminder 通知 | reminder.py + 1 个新文件 | /api/reminders | 低 |
| ChildWish 历史 | child_wish.py + 1 个新文件 | /api/child-wishes | 低 |
| NotificationChannel | notification_channel.py + 1 个新文件 | /api/notifications | 低 |

**新增表总计：** 8 张  
**修改表总计：** 5 张（删除字段）  
**新增迁移文件：** 至少 2 个（建议按模块分组）
