---
date: 2026-07-28
module: backend + frontend (main)
problem_type: feature-design
applies_when: 需要将原本硬编码的家庭/用户级配置抽象为可自定义的设置项
tags: [settings, configuration, family, user, cache, scheduler, dashboard]
---

# 可配置的家庭/用户设置系统

## 1. 背景与目标

Numina 当前存在大量写死在代码或环境变量中的配置参数（AI 缓存 TTL、Dashboard 阈值、定时任务时间等），这些参数本应属于家庭租户或个人用户的偏好。本方案将这些参数抽象出来，按「家庭设置」（仅家庭管理员可修改）和「用户设置」（个人可修改）分类，提供统一的设置 UI 和可扩展的存储机制。

## 2. 范围

### 2.1 V1 纳入的配置项

#### 家庭设置（family-scoped）

| 分组 | 配置项 key | 当前硬编码 | 默认值 | 范围 | 单位 |
|---|---|---|---|---|---|
| AI 缓存时长 | `ai_cache_ttl_report` | 1 小时 | 60 | 5–480 | 分钟 |
| | `ai_cache_ttl_finance_coach` | 8 小时 | 480 | 60–1440 | 分钟 |
| | `ai_cache_ttl_dashboard_narrative` | 4 小时 | 240 | 30–720 | 分钟 |
| Dashboard 阈值 | `dashboard_min_asset_count` | 5 | 5 | 1–50 | 个 |
| | `dashboard_min_history_months` | 1 | 1 | 1–12 | 月 |
| | `dashboard_expiring_days_threshold` | 180 | 180 | 7–365 | 天 |
| 定时任务 | `scheduled_monthly_report_day` | 1 日 | 1 | 1–28 | 日 |
| | `scheduled_monthly_report_hour` | 8:00 | 8 | 0–23 | 时 |
| | `scheduled_weekly_scan_day` | 周一 | 0 | 0–6 | 星期(0=周一) |
| | `scheduled_weekly_scan_hour` | 8:00 | 8 | 0–23 | 时 |

> **定时任务说明**：`server/apps/agent/app/scheduler.py` 中的两个 job 当前处于注释状态，日志显示「暂无活跃任务」。V1 只负责持久化用户偏好的时间配置，实际启用 scheduler 为后续独立任务。

#### 用户设置（user-scoped）

| 分组 | 配置项 key | 默认值 | 范围/可选值 |
|---|---|---|---|
| 仪表盘偏好 | `dashboard_trend_period` | `month` | `month` / `quarter` / `year` |
| 动态流 | `activity_feed_page_size` | 20 | 5–50 |

#### 明确不迁移的现有配置

- **通知阈值**（`large_purchase_threshold_fixed`、`large_purchase_threshold_multiplier`）已存储在 `notification_configs` 表，并有独立页面 `/settings/notifications/threshold`。新家庭设置页仅提供入口链接，不迁移数据。
- **儿童经济配置**、**债务阈值**、**AI Provider 配置** 维持原有独立表和接口不变。

## 3. 数据模型

### 3.1 新增表

#### `family_settings`

```python
class FamilySetting(Base):
    __tablename__ = "family_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    family_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("family_id", "key", name="uq_family_setting_family_key"),
        Index("ix_family_settings_family_key", "family_id", "key"),
    )
```

#### `user_settings`

与 `family_settings` 结构相同，`family_id` 替换为 `user_id`，约束名为 `uq_user_setting_user_key`。

### 3.2 代码端 Registry

配置项的定义（类型、默认值、边界、可选值）放在 Python 代码中维护，不建 DB 定义表。

文件：`server/apps/backend/app/services/config_registry.py`

```python
class SettingDefinition(BaseModel):
    type: Literal["int", "float", "string", "bool"]
    default: int | float | str | bool
    min: int | float | None = None
    max: int | float | None = None
    step: int | float | None = None
    allowed_values: list[str] | None = None
    scope: Literal["family", "user"]

FAMILY_SETTING_DEFINITIONS: dict[str, SettingDefinition] = {
    "ai_cache_ttl_report": SettingDefinition(
        type="int", default=60, min=5, max=480, step=5, scope="family"
    ),
    # ... 其他家庭配置项
}

USER_SETTING_DEFINITIONS: dict[str, SettingDefinition] = {
    "dashboard_trend_period": SettingDefinition(
        type="string", default="month",
        allowed_values=["month", "quarter", "year"], scope="user"
    ),
    "activity_feed_page_size": SettingDefinition(
        type="int", default=20, min=5, max=50, step=5, scope="user"
    ),
}
```

