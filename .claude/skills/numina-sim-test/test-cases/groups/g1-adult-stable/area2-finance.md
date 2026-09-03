# Area 2 — Main app financial management (财务管理能力优化)

Shared conventions in [`_common.md`](../../_common.md).

## Success Criteria (成功标准)

### Pass Threshold
- **Overall pass rate**: ≥ 95% (24/25 cases must pass)
- **Critical cases** (MUST pass): C2.1, C2.2, C2.5, C2.8
- **Optional cases** (can SKIP with reason): C2.14-C2.17 (require specific data)

### Performance Benchmarks
| Case | Metric | Target | Max |
|------|--------|--------|-----|
| C2.1 Dashboard | Page load | < 2s | < 5s |
| C2.2 Wish list | Page load | < 2s | < 5s |
| C2.5 Liability list | Page load | < 2s | < 5s |
| C2.8 Asset list | Page load | < 2s | < 5s |
| All cases | Console errors | 0 | 0 |

### Data Quality Checks
- **No NaN/undefined** in any money field
- **No scientific notation** (e.g., 5.9e7) in amounts
- **Arithmetic verified**: net worth = assets − liabilities (not just presence)
- **Currency formatting**: single symbol (¥ or current currency), no double symbols (¥¥)

---

Auth: establish the adult session as `demouser` / `DemoPass123` first. The
default `bsk fill` form-login (SKILL.md Phase 2) can trigger a password-manager
extension that hijacks the Agent Window tab. **Prefer the cookie+localStorage
injection fallback** (SKILL.md "Phase 2 fallback") — it never focuses the
password field, so the extension never activates. All routes under `${BASE}`
(adult SPA).

Covers Plan A (`finance_coach` capability) + Plan B (P0 business touchpoints
W1/W2/W4/W5, L1/L2, D2, A1a/A1b). All features verified landed in
`frontend/apps/main/src/`.

## Existing cases — core financial flows

### C2.1 Dashboard (DashboardPage) — totals, net worth, trend

**Performance target:** Page load < 2s | **Critical case:** MUST pass

```
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Asset total + liability total + net worth render
- [ ] Net worth = assets − liabilities (verify the arithmetic, not just presence)
- [ ] Trend chart (ECharts) renders with data points
- [ ] Money values display as formatted strings (post Float→Numeric migration, backend returns str; frontend may Number()-coerce for display — check no `NaN`/`undefined`)
- [ ] Allocation breakdown `{items, total}` renders (not a flat list)
- [ ] `[console]` zero errors

**Automated assertion (recommended):**
```bash
# Verify arithmetic and formatting
bsk evaluate --session <id> --expr "(async () => {
  const text = document.body.innerText;
  const hasNaN = text.includes('NaN') || text.includes('undefined');
  const hasScientific = /[0-9]+\.[0-9]+e[+-]?[0-9]+/i.test(text);
  const hasDoubleSymbol = /¥¥|\$\$|€€/.test(text);
  return JSON.stringify({hasNaN, hasScientific, hasDoubleSymbol});
})()"
# Expected: {"hasNaN":false,"hasScientific":false,"hasDoubleSymbol":false}
```

### C2.2 Wish list (WishListPage) — savings progress + advice + debt hint

```
bsk navigate ${BASE}finance?tab=wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Wish list renders with priority + progress
- [ ] WishSavingsProgress component shows saved/target bar for wishes with savings
- [ ] WishAdviceCard (W4) renders AI advice for wishes (if AI enabled + advice generated)
- [ ] Debt warning hint bar appears ABOVE the W4 card when a wish's category exceeds family debt thresholds (W5 linkage)
- [ ] Tap a wish → navigates to WishDetail
- [ ] `[console]` zero errors

### C2.3 Wish detail (WishDetailPage) — savings log + record + afford bar

