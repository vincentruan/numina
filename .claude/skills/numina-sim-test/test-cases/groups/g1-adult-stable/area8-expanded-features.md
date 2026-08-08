# Area 8 — Expanded feature coverage (扩展功能覆盖)

Shared conventions in [`_common.md`](../../_common.md).

Auth: adult session as `demouser` (owner)。
本 Area 覆盖当前 **未被 Area 1-6 测试到的功能模块**:
Manifesto 流程、盲盒管理、儿童管理 (Baby)、深度 Settings、来宾页面、权限边界。

> **运行时机:** G1 内排在 area7 之前 (功能优先于回归)。
> 部分用例 (F.8.x 权限边界) 需要 member 角色账户，当前标记为 deferred。

---

## F.1 — Manifesto 家庭宣言流程

Routes: `/manifesto/template-select` → `/manifesto/edit` → `/manifesto/sign` → `/manifesto/preview`
Components: `ManifestoTemplateSelectPage`, `ManifestoEditPage`, `ManifestoSignPage`, `ManifestoPreviewPage`
Composable: `useManifestoWizard` (sessionStorage 持久化)

### F.1.1 Manifesto 模板选择

```
bsk navigate ${BASE}manifesto/template-select --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/f1.1-manifesto-template.png
```

Assertions:
- [ ] 模板列表渲染 (至少 1 个模板可选)
- [ ] 每个模板显示名称 + 预览摘要
- [ ] 选择模板后可进入编辑步骤
- [ ] `[console]` zero errors

### F.1.2 Manifesto 编辑页

```
bsk navigate ${BASE}manifesto/edit --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/f1.2-manifesto-edit.png
```

Assertions:
- [ ] 编辑器渲染 (文本输入区域)
- [ ] 如果已有宣言内容 → 预填充显示
- [ ] 保存/下一步按钮可用
- [ ] `[console]` zero errors

### F.1.3 Manifesto 签署页

```
bsk navigate ${BASE}manifesto/sign --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/f1.3-manifesto-sign.png
```

Assertions:
- [ ] 宣言内容预览可见
- [ ] 签署交互 (签名 / 确认按钮) 可用
- [ ] 签署后状态更新
- [ ] `[console]` zero errors

### F.1.4 Manifesto 预览页

```
bsk navigate ${BASE}manifesto/preview --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/f1.4-manifesto-preview.png
```

Assertions:
- [ ] 已签署宣言的正式预览渲染
- [ ] 内容完整 (标题 + 正文 + 签署信息)
- [ ] `[console]` zero errors

### F.1.5 Manifesto Settings (owner-only)

```
bsk navigate ${BASE}settings/family/manifesto --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 宣言设置页渲染
- [ ] 家庭级宣言配置选项可见
- [ ] `[console]` zero errors

---

## F.2 — Blind Box 盲盒管理 (成人端)

Routes: `/blind-box/draws`, `/blind-box/gifts`, `/blind-box/gifts/new`, `/blind-box/config`
Components: `BlindBoxDrawsPage`, `BlindBoxGiftListPage`, `BlindBoxGiftFormPage`, `BlindBoxConfigPage`

### F.2.1 Blind Box 抽奖记录

```
bsk navigate ${BASE}blind-box/draws --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/f2.1-blindbox-draws.png
```

Assertions:
- [ ] 抽奖记录列表渲染 (如果有历史抽奖)
- [ ] 空态展示友好 (如果没有历史)
- [ ] 每条记录显示奖品信息 + 时间
- [ ] `[console]` zero errors

### F.2.2 Blind Box 礼物池管理

```
bsk navigate ${BASE}blind-box/gifts --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 礼物列表渲染
- [ ] 新增礼物按钮可见 → 导航到 `/blind-box/gifts/new`
- [ ] 编辑入口可见 (列表项可点击进入编辑)
- [ ] `[console]` zero errors

### F.2.3 Blind Box 礼物创建表单

```
bsk navigate ${BASE}blind-box/gifts/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 表单字段渲染 (名称、描述、图片/emoji、数量等)
- [ ] 必填字段验证
- [ ] 提交后返回列表，新礼物出现
- [ ] `[console]` zero errors

### F.2.4 Blind Box 配置页

```
bsk navigate ${BASE}blind-box/config --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/f2.4-blindbox-config.png
```

Assertions:
- [ ] 盲盒配置页渲染
- [ ] 配置项可见 (概率、费用等)
- [ ] `[console]` zero errors

### F.2.5 礼物编辑表单

```
# 从 F.2.1 列表中获取一个 gift ID (via API 或页面内导航)
GIFT_ID=$(curl -s -H "Authorization: Bearer $TOKEN" ${API_BASE}/blind-box/gifts \
  | jq -r '.data[0].id')
