# Area 7 — Regression sweep (历史缺陷回归)

Shared conventions in [`_common.md`](../../_common.md).

## Success Criteria (成功标准)

### Pass Threshold
- **Overall pass rate**: 100% (all 9 regression cases MUST pass — zero tolerance for historical bug recurrence)
- **Critical cases** (MUST pass): R1 (¥¥), R2 (bigint), R4 (NProgress), R6 (auth expiry)
- **Execution order**: R6 MUST run LAST (session-destroying test)

### Performance Benchmarks
| Case | Metric | Target | Max |
|------|--------|--------|-----|
| R1-R5, R7-R9 | Per-case time | < 30s | < 60s |
| R6 (auth expiry) | Session cleanup | < 5s | < 10s |
| Total runtime | All 9 cases | < 10min | < 15min |
| All cases | Console errors | 0 | 0 |

### Regression Quality Checks
- **R1**: No `¥¥` double symbol on ANY page (Dashboard, assets, liabilities, wishes)
- **R2**: No scientific notation (e.g., `5.9e7`) in money fields
- **R3**: No raw i18n keys (e.g., `dashboard.net_worth`) in en-US mode
- **R4**: NProgress completes after rapid navigation (no stuck spinner)
- **R5**: KeepAlive pages load once (no double onMounted/onActivated)
- **R6**: Auth expiry redirects to login correctly (session cleared)
- **R7**: AI chat shows response (not blank/error-stuck)
- **R8**: Child coin display has no ¥ symbol (coin-based, not currency)
- **R9**: CSP allows required eval in docker mode (no console violations)

---

Auth: adult session as `demouser` (owner). 本 Area 为只读验证，不修改任何数据。
每个用例对应一个已修复的历史缺陷，防止回归。来源见项目 memory 文件。

> **运行时机:** 建议作为每轮 sim-test 的 **最后一步**（G1 内排在 area2/3/6 之后），
> 确保核心功能验证完毕后再做回归扫描。

---

## R1 — 双货币符号回归 (¥¥ double-currency)

**Critical case:** MUST pass | **Performance target:** All pages < 2s

**历史缺陷:** `useCurrency().format()` 已前缀 `¥`，但模板/i18n 又加了字面 `¥`，
导致显示 "¥¥0.00"、"¥¥3,000"。修复: i18n 去掉字面 `¥`，模板去掉冗余 `¥`。

```
bsk navigate ${BASE} --session <id> --wait-until networkidle   # Dashboard
bsk snapshot --session <id>
bsk navigate ${BASE}finance?tab=assets --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk navigate ${BASE}finance?tab=liabilities --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk navigate ${BASE}finance?tab=wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Dashboard 所有金额仅显示 **一个** 货币符号 (¥ 或当前币种)
- [ ] Asset list 金额无 `¥¥` 前缀
- [ ] Liability list 金额无 `¥¥` 前缀
- [ ] Wish list 金额无 `¥¥` 前缀
- [ ] `[console]` zero errors
- [ ] **grep 回归 (可选):** `grep -rn '¥.*format(' frontend/apps/main/src/` 应返回 0 命中

**Automated assertion (recommended):**
```bash
# Verify no double currency symbols across all pages
bsk evaluate --session <id> --expr "(async () => {
  const text = document.body.innerText;
  const hasDoubleSymbol = /¥¥|\$\$|€€|££/.test(text);
  const pages = ['Dashboard', 'Assets', 'Liabilities', 'Wishes'];
  return JSON.stringify({hasDoubleSymbol, pages, safe: !hasDoubleSymbol});
})()"
# Expected: {"hasDoubleSymbol":false,"pages":[...],"safe":true}
```

---

## R2 — 币种精度回归 (Snowflake ID / bigint precision)

**历史缺陷:** JS 对 >2⁵³ 整数丢失精度。修复: 所有 bigint 字段序列化为 str，
前端 type 为 string。

```
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk evaluate --session <id> --expr "document.body.innerText.match(/[0-9]{16,}/g)"
```

Assertions:
- [ ] Dashboard total assets 不使用科学计数法 (如 `5.9e7`)
- [ ] 大额资产 (如 demouser 的 ~59M) 正确显示为格式化字符串 (如 "59,000,000.00")
- [ ] 无 `NaN`、`undefined`、`null` 出现在金额字段
- [ ] Asset/liability ID 不出现在 UI 中作为原始数字 (应为 str 序列化)
- [ ] `[console]` zero errors

---

## R3 — en-US locale 缺失回退回归

**历史缺陷:** en-US locale 缺少 `liability.interest`/`liability.strategy` 等子块，
导致切换英文时部分页面显示 key 而非翻译。

```
# 切换语言到 English (如果有语言切换入口)
bsk navigate ${BASE}settings --session <id> --wait-until networkidle
bsk snapshot --session <id>
# 检查是否有语言切换选项
# 如果有 → 切换到 en-US → 导航到各页面
# 如果没有 UI 入口 → 通过 evaluate 修改 localStorage 并 reload
bsk evaluate --session <id> --expr "localStorage.setItem('numina_language', 'en-US'); 'set'"
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk navigate ${BASE}finance?tab=liabilities --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Dashboard 切换英文后无 raw key (如 `dashboard.net_worth`) 显示
- [ ] Liability 页面策略卡片英文渲染正常 (无 `liability.strategy.*` key 泄露)
- [ ] 导航回中文后恢复正常
- [ ] `[console]` zero errors

