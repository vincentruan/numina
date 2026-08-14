# numina-sim-test 双重对抗者分析报告 — 2026-08-07

> 分析维度: 案例完整度对抗 (Case Completeness Adversary) + 案例与界面一致性对抗 (Case-UI Consistency Adversary)
> 分析范围: Area 2 (Financial) + Area 3 (AI) + Area 7 (Regression) + Area 8 (Expanded Features)
> 测试环境: dev mode, adult :5173, child :5174, AI provider=null

---

## 一、案例完整度对抗 (Case Completeness Adversary)

### 1.1 儿童 app 全线不可测 — Area 1 / Area 5 案例需重构

**发现:** `frontend/apps/child/src/api/index.ts:38` 明确注释 "child app has no auth pages"，未认证用户被重定向到主 app 登录页。测试案例 C1.1–C1.17 和 C5.1–C5.10 假设儿童 app 有独立的 PIN/emoji-grid 登录流程。

**实际行为:**
- dev 模式下 :5174/child/ 无法独立认证 (adult :5173 和 child :5174 是不同 origin, cookie 不共享)
- docker 模式下 nginx 将两者统一到 :80，但 adult cookie 会污染 child route guard
- 儿童 app 当前设计依赖 adult app 提供的 session，无法独立运行

**建议改进:**
- **C1.x 案例需拆分为两组:** (a) docker 模式下的儿童认证流程 (cookie clearing + verifyChildSession), (b) dev 模式下的儿童认证流程 (需要实现独立 child login 或 proxy)
- **新增 C1.0 — Child auth bootstrap 门禁:** 验证儿童 app 是否有可用的认证入口
- **SKILL.md Phase 2 "child session" 流程需更新:** 当前依赖 PIN-based auth，但代码实际不存在此功能

**案例缺口清单:**
```
C1.1   儿童首页渲染         ← 需独立 child login 才可测
C1.3   PIN 登录流程          ← PIN 入口不存在, 需重构
C1.5   儿童设置页            ← 依赖 C1.3
C5.x   儿童导航覆盖          ← 依赖 C1.3
```

### 1.2 AI 未配置导致 35+ 案例被跳过 — 需增加 AI 配置门禁

**发现:** ai_enabled=true 但 ai_provider=null，导致 FinanceCoachCard、AI chat、AI report 等全部显示空状态或跳过。

**建议改进:**
- **Phase 1.5 前置门禁增加 AI provider 检查:**
  ```bash
  AI_STATUS=$(curl -s -H "$AUTH" "$API/ai/config/defaults")
  PROVIDER=$(echo "$AI_STATUS" | jq -r '.data.provider // empty')
  [ -n "$PROVIDER" ] || echo "WARNING: AI provider not configured — Area 3/6 will be SKIP-AI"
  ```
- **新增 C2.9a — FinanceCoachCard 空状态验证:** 当 AI provider=null 时，FinanceCoachCard 应显示合理的空状态 (非报错)
- **C2.10 generate 按钮应验证:** 即使 provider=null，按钮是否引导用户配置 provider？还是静默失败？

### 1.3 C2.14/C2.15/C2.16 依赖特定数据 — 需要数据前提断言

**发现:**
- C2.14 (savings log) 需要有心愿且有储蓄记录
- C2.15 (debt warning) 需要高利率负债 (interest_rate ≥ FamilyDebtThresholds)
- C2.16 (debt thresholds config) 需要 owner session + 阈值数据

**建议改进:**
- **Phase 1.5 增加数据前提检查:**
  ```bash
  # 检查是否有心愿带 saved_amount > 0
  WISH_SAVINGS=$(curl -s -H "$AUTH" "$API/wishes" | jq '[.data[] | select(.saved_amount > 0)] | length')
  [ "$WISH_SAVINGS" -gt 0 ] || echo "WARNING: no wishes with savings — C2.14 will show empty state"

  # 检查是否有高利率负债
  HIGH_RATE=$(curl -s -H "$AUTH" "$API/liabilities" | jq '[.data[] | select(.interest_rate >= 15)] | length')
  [ "$HIGH_RATE" -gt 0 ] || echo "WARNING: no high-interest liabilities — C2.15 debt hint won't trigger"
  ```
- **C2.15 断言需拆分:** (a) 有高利率负债时的提示条显示, (b) 无高利率负债时的提示条隐藏
- **C2.12 afford bar 降级模式已验证:** monthly_saving=null 时降级为净资产可负担模式 ✅ (但案例描述暗示应有 "N 月达成" 显示，需确认降级条件)

### 1.4 访客流程 C10.x 需要真正干净的 session