bsk navigate ${BASE}blind-box/gifts/${GIFT_ID}/edit --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] GiftEditPage 渲染 — 标题显示"编辑礼物"
- [ ] 表单字段预填充为现有值 (名称/描述/emoji/数量)
- [ ] 修改字段 → 保存 → 返回列表页, 更新生效
- [ ] 返回按钮 (`router.back()`) 正常工作
- [ ] `[console]` zero errors

---

## F.3 — Baby 儿童管理 (owner-only)

Routes: `/baby`, `/baby/calendar/day`, `/baby/chores/new`, `/baby/chore-templates`, `/baby/literacy-report`
Components: `BabyPage`, `BabyDayDetailPage`, `BabyChoreCreatePage`, `BabyChoreTemplatesPage`, `LiteracyReportPage`
Also: `/family/chore-approvals` → `ChoreApprovalsPage`

### F.3.1 Baby 总览页

```
bsk navigate ${BASE}baby --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/f3.1-baby-overview.png
```

Assertions:
- [ ] 儿童列表渲染 (显示 demouser 的 children)
- [ ] 每个儿童卡片显示名字 + 头像/emoji
- [ ] 快捷入口: 家务管理、 literacy report 等
- [ ] `[console]` zero errors

### F.3.2 Baby 日历日视图

```
bsk navigate ${BASE}baby/calendar/day --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 日视图渲染: 显示当天的家务/活动
- [ ] 日期选择器可用
- [ ] `[console]` zero errors

### F.3.3 Baby 家务创建

```
bsk navigate ${BASE}baby/chores/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 表单字段渲染 (名称、emoji、奖励、频率、分配给哪个 child)
- [ ] 必填字段验证
- [ ] `[console]` zero errors

### F.3.4 Baby 家务模板管理

```
bsk navigate ${BASE}baby/chore-templates --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 模板列表渲染
- [ ] 每个模板显示名称 + 奖励 + 频率
- [ ] 编辑入口 → `/baby/chore-templates/:id/edit` 点击可达
- [ ] ChoreTemplateEditPage 渲染 — 表单字段预填充
- [ ] 修改字段 (名称/奖励/频率) → 保存 → 返回列表页, 更新生效
- [ ] `[console]` zero errors

### F.3.5 Baby 素养报告

```
bsk navigate ${BASE}baby/literacy-report --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/f3.5-literacy-report.png
```

Assertions:
- [ ] 素养报告渲染 (badge 进度、维度得分)
- [ ] 四个维度可见 (earning/waiting/caring/其他)
- [ ] `[console]` zero errors

### F.3.6 家务审批页

```
bsk navigate ${BASE}family/chore-approvals --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 待审批列表渲染 (如有 pending completions)
- [ ] 审批/驳回按钮可用
- [ ] 空态友好 (无待审批时)
- [ ] `[console]` zero errors

---

## F.4 — Settings 深度覆盖

覆盖 Area 4 (C4.10-C4.11) 未涉及的设置子页面。

### F.4.1 通知配置

```
bsk navigate ${BASE}settings/notifications --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 通知配置页渲染
- [ ] 通知开关/选项可见
- [ ] `[console]` zero errors

### F.4.2 通知阈值

```
bsk navigate ${BASE}settings/notifications/threshold --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 阈值配置页渲染
- [ ] 阈值字段可编辑
- [ ] `[console]` zero errors

### F.4.3 修改密码

```
bsk navigate ${BASE}settings/password --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 修改密码表单渲染 (旧密码 + 新密码 + 确认)
- [ ] 表单验证 (新密码 ≠ 旧密码, 确认匹配)
- [ ] `[console]` zero errors
- [ ] **不实际提交** — 仅验证 UI 渲染

### F.4.4 双因素认证

```
bsk navigate ${BASE}settings/second-factor --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 双因素认证设置页渲染
- [ ] 当前状态显示 (已启用/未启用)
- [ ] `[console]` zero errors

### F.4.5 设备管理