```
# Navigate to a wish with savings (use a real wish id from the API)
bsk navigate ${BASE}wishes/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] WishSavingsProgress shows progress bar + percentage
- [ ] "记录储蓄" button → opens WishSavingsRecordDialog (van-dialog/popup)
- [ ] "储蓄日志" button → opens WishSavingsLogDialog (list of past savings entries)
- [ ] Afford bar (useAffordBar composable, 4 states) renders: can-afford / cannot / loading / error
- [ ] "忽略" button (W5 debt warning) calls T3 backend route, hides the hint
- [ ] A1b buttons (wish_detail → /ai/chat) present when AI enabled
- [ ] `[console]` zero errors

### C2.4 Wish savings record dialog — amount input + submit

```
bsk navigate ${BASE}wishes/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>   # get dialog refs after opening
bsk fill @eN --value 100 --session <id>
bsk click @eM --session <id>   # confirm button
```

Assertions:
- [ ] Amount field accepts numeric input
- [ ] Submit POSTs to savings endpoint, returns 201
- [ ] Progress bar updates after successful record
- [ ] Invalid amount (negative / non-numeric) → validation error
- [ ] `[console]` zero errors

### C2.5 Liability list (LiabilityListPage) — strategy card + interest forecast

```
bsk navigate ${BASE}finance?tab=liabilities --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Liability list renders with category, remaining amount, monthly payment
- [ ] LiabilityStrategyCard renders (client-side monthly-interest sum + 估算)
- [ ] InterestForecast component shows projection (hides when interest_rate=0, per spec §6.1)
- [ ] PaymentCountdown shows days until next payment
- [ ] `?focus=liability_strategy` query param scrolls to / highlights strategy card
- [ ] Tap liability → navigates to LiabilityDetail
- [ ] `[console]` zero errors

### C2.6 Liability detail (LiabilityDetailPage) — simulate extra payment

```
bsk navigate ${BASE}liabilities/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
# open SimulateExtraDialog
```

Assertions:
- [ ] SimulateExtraDialog opens with extra_monthly input
- [ ] calc_amortization (equal / min-payment modes) runs client-side
- [ ] min-payment non-cover boundary: rate=60% edge case handled (no crash)
- [ ] Result shows revised payoff timeline + interest saved
- [ ] A1b button (liability_detail → /ai/chat) present when AI enabled
- [ ] `[console]` zero errors

### C2.7 Liability create/edit form (LiabilityFormPage)

```
bsk navigate ${BASE}liabilities/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Form fields: name, category, original_amount, remaining_amount, monthly_payment, interest_rate
- [ ] Vant van-field uses `:model-value` binding (not `:value`)
- [ ] Submit POSTs, returns 201, navigates to detail
- [ ] Required field validation (Chinese error messages)
- [ ] `[console]` zero errors

### C2.8 Asset list + detail + sell flow

```
bsk navigate ${BASE}finance?tab=assets --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Asset list renders with category filter + status badges (in_use/idle/retired/sold)
- [ ] Money fields (purchase_price, current_value) display correctly post-Float→Numeric migration
- [ ] Tap asset → AssetDetailPage
- [ ] From detail → 出售 button → AssetSellPage
- [ ] Sell form: sell_price + sell_fee → net_recovery shown → submit returns 201
- [ ] `[console]` zero errors

---

## New cases — Plan A: FinanceCoachCard (D2)

Covers Plan A `finance_coach` capability + Plan B D2 dashboard card.
Component: `components/dashboard/FinanceCoachCard.vue`. Backend:
`POST /ai/finance-coach/generate?force=false` (8h capability-cache, streams
`finance_coach.result` frame with `suggestions[]`). AI must be enabled.

### C2.9 FinanceCoachCard — cached state render

```
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c2.9-finance-coach-cached.png
```

Prerequisite: a finance_coach cache already exists for demouser (run generate
once before, or seed). If no cache, skip to C2.10 first.

Assertions:
- [ ] `FinanceCoachCard` renders on the dashboard with the cached suggestions
- [ ] Each suggestion shows: severity, title, action, target_type, cta_label
- [ ] `generated_at` timestamp displayed (human-readable)
- [ ] A "刷新" / regenerate affordance is present (calls generate with `force=true`)
- [ ] `[console]` zero errors (no SSE/EventSource errors after cached load)

### C2.10 FinanceCoachCard — generate (stream) + cache populate

```
# If no cache: click generate on the card
bsk snapshot --session <id>
bsk click @eN --session <id>     # "生成" / generate button
bsk wait-ms 8s                   # finance_coach streams; poll if needed
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c2.10-finance-coach-generate.png
```

Assertions:
- [ ] Card shows loading/spinner state during stream
- [ ] Stream completes; suggestions render (non-empty `suggestions[]`)
- [ ] After completion, the result is cached (revisiting dashboard shows cached state without re-stream — verify via `[console]` no second generate POST)
- [ ] `[console]` zero errors (blank-response / stream-stuck fixes from chat bugs do not regress here)