---

## R4 — NProgress 卡住回归

**历史缺陷:** `Transition mode="out-in"` 延迟 mount 超过 afterEach 200ms timeout，
导致 NProgress 重启并永远停不下来。修复: 500ms timeout + routerDone flag。

```
# 快速连续导航多个页面，模拟触发条件
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk navigate ${BASE}finance?tab=wishes --session <id>
bsk navigate ${BASE}finance?tab=assets --session <id>
bsk navigate ${BASE}finance?tab=liabilities --session <id>
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk wait-ms 1s
bsk evaluate --session <id> --expr "document.querySelector('#nprogress')?.style?.cssText || 'no-nprogress-element'"
```

Assertions:
- [ ] 快速导航后 NProgress bar 完全消失 (无残留进度条)
- [ ] `#nprogress` 元素的 opacity 为 0 或 display 为 none
- [ ] 页面无白屏/卡死
- [ ] `[console]` zero errors

---

## R5 — KeepAlive 双重加载回归

**历史缺陷:** Vue 3 KeepAlive 首次 mount 同时触发 onMounted + onActivated，
导致页面数据加载两次。修复: hasActivated flag pattern。

```
# 导航到 Dashboard → 离开 → 返回，观察是否双重加载
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk evaluate --session <id> --expr "window.__dashboardFetchCount = 0; const origFetch = window.fetch; window.fetch = (...a) => { if (a[0]?.includes?.('/dashboard/overview')) window.__dashboardFetchCount++; return origFetch(...a); }; 'interceptor-installed'"
bsk navigate ${BASE}finance?tab=wishes --session <id> --wait-until networkidle
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk wait-ms 1s
bsk evaluate --session <id> --expr "String(window.__dashboardFetchCount || 'no-interceptor')"
```

Assertions:
- [ ] Dashboard 返回时 `/dashboard/overview` 只被调用 **一次** (非两次)
- [ ] 页面数据正常渲染 (无空态闪烁)
- [ ] `[console]` zero errors

---

## R6 — Auth session 过期重定向回归

**历史缺陷:** session 过期时 showDialog 阻塞而非立即重定向到 /login。
修复: 去掉 showDialog，直接 redirect。

```
# 清除 auth 状态模拟过期
bsk evaluate --session <id> --expr "localStorage.removeItem('numina_user'); 'cleared'"
bsk navigate ${BASE}settings --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk evaluate --session <id> --expr "location.href"
```