```
bsk navigate ${BASE}settings/devices --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 设备列表渲染 (当前会话 + 历史设备)
- [ ] `[console]` zero errors

### F.4.6 家庭配置 (owner-only)

```
bsk navigate ${BASE}settings/family/config --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 家庭配置页渲染 (经济参数等)
- [ ] 配置项可编辑
- [ ] `[console]` zero errors

### F.4.7 币种汇率配置

```
bsk navigate ${BASE}settings/family/coin-rates --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 金币兑换率配置页渲染
- [ ] `[console]` zero errors

### F.4.8 债务阈值配置

```
bsk navigate ${BASE}settings/family/debt-thresholds --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 债务阈值配置页渲染
- [ ] 按类别阈值可见
- [ ] `[console]` zero errors

### F.4.9 用户配置

```
bsk navigate ${BASE}settings/user/config --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 用户级配置渲染 (语言、主题、默认币种等)
- [ ] `[console]` zero errors

### F.4.10 导入报告

```
bsk navigate ${BASE}finance/import --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 导入报告页渲染
- [ ] 如有历史导入 → 列表显示
- [ ] 点击历史条目 → 详情 popup 打开 (显示 source + report_date + item list)
- [ ] 详情页含 rollback 按钮 (如有)
- [ ] `[console]` zero errors

### F.4.11 外部存储后端配置

```
bsk navigate ${BASE}settings/family/storage --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] FamilyStorageBackendPage 渲染
- [ ] S3 / WebDAV 配置区域可见
- [ ] 启用/禁用切换开关可操作
- [ ] 必填字段 (endpoint, bucket/prefix, access_key 等) 有 placeholder/label
- [ ] `[console]` zero errors

### F.4.12 用户名修改

```
bsk navigate ${BASE}settings/username --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] ChangeUsernamePage 渲染 — 显示当前用户名
- [ ] remaining changes 计数器可见 (如 "剩余 X 次修改机会")
- [ ] 冷却期提示可见 (如有, 显示 countdown)
- [ ] 新用户名格式校验 (lowercase/digits/underscore/hyphen/dot)
- [ ] 确认密码输入框可见
- [ ] `[console]` zero errors

---

## F.5 — Guest 来宾页面

无需认证。使用 **新 bsk session** + **清除 cookie/localStorage** 来测试。

> **重要:** bsk 所有 session 共享同一 browser profile，cookie 按 origin 共享。
> 新 session 会继承 adult session 的 cookie，导致 route guard 认为用户已认证，
> 从而将访客页面重定向到 dashboard (页面空白/内容错误)。必须在导航到访客页面前
> 清除所有 cookie 和 localStorage。

```bash
# 1) 启动新 session (与 adult session 隔离状态)
GUEST_SID=$(bsk session start --json | jq -r .session_id)
# 2) 导航到 adult origin (先到达目标域名)
bsk navigate ${BASE} --session $GUEST_SID --wait-until domcontentloaded
# 3) 清除 cookie + localStorage (消除 adult session 污染)
bsk evaluate --session $GUEST_SID --expr "document.cookie.split(';').forEach(c => { document.cookie = c.replace(/^ +/, '').replace(/=.*/, '=;expires=' + new Date().toUTCString() + ';path=/'); }); 'cookies-cleared'"
bsk evaluate --session $GUEST_SID --expr "localStorage.clear(); 'localStorage-cleared'"
```

### F.5.1 Welcome 页

```
bsk navigate ${BASE}welcome --session $GUEST_SID --wait-until networkidle
bsk snapshot --session $GUEST_SID
bsk screenshot --session $GUEST_SID --out dogfood-output/f5.1-welcome.png
```

Assertions:
- [ ] 欢迎页渲染 (登录/注册入口)
- [ ] 品牌元素正确
- [ ] `[console]` zero errors

### F.5.2 Register 页

```
bsk navigate ${BASE}register --session $GUEST_SID --wait-until networkidle
bsk snapshot --session $GUEST_SID
```

Assertions:
- [ ] 注册表单渲染 (username, password, display_name 等)
- [ ] 表单验证 (空字段、密码强度)
- [ ] `[console]` zero errors
- [ ] **不实际提交注册** — 仅验证 UI

### F.5.3 Join Family 页

```
bsk navigate ${BASE}join-family --session $GUEST_SID --wait-until networkidle
bsk snapshot --session $GUEST_SID
```

Assertions:
- [ ] 加入家庭表单渲染 (邀请码输入)
- [ ] `[console]` zero errors

### F.5.4 Promo 页面