### C2.11 FinanceCoachCard — entity-change invalidation

```
# After C2.10 cached: create/edit an asset or liability, then return to dashboard
bsk navigate ${BASE}assets/new --session <id> --wait-until networkidle
# ... create an asset (C2.7-style flow) ...
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] After an asset/liability write, the finance_coach cache is invalidated (Plan A T9 entity-change invalidation)
- [ ] Dashboard card no longer shows stale `generated_at` — it re-generates or shows a regenerate prompt
- [ ] `[console]` zero errors

---

## New cases — Plan B: W1/W2 savings + afford bar rhythm

Covers W1 (wish savings fields: `saved_amount`/`target_date`/`monthly_saving` +
`WishSavingsLog`) and W2 (afford bar refactored from "net worth can afford" to
"months-to-reach by monthly-savings rhythm" = `(price-saved)/monthly_saving`).

### C2.12 Wish savings fields — monthly_saving + target_date

```
bsk navigate ${BASE}finance?tab=wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Open a wish that has monthly_saving + target_date set
bsk click @eN --session <id>
bsk snapshot --session <id>
```

Assertions:
- [ ] Wish detail shows `monthly_saving` (月存) and `target_date` (目标日期) fields (W1)
- [ ] WishSavingsProgress shows `已存 ¥X / ¥Y (Z%)` with the savings ratio
- [ ] Afford bar shows the months-to-reach projection = `(price - saved) / monthly_saving` (W2 rhythm, NOT net-worth affordability)
- [ ] If `monthly_saving` is 0/null, afford bar degrades gracefully (shows "未设定月存" or cannot-compute, not NaN/crash)
- [ ] `[console]` zero errors

### C2.13 Afford bar — 4 states + edge cases

```
# Navigate to wishes with different savings states
bsk navigate ${BASE}finance?tab=wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions (verify across multiple wishes if available):
- [ ] can-afford state: saved ≥ price → green/positive afford bar
- [ ] cannot (on-track) state: saved < price but monthly_saving set → shows "≈ N 月达成" projection
- [ ] loading state: brief skeleton/spinner while computing
- [ ] error state: if compute fails, shows error affordance (not a blank bar)
- [ ] Edge: wish with `price=0` or `saved>price` handled without NaN
- [ ] `[console]` zero errors

### C2.14 Wish savings log — entry list + add entry updates progress

```
bsk navigate ${BASE}wishes/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>     # "储蓄日志" button → WishSavingsLogDialog
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c2.14-savings-log.png
```

Assertions:
- [ ] WishSavingsLogDialog lists past savings entries (amount + timestamp)
- [ ] Each entry reflects a `WishSavingsLog` row (W1 table)
- [ ] Adding a new entry (via WishSavingsRecordDialog, C2.4) appends to this log
- [ ] Progress bar + afford bar recompute after the new entry
- [ ] `[console]` zero errors

---

## New cases — Plan B: W5 debt-warning + L1/L2 simulate endpoint

Covers W5 (high-interest liability ↔ wish linkage hint) and L1/L2
(`calc_amortization` util + `POST /liabilities/simulate` endpoint). Model:
`FamilyDebtThresholds` (GET/PUT `/family/debt-thresholds`, owner-only).

### C2.15 Debt-warning hint bar — threshold linkage

**注意:** 债务警告提示条仅在心愿列表页显示，不在详情页显示（避免重复提示）。