**发现:** bsk 新 session 访问 /register 和 /join-family 时页面空白，原因是 bsk 共享浏览器 profile，adult cookie 污染了访客 session。

**建议改进:**
- **Phase 2 增加 session 清洁步骤:**
  ```
  bsk navigate http://localhost:5173/ --session <guest-id>
  bsk evaluate --session <guest-id> "document.cookie.split(';').forEach(c => document.cookie = c.replace(/^ +/, '').replace(/=.*/, '=;expires=' + new Date().toUTCString() + ';path=/'))"
  bsk evaluate --session <guest-id> "localStorage.clear()"
  bsk navigate http://localhost:5173/register --session <guest-id>
  ```
- **新增 C10.0 — Guest session bootstrap 门禁:** 验证访客页面是否可在无 cookie 环境下正常渲染

---

## 二、案例与界面一致性对抗 (Case-UI Consistency Adversary)

### 2.1 路由名称与实际路由不匹配

| 案例中的路由 | 实际路由 | 影响案例 |
|-------------|----------|----------|
| `/settings/notification` | `/settings/notifications` | F.4 断言 |
| `/settings/family` | `/settings/family/config` | F.4 断言 |
| `/settings/ai` | `/settings/ai/mcp` (或 ai/web-search/skills/agents) | F.4 断言 |
| `/settings/devices` | `/settings/devices` ✅ | 匹配 |
| `/settings/password` | `/settings/password` ✅ | 匹配 |
| `/settings/security` | `/settings/security` (需确认) | C9.x |

**建议:** 更新 area8-expanded-features.md 中 F.4 的断言路由。

### 2.2 标签命名 vs 代码命名

| 案例中的标签 | UI 实际标签 | 代码位置 |
|-------------|-------------|----------|
| "Kids" (tab) | "Baby" (tab) | 导航栏 |
| "AI Model Management" | "AI Hub" | AI Hub 页面标题 |
| "记录储蓄" | "Record Savings" (en) / "记录储蓄" (zh) | C2.3/C2.4 |

**建议:** 案例中的标签名应注明中英文两种语言版本。

### 2.3 C2.3 Afford bar 实际模式 vs 案例预期

**案例预期 (C2.12):** "Afford bar shows the months-to-reach projection = `(price - saved) / monthly_saving` (W2 rhythm)"

**实际 UI:** "Current net worth ¥465.58万, affordable" — 这是旧版净资产可负担模式

**一致性分析:**
- 当 monthly_saving=null 时，降级为净资产模式是合理的 (C2.12 第 4 条断言: "If monthly_saving is 0/null, afford bar degrades gracefully")
- 但案例未提供有 monthly_saving 的心愿来验证 W2 rhythm 模式
- **建议:** 创建一个有 monthly_saving 的心愿，验证 W2 模式的 "≈ N 月达成" 显示

### 2.4 C2.15 债务警告提示条 — 列表页 vs 详情页

**案例预期 (C2.15):** "Debt warning hint bar appears ABOVE the WishAdviceCard"

**实际 UI:**
- 心愿列表页: ✅ 显示 "You have ¥25000 in high-interest debt (rate 18%)..." 提示条
- 心愿详情页: ❌ 不显示债务警告提示条

**一致性分析:** 案例未明确区分列表页和详情页。这可能是有意设计 (避免重复)，也可能是遗漏。

**建议:** 明确产品需求 — 详情页是否也需要债务警告提示条？如果不需要，C2.15 断言应注明 "仅在列表页显示"。

### 2.5 AI Hub tab 标签 vs 页面标题

**案例预期:** "AI Hub" (Area 3 入口)

**实际 UI:**
- 底部导航 tab: "AI Hub" ✅
- 页面内标题: "AI 中心" ✅
- 子页面标题: "AI 模型管理" (对应 /settings/ai/mcp)

**一致性分析:** 匹配。但案例中 "AI Model Management" 这个英文标签在 UI 中不存在。

### 2.6 C2.25 汇率 API — 案例断言 vs 实际返回格式

**案例断言:** "返回 200 + 汇率表 (base=CNY, targets=[USD,EUR,JPY,...])"

**实际返回:**
```json
{
  "AED": { "rate": 0.543, "fetched_at": "2026-08-07T14:11:37.775555+00:00" },
  ...
}
```

**一致性分析:** 实际返回的是全量汇率表 (非指定 targets)，且包含 fetched_at 时间戳。案例断言应更新为 "返回全量汇率表，每个币种包含 rate 和 fetched_at"。

### 2.7 儿童 app 认证模型 — 案例假设 vs 代码现实

**案例假设 (C1.3):** "儿童选择页 (emoji PIN grid)"