```
bsk navigate ${BASE}promo/family --session $GUEST_SID --wait-until networkidle
bsk snapshot --session $GUEST_SID
bsk navigate ${BASE}promo/developer --session $GUEST_SID --wait-until networkidle
bsk snapshot --session $GUEST_SID
```

Assertions:
- [ ] 两个 promo 页面均渲染正常
- [ ] `[console]` zero errors

```bash
bsk session stop $GUEST_SID
```

---

## F.6 — 儿童端扩展功能

覆盖 Area 1/5 未涉及的儿童页面。

### F.6.1 儿童周情景游戏 (Scenario)

```
bsk navigate ${CHILD_BASE}scenario --session <child_id> --wait-until networkidle
bsk snapshot --session <child_id>
```

Assertions:
- [ ] 情景游戏页渲染
- [ ] 如有本周情景 → 显示选项
- [ ] 如无 → 友好空态
- [ ] `[console]` zero errors

### F.6.2 儿童素养徽章 (Badges)

```
bsk navigate ${CHILD_BASE}badges --session <child_id> --wait-until networkidle
bsk snapshot --session <child_id>
bsk screenshot --session <child_id> --out dogfood-output/f6.2-child-badges.png
```

Assertions:
- [ ] 徽章页渲染
- [ ] 各维度徽章可见 (earning/waiting/caring 等)
- [ ] 已获得/未获得状态区分
- [ ] `[console]` zero errors

### F.6.3 儿童日历日视图

```
bsk navigate ${CHILD_BASE}calendar/day --session <child_id> --wait-until networkidle
bsk snapshot --session <child_id>
```

Assertions:
- [ ] 日视图渲染: 家务、心愿、里程碑
- [ ] `[console]` zero errors

### F.6.4 儿童宣言签署

```
bsk navigate ${CHILD_BASE}manifesto/sign --session <child_id> --wait-until networkidle
bsk snapshot --session <child_id>
```

Assertions:
- [ ] 儿童端宣言签署页渲染
- [ ] 签署交互可用
- [ ] `[console]` zero errors

### F.6.5 儿童心愿详情

```
# 使用一个真实的心愿 ID
bsk navigate ${CHILD_BASE}wishes/<id> --session <child_id> --wait-until networkidle
bsk snapshot --session <child_id>
```

Assertions:
- [ ] 心愿详情渲染 (名称、emoji、进度)
- [ ] 储蓄预估天数显示 (daysEstimate)
- [ ] `[console]` zero errors

---

## F.7 — AI 设置深度覆盖

覆盖 Area 4 C4.10 中 AI 设置子页面的深度验证。

### F.7.1 MCP 工具管理 (owner-only)

```
bsk navigate ${BASE}settings/ai/mcp --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] MCP 工具管理页渲染
- [ ] 工具列表/配置可见
- [ ] `[console]` zero errors

### F.7.2 Web Search 配置 (owner-only)

```
bsk navigate ${BASE}settings/ai/web-search --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Web search 配置页渲染
- [ ] 开关/配置可见
- [ ] `[console]` zero errors

### F.7.3 ASR 语音识别配置 + CRUD

```
bsk navigate ${BASE}settings/ai/asr --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] ASR 配置页渲染
- [ ] Provider 列表可见
- [ ] `/settings/ai/asr/new` 新建表单 — provider_name, api_key, endpoint 字段可见
- [ ] `/settings/ai/asr/:id/edit` 编辑表单 — 字段预填充为现有值
- [ ] 删除 provider → 确认对话框 → 列表刷新
- [ ] `[console]` zero errors

### F.7.4 AI Skills 管理

```
bsk navigate ${BASE}settings/ai/skills --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Skills 管理页渲染
- [ ] 内置 skills 列表可见
- [ ] `[console]` zero errors

### F.7.5 AI Agents 管理

```
bsk navigate ${BASE}settings/ai/agents --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Agents 管理页渲染
- [ ] Agent 列表可见 (数鸣 + 自定义)
- [ ] 新建 agent 入口可见
- [ ] `[console]` zero errors

---

## F.11 — FamilyPage 成员管理

覆盖 `/family` 路由下的成员管理功能 (promote/demote/deactivate/activate)。

### F.11.1 家庭页面总览

```
bsk navigate ${BASE}family --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] FamilyPage 渲染 — 家庭名可编辑 (owner)
- [ ] 成员列表可见 (每个成员的 display_name + role badge + avatar)
- [ ] 邀请码/邀请链接入口可见 (复制按钮)
- [ ] `[console]` zero errors