理由：V1 仅约 12 个家庭 key + 2 个用户 key，代码端维护更简单、类型安全、无需额外 DB 查询。当 key 数量超过 ~30 时，再迁移到 DB-backed 定义表成本也很低。

## 4. 后端 API

### 4.1 路由

| 路由 | 方法 | 鉴权 | 说明 |
|---|---|---|---|
| `/api/v1/family/config` | GET | `require_adult` | 返回家庭全部配置（DB 值与默认值合并） |
| `/api/v1/family/config` | PATCH | `require_owner` | 批量更新，校验后持久化 |
| `/api/v1/family/config/definitions` | GET | `require_adult` | 返回配置定义元数据，供前端渲染 |
| `/api/v1/user/config` | GET | `get_current_user` | 返回用户全部配置 |
| `/api/v1/user/config` | PATCH | `get_current_user` | 批量更新，校验后持久化 |

### 4.2 请求/响应示例

**GET `/api/v1/family/config`**

```json
{
  "ai_cache_ttl_report": 60,
  "ai_cache_ttl_finance_coach": 480,
  "ai_cache_ttl_dashboard_narrative": 240,
  "dashboard_min_asset_count": 5,
  "dashboard_min_history_months": 1,
  "dashboard_expiring_days_threshold": 180,
  "scheduled_monthly_report_day": 1,
  "scheduled_monthly_report_hour": 8,
  "scheduled_weekly_scan_day": 0,
  "scheduled_weekly_scan_hour": 8
}
```

**PATCH `/api/v1/family/config`**

```json
{
  "settings": {
    "ai_cache_ttl_report": 120,
    "dashboard_min_asset_count": 3
  }
}
```

未知 key 或越界值返回 422，非 owner 返回 403。

## 5. 服务层

### 5.1 ConfigService

文件：`server/apps/backend/app/services/config_service.py`

核心职责：

- 读取单条/全部配置，DB 无记录时回退 Registry 默认值。
- 写入时按 Registry 校验类型、范围、allowed_values。
- 序列化/反序列化 value 字段（统一用 JSON）。

### 5.2 热路径缓存

`finance_coach_cache.is_cache_fresh()` 会在每次 AI 请求时被调用。为避免每次查 DB，对配置读取加 5 分钟内存缓存：

```python
@lru_cache(maxsize=256)
def _cached_family_setting(family_id: int, key: str, cache_ts: int) -> Any:
    ...
```

`cache_ts = int(time.time()) // 300`，即按 5 分钟分桶。配置变更最长 5 分钟后生效，对缓存 TTL 类设置可接受。

## 6. 集成点

### 6.1 AI 缓存 TTL

修改 `server/apps/backend/app/services/finance_coach_cache.py`：

- `is_cache_fresh()` 增加可选 `family_id` 参数。
- 传入 `family_id` 时，动态读取 `ai_cache_ttl_{skill_id}`（将 `-` 替换为 `_`）。
- 未传入 `family_id` 时回退原 `SKILL_TTL` 字典，保持向后兼容。

调用方 `ai_finance_coach.py` 和 `ai_report.py` 在调用时传入 `user.family_id`。

### 6.2 Dashboard 叙事阈值

修改 `server/apps/backend/app/services/dashboard_narrative.py`：

- `MIN_ASSET_COUNT` → `get_family_setting(db, family_id, "dashboard_min_asset_count")`
- `MIN_HISTORY_MONTHS` → `get_family_setting(db, family_id, "dashboard_min_history_months")`
- 缓存 TTL 本身通过 `is_cache_fresh()` 的动态读取已经覆盖。

### 6.3 到期资产天数

`server/apps/backend/app/routers/ai_internal.py:103` 的 `days_threshold` 默认值 180，改为从家庭配置读取，允许调用方不传时自动使用配置值。

### 6.4 用户设置消费

- 趋势图默认周期：前端在 Dashboard 初始化时读取 `dashboard_trend_period`，作为默认选中的周期参数。
- 动态流每页条数：前端在请求 `/activities` 时将该值作为 `limit` query 参数传入。

## 7. 前端设计

### 7.1 新增页面

- `frontend/apps/main/src/pages/FamilyConfigPage.vue` → 路由 `/settings/family/config`
- `frontend/apps/main/src/pages/UserConfigPage.vue` → 路由 `/settings/user/config`

### 7.2 UI 模式