```
bsk navigate ${BASE}finance?tab=wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Prerequisite: demouser has a high-interest liability (interest_rate ≥ category
threshold in `FamilyDebtThresholds`).

Assertions:
- [ ] Debt warning hint bar appears ABOVE the WishAdviceCard (W5) **in the wish list page** for wishes in categories exceeding the family debt threshold
- [ ] Hint text references the high-interest liability (e.g. "建议优先还债 利率 18%")
- [ ] "忽略" button hides the hint (persists via T3 backend route)
- [ ] After "忽略", hint does NOT reappear on reload for that wish
- [ ] Wishes in categories BELOW the threshold show no hint bar
- [ ] **Wish detail page does NOT show debt warning hint bar** (avoid duplicate hints)
- [ ] `[console]` zero errors

### C2.16 Debt thresholds config — owner GET/PUT

```
# Owner session. Hit the thresholds endpoint (or via settings UI if present)
curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/family/debt-thresholds" | jq .
```

Assertions:
- [ ] GET `/family/debt-thresholds` returns the family's per-category thresholds (owner-only — child/non-owner gets 403)
- [ ] PUT updates a threshold; subsequent GET reflects the change
- [ ] After raising a threshold above a liability's rate, the C2.15 hint bar disappears for that category
- [ ] `[console]` zero errors on the settings/threshold UI if present

### C2.17 Liability /simulate endpoint — amortization modes

```
# Direct API test (L1/L2 single-source amortization util + route)
# NOTE: This is a pure-compute endpoint — it takes remaining/annual_rate directly,
# NOT a liability_id. The backend has no DB access for this endpoint.
curl -s -X POST "${API_BASE}/liabilities/simulate" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"remaining":"10000","annual_rate":"12","monthly_payment":"500","extra_monthly":"500"}' | jq .
curl -s -X POST "${API_BASE}/liabilities/simulate" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"remaining":"10000","annual_rate":"12","monthly_payment":null,"extra_monthly":"0"}' | jq .
```

Assertions:
- [ ] `monthly_payment` given (equal-payment mode) returns a revised payoff timeline (months) + total interest + interest saved
- [ ] `monthly_payment: null` (minimum-payment mode, e.g. credit card) with `extra_monthly=0` returns the baseline min-payment schedule
- [ ] min-payment non-cover boundary: when min-payment < monthly interest (rate=60% edge), returns a structured "cannot-pay-off" result (no 500/crash, no infinite loop — 1200-month cap)
- [ ] Frontend SimulateExtraDialog (C2.6) consumes the same util client-side; results match the API
- [ ] `[console]` zero errors

---

## New cases — Plan B: A1b passive buttons (wish/liability → /ai/chat)

Covers A1b: passive "ask AI" buttons on wish_detail and liability_detail that
deep-link into `/ai/chat` with context. Already referenced in C2.3/C2.6; this
case verifies the navigation + context handoff.

### C2.18 A1b — wish_detail → /ai/chat context handoff

```
# On a wish detail page (AI enabled)
bsk navigate ${BASE}wishes/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>     # the A1b "问 AI" / consult button
bsk wait-ms 1s
bsk snapshot --session <id>
```

Assertions:
- [ ] Clicking the A1b button navigates to `/ai/chat` (with a context query param or prefilled message referencing the wish)
- [ ] The chat page loads with the wish context (thread or prefilled prompt mentions the wish)
- [ ] No blank/empty state (chat input is ready, not stuck loading)
- [ ] `[console]` zero errors

### C2.19 A1b — liability_detail → /ai/chat context handoff

```
bsk navigate ${BASE}liabilities/<id> --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>     # the A1b button on liability detail
bsk wait-ms 1s
bsk snapshot --session <id>
```

Assertions:
- [ ] Navigates to `/ai/chat` with liability context
- [ ] Chat loads ready (not stuck); liability context visible or prefilled
- [ ] `[console]` zero errors

---

## New cases — Plan B: money Float→Numeric migration display

Covers the money-type migration (Asset/Liability/Wish/PaymentRecord Numeric
columns, str on wire). Verifies display correctness post-migration across
financial pages.

### C2.20 Money display — no precision loss across financial pages

```
bsk navigate ${BASE} --session <id> --wait-until networkidle        # dashboard
bsk navigate ${BASE}finance?tab=assets --session <id> --wait-until networkidle   # asset list
bsk navigate ${BASE}finance?tab=liabilities --session <id> --wait-until networkidle  # liability list
bsk navigate ${BASE}finance?tab=wishes --session <id> --wait-until networkidle   # wish list
bsk snapshot --session <id>
```

Assertions (per page):
- [ ] All money values render as formatted strings — no `NaN`, `undefined`, scientific notation, or float artifacts (e.g. `30413901.0` not `30413901.00000001`)
- [ ] Large amounts (e.g. demouser's 59M total assets) display without JS precision loss (bigint-as-str wire format)
- [ ] Computed values (net worth, totals, allocation percentages) are arithmetically correct
- [ ] `[console]` zero errors

---

## New cases — Dashboard extras (FocusTop3Card + dashboard_narrative)

Reverse-engineered from frontend `FocusTop3Card.spec.ts` (top-3 assets /
liabilities / wishes by urgency) and backend `test_dashboard_narrative.py`
(AI-generated narrative summary). Covers HIGH-IMPACT gaps in the previous
inventory.

### C2.21 Dashboard — FocusTop3Card 三大紧急项

```
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 定位 "重点事项" / FocusTop3Card 区块
```

Assertions:
- [ ] 卡片显示三个标签页: 资产 (by current_value desc) / 负债 (by interest_rate desc) / 心愿 (by nearest target_date)
- [ ] 每个标签页显示 ≤3 条, 带 "查看全部" 链接 → `/finance?tab=X`
- [ ] 心愿标签页 *排除* 无 target_date 的心愿 (spec: "nearest target_date, excludes wishes with no target_date")
- [ ] 少于 3 条时不补位/不截断
- [ ] 某域为 0 条时显示 empty state
- [ ] 加载期间显示 skeleton (AssetListPanel skeleton 模式)
- [ ] `[console]` zero errors

### C2.22 Dashboard — AI 叙事卡片 (dashboard_narrative)

```
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 定位 AI 叙事区块 (DashboardNarrativeCard 或类似)
```

Assertions:
- [ ] 卡片存在 + 渲染 (若 AI 启用)
- [ ] 显示 AI 生成的摘要文字 (非空, 非占位符)
- [ ] 刷新按钮可点 → 重新生成 (loading 状态 → 新内容)
- [ ] AI 禁用时卡片隐藏 (不显示空框或 "请启用 AI")
- [ ] `[console]` zero errors

> **AI 必须启用:** 若 aiEnabled=false, 跳过并标注 SKIP-AI。

---

## New cases — What-if 模拟器 (交互式)

Reverse-engineered from backend `test_whatif.py` + `test_projection.py` +
`test_purchasing_power.py`. C3.6 只验证 AI 时光机 *页面渲染*; C2.23 验证
*实际交互* (参数调整 → 预测曲线变化)。

### C2.23 What-if 模拟器 — 参数调整 + 预测曲线

```
bsk navigate ${BASE}finance?tab=assets --session <id> --wait-until networkidle
# 找到 "What-if 模拟" 按钮 / 入口
bsk snapshot --session <id>
```

Assertions:
- [ ] 模拟器打开 (dialog 或子页面)
- [ ] 显示至少一个参数滑块 (如 "年增长率" / "投资期限")
- [ ] 滑块拖动 → 预测曲线 (ECharts) 实时更新 (无需点"计算")
- [ ] 参数极端值 (0% / 100%) 不崩溃
- [ ] 重置按钮 → 参数回到默认, 曲线回到初始状态
- [ ] `[console]` zero errors

---

## New cases — Asset sell flow 完整路径

C2.8 仅触及 sell 入口; C2.24 验证完整的出售 → 收益计算 → 状态流转。
Reverse-engineered from backend `test_assets.py` sell-flow tests + frontend
`AssetSellPage.spec.ts`。

### C2.24 Asset sell — 完整出售流程 + 状态变更

```
# 选择一条状态为 in_use 或 idle 的资产 (不能是 sold)
bsk navigate ${BASE}assets/<id>/sell --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 表单显示: 出售价 (sell_price) + 手续费 (sell_fee)
- [ ] net_recovery (净回收) 实时计算 = sell_price − sell_fee
- [ ] net_recovery 为负数 → 警告提示 ("出售将产生亏损")
- [ ] 提交 POST → 201, 跳转到资产详情页
- [ ] 详情页状态徽章变为 "sold"
- [ ] 资产从活跃列表消失 (或显示 sold 灰色状态)
- [ ] Dashboard 总资产减少 (反映 sold 资产的 removal)
- [ ] `[console]` zero errors

---

## New cases — 汇率 API 直接验证

C4.0 验证 UI 显示 bug (per-record 不重算); C2.25 验证汇率 API 端点本身。
Reverse-engineered from backend `test_exchange_rate.py`。

### C2.25 汇率 API — 实时汇率查询

```
# 通过 curl 直接调用 (无需 bsk)
curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/currencies/rates" | jq .
```

Assertions:
- [ ] 返回 200 + 全量汇率表 (每个币种包含 `rate` 和 `fetched_at` 字段)
- [ ] 所有汇率 > 0 (非 0 / 非 null / 非 1:1 fallback)
- [ ] 每个币种的 `fetched_at` 时间戳在 24 小时内 (非过期数据)
- [ ] `GET /currencies` 返回支持的货币列表 (含代码 + 名称 + 符号 + flag_emoji + is_favorite + sort_order)
- [ ] `[console]` zero errors (curl 不适用, 但前端调用 /rates 时不应报 console 错误)