### F.11.2 成员权限操作 (owner-only)

```
# 需要 member 角色的成员才能测试 promote/demote
# 以下断言在有 member 成员时执行, 否则 skip 并注明
bsk navigate ${BASE}family --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions (skip if no member-role member exists):
- [ ] 成员操作菜单可见 (⋮ 或 context menu) — 含 promote to admin / demote to member
- [ ] promote member → admin: 点击 → 确认对话框 → 成员 role 更新为 admin
- [ ] demote admin → member: 点击 → 确认对话框 → 成员 role 更新为 member
- [ ] deactivate member: 点击 → 确认对话框 → 成员状态变为 inactive
- [ ] activate member: 点击 → 成员恢复 active 状态
- [ ] owner 自身不可被 demote/deactivate
- [ ] `[console]` zero errors

---

## F.12 — ChildResetPage 儿童密码/PIN 重置

覆盖 `/family/children/:childId/reset` — 安全相关的密码+PIN 双 tab 重置流程。

### F.12.1 儿童重置页

```
# 先获取一个 child member ID via API
CHILD_ID=$(curl -s -H "Authorization: Bearer $TOKEN" ${API_BASE}/family/members \
  | jq -r '[.data[] | select(.role=="child")] | .[0].id')
bsk navigate ${BASE}family/children/${CHILD_ID}/reset --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] ChildResetPage 渲染 — 顶部显示目标儿童名称
- [ ] 双 tab 结构: 密码重置 + PIN 重置
- [ ] 密码 tab: 新密码输入 + 确认密码输入 + 显示/隐藏切换
- [ ] 确认密码不匹配 → 校验错误提示
- [ ] PIN tab: 4×3 emoji 网格 (PIN 输入键盘)
- [ ] 重置成功 → toast 提示
- [ ] `[console]` zero errors

---

## F.8 — Owner vs Member 权限边界

> **前提:** 需要一个 `member` 角色的测试账户。
> 如果 DB 中无 member 账户，以下用例全部 skip 并在报告注明。

### F.8.1 Member 访问 owner-only 页面 → 403

```
# 以 member 身份登录 (需要 member 账户)
# 尝试访问 /baby → 应被拒绝
bsk navigate ${BASE}baby --session <member_sid> --wait-until networkidle
bsk snapshot --session <member_sid>
```

Assertions (如果 member 账户可用):
- [ ] `/baby` 不渲染 BabyPage 内容 (403 / redirect / empty state)
- [ ] `/settings/family/config` 不渲染编辑功能
- [ ] `/settings/family/debt-thresholds` 不渲染编辑功能
- [ ] `/family/chore-approvals` 不渲染审批功能
- [ ] `[console]` zero errors

> **Deferred:** 完整 member 功能遍历 (member 能做什么) 需要单独的 member 测试账户和用例集。

---

## New cases — Baby 家务审批端到端 +  sibling 赠币

Reverse-engineered from backend `test_chores.py` (43 tests, full lifecycle:
create/assign/complete/approve/reject/abandon), `test_chore_assignment.py`
(9 tests), `test_coin_gifting.py` (sibling coin transfer). 之前 F.3.6 仅
验证审批页 *渲染*; F.9 验证 *端到端流转* (child 完成 → parent 审批 → 币
到账)。F.10 验证 sibling 赠币的 *实际交易*。

### F.9.1 家务审批端到端 — child 完成 + parent 批准

> **前置:** 需 demouser family 有 ≥1 child + ≥1 chore 已分配给该 child。

```
# Step 1: child 端登录, 完成一条家务
bsk navigate "$CHILD_BASE" --session "$SID_CHILD" --wait-until networkidle
bsk snapshot --session "$SID_CHILD"
# 找到一条 chore, 点击 "完成"
bsk click @eN --session "$SID_CHILD"   # 完成按钮
bsk wait-ms 2s
bsk snapshot --session "$SID_CHILD"
# 应看到 "待审批" / "pending" 状态

# Step 2: adult 端登录, 进入审批页
bsk navigate ${BASE}baby/chores/approvals --session "$SID" --wait-until networkidle
bsk snapshot --session "$SID"
```