- 使用 `van-cell-group inset :title="..."` 分组。
- 数值型配置使用 `van-slider` + `van-field type="number"` 双控件。
- 枚举型配置（趋势周期）使用 `van-field readonly is-link` + `van-popup` + `van-picker`。
- 保存采用 `BlindBoxConfigPage` 的 debounced auto-save 模式（600ms），每次变更后自动保存。

### 7.3 入口

在 `SettingsPage.vue`：

- 「家庭管理」分组下新增 `家庭高级设置`（owner-only）。
- 「用户设置」分组下新增 `个人偏好设置`（所有用户可见）。

### 7.4 前端 API

新增 `frontend/apps/main/src/api/config.ts`：

```typescript
export function getFamilyConfig() { ... }
export function updateFamilyConfig(settings: Partial<FamilyConfigValues>) { ... }
export function getFamilyConfigDefinitions() { ... }
export function getUserConfig() { ... }
export function updateUserConfig(settings: Partial<UserConfigValues>) { ... }
```

## 8. i18n

新增顶层 key：

- `familyConfig.*`：家庭高级设置相关文案。
- `userConfig.*`：个人偏好设置相关文案。
- `settings.familyAdvancedConfig` / `settings.userAdvancedConfig`：主设置页入口标签。

所有 UI 字符串必须同时加入 `zh-CN.ts` 和 `en-US.ts`，Toast 文案放入 `toast.*`。

## 9. 迁移

新增 Alembic migration 创建 `family_settings` 和 `user_settings` 两张表。当前分支若存在多个 alembic head，需先执行 `alembic merge` 合并为单一 head，再编写新 migration。

## 10. 测试策略

### 后端

- `test_family_config.py`：默认值、更新、越界、未知 key、owner 权限、非 owner 写入失败。
- `test_user_config.py`：默认值、越界、allowed_values 校验。
- `test_config_registry.py`：Registry 的 `_validate` / `_deserialize`。
- 回归 `finance_coach_cache` 和 `dashboard_narrative` 现有调用路径。

### 前端

- 手动 QA：滑块边界、自动保存提示、owner 权限隐藏/显示、趋势周期 picker。

## 11. 文件变更清单

### 新增

- `server/packages/db/models/family_setting.py`
- `server/packages/db/models/user_setting.py`
- `server/apps/backend/app/services/config_registry.py`
- `server/apps/backend/app/services/config_service.py`
- `server/apps/backend/app/schemas/config.py`
- `server/apps/backend/app/routers/family_config.py`
- `server/apps/backend/app/routers/user_config.py`
- `server/apps/backend/alembic/versions/<new>_add_family_and_user_settings_tables.py`
- `server/tests/backend/test_family_config.py`
- `server/tests/backend/test_user_config.py`
- `server/tests/backend/test_config_registry.py`
- `frontend/apps/main/src/pages/FamilyConfigPage.vue`
- `frontend/apps/main/src/pages/UserConfigPage.vue`
- `frontend/apps/main/src/api/config.ts`

### 修改

- `server/packages/db/models/__init__.py`
- `server/apps/backend/app/main.py`
- `server/apps/backend/app/services/finance_coach_cache.py`
- `server/apps/backend/app/services/dashboard_narrative.py`
- `server/apps/backend/app/routers/ai_internal.py`
- `server/apps/backend/app/routers/ai_finance_coach.py`
- `server/apps/backend/app/routers/ai_report.py`
- `frontend/apps/main/src/router/index.ts`
- `frontend/apps/main/src/pages/SettingsPage.vue`
- `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- `frontend/apps/main/src/i18n/locales/en-US.ts`

## 12. 实施顺序

1. **数据库与服务基础**：建模型、Registry、Service、Alembic migration。
2. **后端 API**：新增 routers、schemas、注册路由、写测试。
3. **服务集成**：替换 AI 缓存 TTL 和 Dashboard 阈值读取。
4. **前端**：API 模块、两个新页面、路由、入口、i18n。
5. **回归验证**：backend 测试、frontend typecheck。

## 13. 决策记录

- **为何 key-value 表**：用户明确选择；扩展无需 migration；支持 per-key 校验。
- **为何代码端 Registry 而非 DB 定义表**：V1 key 数量少，代码端更轻量、类型安全。
- **为何通知阈值不迁移**：现有表和页面工作正常，迁移收益低、风险高。
- **为何定时任务 V1 只存不配**：scheduler 当前无活跃 job，提前接线无实际价值。
- **为何 5 分钟内存缓存**：AI 缓存判断为热路径，LRU 分桶缓存零基础设施成本，延迟可接受。
