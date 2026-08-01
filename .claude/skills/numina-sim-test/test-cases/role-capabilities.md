# Numina 角色能力矩阵 (Role Capabilities Matrix)

Sim-test 用例按角色视角划分覆盖范围。`demouser` 默认角色为 **owner**；
如需测试 **member** 视角，需在 DB 中另建 member 账户或使用 `test_rich` family 的副账号。

## 角色一览

| 角色 | 前端应用 | 认证方式 | 默认账户 |
|------|----------|----------|----------|
| **owner** | main SPA (`:5173` / `/`) | 单步密码 + httpOnly cookie | `demouser` |
| **member** | main SPA (`:5173` / `/`) | 同 owner | 需手动创建 |
| **child** | child SPA (`:5174/child/` / `/child/`) | 两步：密码 + emoji PIN | `小宝`/`大宝` (docker seed) |

## Owner vs Member 权限差异

两者共享大部分财务/AI 功能，差异集中在 **家庭治理**：

| 功能 | owner | member | 后端鉴权 |
|------|:-----:|:------:|----------|
| 查看 Dashboard / Finance / AI | ✅ | ✅ | `require_adult` |
| 创建/编辑/删除 资产/负债/心愿 | ✅ | ✅ | `require_adult` |
| 查看儿童列表及数据 | ✅ | ✅ | `require_adult` |
| 查看盲盒抽奖/礼物 | ✅ | ✅ | `require_adult` |
| 管理标签/分类 | ✅ | ✅ | `require_adult` |
| 查看债务阈值 (read) | ✅ | ✅ | `require_adult` |
| 查看家庭配置 (read) | ✅ | ✅ | `require_adult` |
| **创建/编辑/删除 儿童账户** | ✅ | ❌ | `require_owner` |
| **解锁儿童 PIN** | ✅ | ❌ | `require_owner` |
| **强制登出儿童** | ✅ | ❌ | `require_owner` |
| **审批/驳回家务完成** | ✅ | ❌ | `require_owner` |
| **修改成员角色** | ✅ | ❌ | `require_owner` |
| **修改家庭设置 (经济配置)** | ✅ | ❌ | owner check inline |
| **修改债务阈值 (write)** | ✅ | ❌ | owner check inline |
| **修改家庭配置 (write)** | ✅ | ❌ | owner check inline |
| **管理 Web Search / MCP** | ✅ | ❌ | `require_owner` |
| **转让 ownership** | ✅ | ❌ | `require_owner` |
| **移除成员** | ✅ | ❌ | `require_owner` |
| **重新生成邀请码** | ✅ | ❌ | `require_owner` |
| **Baby Tab (儿童管理)** 可见 | ✅ | ❌ | `v-if="isOwner"` |

## 各角色可见页面清单

### Owner / Member 共享页面 (main SPA)

| 路由 | 页面 | Tab 归属 |
|------|------|----------|
| `/` | DashboardPage | Dashboard |
| `/dashboard/analytics` | AssetAnalyticsPage | — |
| `/finance` | FinanceHubPage (assets/liabilities/wishes tabs) | Finance |
| `/assets/new`, `/assets/:id`, `/assets/:id/edit`, `/assets/:id/sell` | 资产 CRUD | — |
| `/liabilities/new`, `/liabilities/:id`, `/liabilities/:id/edit` | 负债 CRUD | — |
| `/wishes/new`, `/wishes/:id`, `/wishes/:id/edit` | 心愿 CRUD | — |
| `/ai` | AIHubPage | AI |
| `/ai/chat`, `/ai/chat/history` | AI 对话 | — |
| `/ai/report` | AI 资产报告 | — |
| `/ai/time-machine` | AI 时光机 | — |
| `/settings` | SettingsPage | Settings |
| `/settings/categories`, `/settings/tags` | 分类/标签 | — |
| `/settings/ai`, `/settings/ai/provider/*`, `/settings/ai/mcp`, `/settings/ai/web-search*`, `/settings/ai/asr*`, `/settings/ai/skills`, `/settings/ai/agents*` | AI 设置 | — |
| `/settings/devices`, `/settings/notifications*` | 设备/通知 | — |
| `/settings/password`, `/settings/second-factor` | 安全 | — |
| `/settings/import-report` | 导入报告 | — |
| `/settings/user/config` | 用户配置 | — |
| `/family` | FamilyPage (成员列表) | — |
| `/manifesto/template-select`, `/manifesto/edit`, `/manifesto/sign`, `/manifesto/preview` | 家庭宣言 | — |
| `/blind-box/draws`, `/blind-box/gifts*`, `/blind-box/config` | 盲盒 | — |

### Owner-only 页面

| 路由 | 页面 | Tab 归属 |
|------|------|----------|
| `/baby` | BabyPage (儿童总览) | Baby (仅 owner 可见) |
| `/baby/calendar/day` | BabyDayDetailPage | — |
| `/baby/chores/new` | BabyChoreCreatePage | — |
| `/baby/chore-templates`, `/baby/chore-templates/:id/edit` | 家务模板管理 | — |
| `/baby/literacy-report` | LiteracyReportPage | — |
| `/family/chore-approvals` | ChoreApprovalsPage | — |
| `/family/children/:childId/reset` | ChildResetPage | — |
| `/settings/family/coin-rates`, `/settings/family/config`, `/settings/family/debt-thresholds`, `/settings/family/manifesto` | 家庭治理设置 | — |

### 来宾页面 (无需认证)

| 路由 | 页面 |
|------|------|
| `/welcome` | 欢迎页 |
| `/promo/family` | 家庭功能推广 |
| `/promo/developer` | 开发者推广 |
| `/login` | 登录 |
| `/register` | 注册 |
| `/join-family` | 加入家庭 |

### Child 页面 (child SPA)

| 路由 | 页面 | Tab 归属 |
|------|------|----------|
| `/` | ChildHomePage | Home |
| `/wishes` | ChildWishesPage | Wishes |
| `/wishes/new` | ChildWishCreatePage | — |
| `/wishes/:id` | ChildWishDetailPage | — |
| `/tasks` | ChildTasksPage | Tasks |
| `/treasures` | ChildTreasuresPage | Treasures |
| `/assets/:id` | ChildAssetDetailPage | — |
| `/ledger` | ChildLedgerPage | Ledger |
| `/calendar/day` | ChildDayDetailPage | — |
| `/scenario` | ChildScenarioPage | — |
| `/badges` | ChildBadgesPage | — |
| `/manifesto/sign` | ManifestoSigningPage | — |
| `/settings` | ChildSettingsPage | — |

## 用例与角色映射

| Area | 覆盖角色 | 备注 |
|------|----------|------|
| Area 1 (C1.x) | child | 儿童核心功能 |
| Area 2 (C2.x) | owner (demouser) | 财务管理 |
| Area 3 (C3.x) | owner | AI 功能 |
| Area 4 (C4.x) | owner | 导航 + 币种 |
| Area 5 (C5.x) | child | 儿童导航 |
| Area 6 (C6.x) | owner | AI chat 对等性 |
| **Area 7 (R.x)** | **owner** | **回归用例** |
| **Area 8 (F.x)** | **owner + member** | **扩展功能覆盖** |

> **member 视角缺口**: 当前所有 adult 用例均以 `demouser` (owner) 运行。
> member 角色的权限边界测试 (owner-only 页面返回 403) 列入 Area 8 (F.8.x)。
> 完整的 member 功能遍历需额外账户，暂标记为 deferred。