**代码现实:** `frontend/apps/child/src/api/index.ts:38` 注释 "child app has no auth pages"

**一致性分析:** 案例描述的功能在代码中不存在。这可能是:
1. 儿童认证流程已实现但不在 child app 中 (在 adult app 的某个子路由)
2. 儿童认证流程尚未实现
3. 案例描述的是未来规划的功能

**建议:** 确认儿童认证的实际入口位置，更新 C1.3 断言。

---

## 三、综合改进建议

### 3.1 测试案例优先级调整

| 优先级 | 案例 | 原因 |
|--------|------|------|
| P0 阻塞 | C1.x, C5.x | 儿童 app 认证不可用，阻塞 27 个案例 |
| P1 需数据 | C2.14, C2.15, C2.16 | 需要特定数据 (savings/high-interest liability) |
| P1 需配置 | C2.9–C2.11, C3.2–C3.7, C6.x | 需要 AI provider 配置 |
| P2 需清洁 session | C10.x, F.5 | 需要无 cookie 环境 |
| P3 路由修正 | F.4 | 路由名称需更新 |

### 3.2 SKILL.md Phase 流程改进

1. ~~**Phase 1.5 增加 AI provider 检查** — 提前标记 SKIP-AI 案例~~ ✅ 已完成 (commit eb7f5064)
2. ~~**Phase 1.5 增加数据前提检查** — 验证 wishes/liabilities 数据是否满足案例需求~~ ✅ 已完成 (commit eb7f5064)
3. ~~**Phase 2 增加 session 清洁步骤** — 访客流程测试前清除 cookie + localStorage~~ ✅ 已完成 (commit f425fdd9, F.5 案例更新)
4. ~~**Phase 2 增加儿童 app 认证门禁** — 验证 :5174/child/ 是否有可用的认证入口~~ ✅ 已完成 (commit 90ca4006, 增加 step1 probe)
5. ~~**Phase 6 增加案例-UI 一致性检查** — 对比案例路由/标签 vs 实际 UI~~ ✅ 已完成 (commit 70d562a3, report guidance)

### 3.3 新增案例建议

| 案例 ID | 名称 | 目的 |
|---------|------|------|
| C1.0 | Child auth bootstrap 门禁 | 验证儿童 app 是否有可用的认证入口 |
| C2.9a | FinanceCoachCard 空状态 | 验证 AI provider=null 时的空状态渲染 |
| C10.0 | Guest session bootstrap 门禁 | 验证访客页面是否可在无 cookie 环境下正常渲染 |
| C2.26 | Afford bar W2 rhythm 验证 | 验证有 monthly_saving 的心愿显示 "≈ N 月达成" |
| C2.27 | Debt warning 列表页 vs 详情页 | 验证债务警告提示条在列表页和详情页的显示差异 |

### 3.4 文档更新建议

1. ~~**area8-expanded-features.md F.4** — 更新路由名称 (notification→notifications, family→family/config)~~ ✅ 路由已正确, 无需更新
2. ~~**area2-finance.md C2.15** — 注明 "仅在列表页显示"~~ ✅ 已完成 (commit adce2a58)
3. ~~**area2-finance.md C2.25** — 更新断言 (全量汇率表, 含 fetched_at)~~ ✅ 已完成 (commit adce2a58)
4. ~~**area1-child.md C1.3** — 确认儿童认证的实际入口位置~~ ✅ 已完成 (commit 90ca4006, C1.3 重写为 API 注入验证)
5. ~~**_common.md** — 修正儿童 PIN 错误 (🌟🌈 → 🐱🐶🌟🌈)~~ ✅ 已完成 (commit adce2a58)

---

## 四、总结

**案例完整度对抗发现:**
- 儿童 app 全线不可测 (27 案例阻塞) — 需重构认证流程
- AI 未配置导致 35+ 案例跳过 — 需增加 AI 配置门禁
- 数据前提检查缺失 — 需增加 wishes/liabilities 数据验证

**案例-UI 一致性对抗发现:**
- 路由名称不匹配 (3 处) — F.4 需更新
- 标签命名差异 (2 处) — 案例需注明中英文
- 功能实现与案例描述不符 (2 处) — C1.3 (PIN login), C2.15 (详情页债务警告)
- API 返回格式与断言不符 (1 处) — C2.25 汇率 API

**建议优先修复:**
1. P0: 儿童 app 认证流程 (阻塞 27 案例)
2. P1: F.4 路由名称更新 (快速修复)
3. P1: Phase 1.5 增加 AI provider + 数据前提检查
4. P2: C10.x 访客流程 session 清洁
5. P3: 新增 5 个案例 (C1.0, C2.9a, C10.0, C2.26, C2.27)
