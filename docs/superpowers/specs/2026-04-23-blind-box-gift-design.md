# 盲盒礼物系统设计文档

**日期：** 2026-04-23
**状态：** 待实现
**范围：** 儿童星星币系统扩展 — 盲盒礼物池 + 抽奖机制

---

## 背景与目标

在现有心愿兑现流水线基础上，为儿童激励系统增加盲盒功能，让完成家务的奖励更有创意和惊喜感。

**核心价值：**
- 父母：预设礼物池，营造惊喜氛围，避免孩子提前知道礼物内容
- 孩子：完成家务后可选择抽盲盒，消耗积分越多，抽中高价值礼物的概率越高
- 设计原则：避免赌博心理（权重渐变而非阶梯），保留小概率超预期惊喜

---

## 数据模型

### 新增表：`blind_box_gifts`（礼物池）

```sql
id              BigInt  PK
family_id       BigInt  FK → families.id
name            String(100)  NOT NULL
description     String(200)  nullable
emoji           String(10)   nullable
value_score     Integer      NOT NULL  -- 1-10，父母设定的价值评分
source_wish_id  BigInt       nullable  FK → child_wishes.id（从心愿转入时保留来源）
is_active       Boolean      default=True  -- 归档用，不物理删除
created_by      BigInt       FK → users.id
created_at      DateTime
updated_at      DateTime
```

### 新增表：`blind_box_draws`（抽奖记录）

```sql
id              BigInt  PK
family_id       BigInt  FK → families.id
child_user_id   BigInt  FK → users.id
coins_spent     Integer  NOT NULL  -- 本次消耗的铜币总量
gift_id         BigInt   FK → blind_box_gifts.id
is_surprise     Boolean  default=False  -- 是否触发了超预期惊喜
is_bonus        Boolean  default=False  -- 是否为免费抽奖机会（心愿兑现后触发）
source_wish_id  BigInt   nullable  -- 免费抽奖时，来源心愿 ID
status          String(30)  -- 'pending_fulfillment' | 'fulfilled'
draw_at         DateTime
fulfilled_at    DateTime  nullable
```

### 新增表：`blind_box_config`（家庭盲盒配置）

一家庭一条记录，首次使用时自动创建（使用默认值）。

```sql
id              BigInt  PK
family_id       BigInt  UNIQUE  FK → families.id
enabled         Boolean  default=True

-- 免费抽奖触发概率
base_draw_prob          Float  default=0.30  -- 普通时段（≤0.50）
special_day_prob        Float  default=0.80  -- 特殊节日（0.50-1.00）

-- 权重算法参数
weight_scale            Float    default=2.0   -- 积分对高分礼物的权重加成倍率（0.5-5.0）
surprise_threshold_coins Integer default=200   -- 触发超预期惊喜检定的最低消耗铜币（50-9999）

-- 超预期惊喜概率（各场景）
surprise_prob_normal        Float  default=0.05  -- 日常（0.05-0.20）
surprise_prob_parent_bday   Float  default=0.60  -- 父母生日（0.50-1.00）
surprise_prob_sibling_bday  Float  default=0.50  -- 兄弟姐妹生日（0.50-1.00）
-- 以下两项固定，不可修改：
-- surprise_prob_birthday = 1.00（孩子自己生日）
-- surprise_prob_childrens_day = 1.00（儿童节 6月1日）

created_at  DateTime
updated_at  DateTime
```

### `User` 模型新增字段

```sql
birthday          Date     nullable  -- 生日日期
birthday_is_lunar Boolean  default=False  -- False=公历，True=农历
```

---

## 权重算法

### 基础权重公式

```
gift_weight(score, coins_spent) = score ^ (1 + coins_spent / 100 * weight_scale)
```

**示例**（weight_scale=2.0，礼物池有 1分/5分/10分 三件礼物）：

| 消耗铜币 | 1分权重 | 5分权重 | 10分权重 | 10分中奖率 |
|---------|--------|--------|---------|----------|
| 0铜     | 1.0    | 5.0    | 10.0    | 62.5%    |
| 50铜    | 1.0    | 11.2   | 31.6    | 72.8%    |
| 100铜   | 1.0    | 25.0   | 100.0   | 79.4%    |
| 200铜   | 1.0    | 125.0  | 1000.0  | 88.4%    |

### 超预期惊喜机制