Assertions:
- [ ] 审批页显示 ≥1 条待审批的家务完成记录
- [ ] 每条记录显示: child 名称 + chore 名称 + 完成时间 + 请求的 coin 数
- [ ] "批准" 按钮可点 → 弹出确认框 → 确认
- [ ] 批准后: 该记录从 "待审批" 列表消失
- [ ] child 端刷新 → coin balance 增加对应数量
- [ ] Activity 记录中出现一条 "chore_reward" 类型的入账
- [ ] `[console]` zero errors

### F.9.2 家务审批 — parent 拒绝 + 反馈

```
# 接续 F.9.1, child 再完成一条 chore
# adult 端进入审批页
bsk navigate ${BASE}baby/chores/approvals --session "$SID" --wait-until networkidle
bsk snapshot --session "$SID"
bsk click @eN --session "$SID"   # "拒绝" 按钮
```

Assertions:
- [ ] "拒绝" 按钮可点 → 弹出确认框 (可含拒绝理由输入框)
- [ ] 拒绝后: 该记录从 "待审批" 列表消失
- [ ] child 端刷新 → coin balance 不变
- [ ] child 端该 chore 状态变为 "rejected" 或 "abandoned"
- [ ] Activity 记录中 **无** chore_reward 入账
- [ ] `[console]` zero errors

### F.9.3 家务完成庆祝动画 — FlyToTarget + coin bump

> **与 C1.10 的差异:** C1.10 仅验证动画 *触发*; F.9.3 验证 审批通过
> 后的 *完整庆祝链路* (动画 + coin bump + 音效)。

```
# 接续 F.9.1 的批准操作, 在 child 端观察
bsk navigate "$CHILD_BASE" --session "$SID_CHILD" --wait-until networkidle
bsk screenshot --session "$SID_CHILD" --out dogfood-output/f9.3-celebration.png
```

Assertions:
- [ ] 批准后 child 端首页/ledger 出现 coin bump 动画 (数字跳动 + 增加)
- [ ] FlyToTarget 粒子效果 (coin 从 chore 卡片飞向 balance 显示)
- [ ] 触感反馈 (mobile: navigator.vibrate; desktop: 跳过)
- [ ] reduced-motion 模式下: 动画降级为静态 (无 FlyToTarget, 仅数字变化)
- [ ] `[console]` zero errors

---

### F.10 — Sibling 赠币端到端

Reverse-engineered from backend `test_coin_gifting.py`. C1.2 渲染了赠币按钮;
F.10 验证 *实际交易*: sender 扣币 + receiver 加币 + Activity 记录。

> **前置:** demouser family 有 ≥2 child 账户, 且 sender 有 ≥1 coin。

```
# 以 sender child 登录
bsk navigate "$CHILD_BASE"ledger --session "$SID_CHILD" --wait-until networkidle
bsk snapshot --session "$SID_CHILD"
# 找到 "赠送" 按钮 / sibling 头像
bsk click @eN --session "$SID_CHILD"
```

Assertions:
- [ ] 弹出赠币对话框, 显示可选的 sibling 列表 (不含自己)
- [ ] 选择 receiver + 输入金额 → 提交
- [ ] 金额 > sender balance → 校验错误 ("余额不足")
- [ ] 金额 ≤ 0 → 校验错误
- [ ] 合法金额提交 → sender ledger 出现一条 "gift_sent" 扣币记录
- [ ] receiver ledger 出现一条 "gift_received" 加币记录 (切换 child 登录验证)
- [ ] sender coin balance 减少, receiver coin balance 增加
- [ ] `[console]` zero errors

---

## Quick Reference

| Case | 功能模块 | 路由 | 角色要求 |
|------|----------|------|----------|
| F.1.1–F.1.5 | Manifesto 宣言 | `/manifesto/*` | owner |
| F.2.1–F.2.4 | Blind Box 盲盒 | `/blind-box/*` | owner |
| F.3.1–F.3.6 | Baby 儿童管理 | `/baby/*` | owner |
| F.4.1–F.4.10 | Settings 深度 | `/settings/*` | owner |
| F.5.1–F.5.4 | Guest 来宾 | `/welcome`, `/register`, ... | none |
| F.6.1–F.6.5 | Child 扩展 | `/scenario`, `/badges`, ... | child |
| F.7.1–F.7.5 | AI 设置深度 | `/settings/ai/*` | owner |
| F.8.1 | 权限边界 | owner-only 页面 | member (deferred) |
| F.9.1–F.9.3 | 家务审批端到端 | `/baby/chores/approvals` | owner + child |
| F.10 | Sibling 赠币端到端 | `/ledger` (child) | child |