Assertions:
- [ ] 清除 localStorage 后导航到受保护页面 → 自动重定向到 `/login`
- [ ] 无 showDialog 模态框阻塞 (页面直接跳转)
- [ ] 重定向后 URL 包含 `/login`
- [ ] `[console]` zero errors (401 是预期的，不算错误)

> **注意:** 此用例会破坏当前 session。执行后需重新登录 (Phase 2 fallback)
> 才能继续后续用例。建议在回归的最后执行，或单独一轮。

---

## R7 — AI Chat 空响应/错误清理回归

**历史缺陷:** AI chat 偶发空白响应、错误状态未清理、重复 greeting。
修复涉及多处: blank-response fix, error-cleanup fix, retry-duplicate fix。

```
# 前提: AI 已启用。导航到 AI chat
bsk navigate ${BASE}ai/chat --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] 页面加载后无空白消息气泡
- [ ] 无重复的 greeting 消息
- [ ] 输入框可正常输入 (非 disabled/loading 状态)
- [ ] 如果有历史对话 → 消息列表无 `[content empty]` 或 `undefined` 占位
- [ ] `[console]` zero errors (无 SSE/EventSource 未关闭警告)

---

## R8 — 儿童端 coin 不显示货币符号回归

**历史缺陷:** 儿童端使用 coin (整数)，不应出现 `¥` 或 `useCurrency`。
曾有混淆将成人 currency 逻辑带入儿童端。

```
bsk navigate ${CHILD_BASE} --session <child_id> --wait-until networkidle
bsk snapshot --session <child_id>
bsk navigate ${CHILD_BASE}ledger --session <child_id> --wait-until networkidle
bsk snapshot --session <child_id>
```

Assertions:
- [ ] Child home 余额显示为整数 coin (如 "120 ⭐")，无 `¥` 前缀
- [ ] Ledger 交易金额为整数，无 `¥` / `useCurrency` 格式化
- [ ] 无 `NaN` / `undefined` 出现在 coin 数值中
- [ ] `[console]` zero errors

---

## R9 — CSP unsafe-eval 回归 (ECharts / vue-i18n)

**历史缺陷:** nginx CSP 缺少 `unsafe-eval` 导致 ECharts/vue-i18n 在
production build 下被阻止。修复: CSP script-src 添加 `unsafe-eval`。

```
# 仅 docker 模式适用 (dev 模式无 nginx CSP)
bsk navigate ${BASE} --session <id> --wait-until networkidle
bsk evaluate --session <id> --expr "typeof echarts !== 'undefined' ? 'echarts-loaded' : 'echarts-missing'"
```

Assertions:
- [ ] `echarts` 全局对象存在 (CSP 未阻止加载)
- [ ] Dashboard trend chart 渲染正常 (非空白 canvas)
- [ ] `[console]` 无 `Refused to evaluate a string` CSP 违规
- [ ] docker 模式: `curl -sI $BASE | grep Content-Security-Policy` 包含 `unsafe-eval`

---

## Quick Reference

| Case | 回归目标 | 涉及组件 | Memory 来源 |
|------|----------|----------|-------------|
| R1 | ¥¥ 双符号 | useCurrency, 模板 | yy-double-currency-bug |
| R2 | bigint 精度 | SnowflakeBase, API | sim-test-nav-coverage |
| R3 | en-US 缺失 | i18n locale | sim-test-nav-coverage |
| R4 | NProgress 卡住 | router afterEach | nprogress-out-in-transition-race |
| R5 | KeepAlive 双加载 | onActivated flag | keepalive-onactivated-double-load |
| R6 | Auth 过期重定向 | auth guard | 505d6b61 commit |
| R7 | AI Chat 空响应 | AIChatBox | ai-chat-blank-response-fix |
| R8 | 儿童端 coin 符号 | ChildHomePage | sim-test-nav-coverage |
| R9 | CSP unsafe-eval | nginx config | 348b5f99 commit |