当 `coins_spent >= surprise_threshold_coins` 时，在正常抽奖结果之外，额外触发一次"惊喜检定"：

```python
def check_surprise(coins_spent, config, special_day_type):
    if coins_spent < config.surprise_threshold_coins:
        return False
    prob = get_surprise_prob(config, special_day_type)
    return random() < prob
```

若惊喜检定通过，将抽奖结果替换为礼物池中 `value_score` 最高的礼物（多件同分取随机一件）。

### 特殊日期判定

后端在每次抽奖时判定当天是否为特殊日期，优先级从高到低：

1. 孩子自己生日 → `surprise_prob = 1.00`（固定）
2. 儿童节（6月1日）→ `surprise_prob = 1.00`（固定）
3. 父母生日 → `surprise_prob = config.surprise_prob_parent_bday`
4. 兄弟姐妹生日 → `surprise_prob = config.surprise_prob_sibling_bday`
5. 日常 → `surprise_prob = config.surprise_prob_normal`

取最高优先级，不叠加。

**农历处理：** 若 `User.birthday_is_lunar=True`，使用 `lunardate` 库将农历日期转换为当年对应公历日期后再比较。

---

## 父母端操作流程

### 礼物池管理

父母在"宝贝"页新增"盲盒礼物池"入口，支持两种添加方式：

**方式一：手动添加**
- 填写：名称（必填）、描述（可选）、emoji（可选）、价值评分（1-10滑块）
- 提交时触发重复检查

**方式二：从 ChildWish 转入**
- 父母在心愿管理页，对 `active` 或 `realized` 状态的心愿点击"转为盲盒礼物"
- 系统自动填充名称/emoji，`source_wish_id` 保留来源引用
- 父母只需设定 `value_score`

### 重复检查逻辑

提交时后端查询家庭内所有孩子（role=child）的资产列表，按礼物名称做模糊匹配：

| 情况 | 提示 | 是否阻断 |
|------|------|---------|
| 无孩子拥有 | 无提示 | 否 |
| 部分孩子拥有 | "⚠️ 小明已经有了这个，要继续添加吗？" | 否 |
| 所有孩子都拥有 | "⚠️ 所有孩子都已经有了这个，可能是新款？" | 否 |

### 礼物池列表

- 按 `value_score` 降序排列
- 显示：评分、名称、来源标记（"来自心愿" / "手动添加"）、是否已归档
- 父母可随时归档礼物（`is_active=False`），归档后不进入抽奖池，历史记录保留

---

## 孩子端抽奖流程

### 触发场景一：完成家务后主动选择

家务被父母批准后，进入"奖励领取"页面：
- "实现心愿" → 跳转心愿列表（现有流程）
- "抽盲盒" → 进入积分选择页

**积分选择页：**
- 显示当前余额（金银铜组合）
- 展示所有已批准未消耗的家务，孩子勾选消耗哪些
- 底部显示"本次消耗：XX铜"，确认进入抽奖动画

### 触发场景二：心愿兑现后概率性获得免费抽奖

父母执行心愿兑现后，后端判定是否触发免费抽奖机会：

```python
if random() < get_draw_prob(config, special_day_type):
    create_bonus_draw(child_user_id, source_wish_id, coins_equivalent=wish.star_coin_cost)
```

孩子下次打开 App 时，首页顶部显示"🎁 你获得了一次免费抽奖机会！"横幅，点击直接进入抽奖动画（跳过积分选择）。

免费抽奖的权重计算使用 `coins_equivalent = wish.star_coin_cost`，继承心愿消耗的积分量。

### 抽奖动画页（三阶段）

1. **硬币落入阶段**（1秒）：选中的铜币从顶部落下，带金属碰撞音效
2. **盲盒旋转阶段**（2秒）：3D盲盒在屏幕中央旋转，背景粒子特效
3. **开盒揭晓阶段**（1秒）：盲盒打开，礼物 emoji 放大弹出，彩纸飘落，显示礼物名称和"爸爸妈妈会帮你实现！"

动画结束后显示结果卡片，底部按钮"继续抽" / "回到首页"。

---

## API 端点设计

### 父母端（role=owner 或 role=member）

```
POST   /api/v1/blind-box/gifts
  body: { name, description?, emoji?, value_score, source_wish_id? }
  返回: { gift, duplicate_warning: { has_owners: [child_names], all_have: bool } }

GET    /api/v1/blind-box/gifts
  query: include_archived=false
  返回: [{ id, name, emoji, value_score, source_wish_id, is_active, created_at }]

PUT    /api/v1/blind-box/gifts/{id}
  body: { name?, description?, emoji?, value_score? }

PATCH  /api/v1/blind-box/gifts/{id}/archive

GET    /api/v1/blind-box/config
PUT    /api/v1/blind-box/config  （仅 owner 可调用）

GET    /api/v1/blind-box/draws
  query: child_user_id?, status?
  返回: [{ id, child_name, gift_name, coins_spent, is_surprise, status, draw_at }]

POST   /api/v1/blind-box/draws/{id}/fulfill
```

### 孩子端（role=child）

```
POST   /api/v1/child/blind-box/draw
  body: { chore_instance_ids: [id1, id2] }
  返回: { gift: { id, name, emoji, value_score }, coins_spent, is_surprise }

GET    /api/v1/child/blind-box/bonus-draws
  返回: [{ id, source_wish_name, coins_equivalent }]

POST   /api/v1/child/blind-box/bonus-draws/{id}/use
  返回: { gift, coins_spent: 0, is_surprise }

GET    /api/v1/child/blind-box/my-draws
  返回: [{ gift_name, emoji, coins_spent, draw_at, is_fulfilled }]
```

### 事务原子性（`POST /child/blind-box/draw`）

以下步骤在同一 SQLAlchemy 事务内执行，任一失败全部回滚：

1. 校验 `chore_instance_ids` 都是 `approved` 状态且属于该孩子
2. 计算总铜币数 `coins_spent`
3. 写入负数 `CoinTransaction`（`transaction_type='blind_box_draw'`）
4. 执行权重抽奖算法，判定特殊日期，执行超预期惊喜检定
5. 创建 `BlindBoxDraw` 记录
6. 标记 `chore_instances` 为 `consumed`（新增 `consumed_at` 字段）

---

## 配置项默认值汇总

| 字段 | 默认值 | 范围限制 | 说明 |
|------|--------|---------|------|
| `enabled` | `true` | — | 全局开关 |
| `base_draw_prob` | `0.30` | 0.01–0.50 | 普通时段免费抽奖触发概率 |
| `special_day_prob` | `0.80` | 0.50–1.00 | 特殊节日触发概率 |
| `weight_scale` | `2.0` | 0.5–5.0 | 积分权重加成倍率 |
| `surprise_threshold_coins` | `200` | 50–9999 | 超预期惊喜最低消耗铜币 |
| `surprise_prob_normal` | `0.05` | 0.05–0.20 | 日常超预期概率 |
| `surprise_prob_parent_bday` | `0.60` | 0.50–1.00 | 父母生日超预期概率 |
| `surprise_prob_sibling_bday` | `0.50` | 0.50–1.00 | 兄弟姐妹生日超预期概率 |
| `surprise_prob_birthday` | `1.00` | 固定 | 孩子自己生日 |
| `surprise_prob_childrens_day` | `1.00` | 固定 | 儿童节（6月1日） |

---

## 防赌博设计原则

- 权重连续渐变，50铜和51铜差异微乎其微，不存在"充值越多越好"的阶梯心理
- 低分礼物永远有权重，孩子积分少时不会"必输"
- 超预期惊喜概率有上限（日常最高20%），特殊节日固定值不可调低（≥50%）
- 孩子自己生日和儿童节固定100%超预期，强化节日仪式感而非赌博预期

---

## 依赖关系

- 依赖现有 `ChildWish` 模型（心愿转礼物、免费抽奖来源）
- 依赖现有 `CoinTransaction` 账本（新增 `blind_box_draw` 交易类型）
- 依赖现有 `ChoreInstance` 模型（需新增 `consumed_at` 字段）
- 需引入 `lunardate` Python 库处理农历生日转换
- `User` 模型需新增 `birthday` + `birthday_is_lunar` 字段（Alembic 迁移）

## 范围边界

- 不实现礼物库存管理（礼物池无数量限制，抽中即通知父母兑现）
- 不实现抽奖动画的物理引擎（CSS 动画 + Vue Transition 实现）
- 不实现跨家庭礼物池共享
- 不实现礼物池模板（v1 全部手动添加或从心愿转入）
