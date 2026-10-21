---
name: numina-sim-test
description: >
  Use when the user wants to run full-stack functional verification tests,
  audit the interface, capture screenshots, or verify deployed UI flows for
  the Numina project. Covers 20 areas across child app, financial management,
  AI capabilities, currency, regression, expanded features, security/notification,
  AI report, adversarial security, task resilience, travel, UI quality/design
  system, learning OS (taxonomy/core/parent/optimization), and MCP token governance.
  Triggers on: "run sim test", "ui audit", "截图测试", "仿真测试", "全栈验收",
  "功能验收", "ui检查", "界面审查", "check the UI", "test the app visually",
  "儿童测试", "child frontend test", "test AI chat/report/PDF import",
  "ui quality", "设计审查", "UI 质量检查", "dark mode test", "深色模式测试",
  "mobile test", "移动端测试", "dev server test", "5173/5174 测试",
  "热加载测试", "HMR test", "accessibility test", "无障碍测试",
  "security test", "安全测试", "learning test", "学习测试", "curriculum test",
  "课标测试", "travel test", "旅行测试", "MCP token test",
  or any request to verify the deployed app's features.
---

# Numina Full-Stack Functional Verification Pipeline

End-to-end pipeline for browser-based full-stack functional verification. The pipeline
covers 20 test areas (UI flows, AI capabilities, security adversarial, design system
quality, learning OS taxonomy, MCP token governance, and more). It detects the best available browser driver at startup (priority:
**browser-use** → **bsk** → **Chrome DevTools MCP**) and drives the user's real browser
through authenticated flows, screenshot capture, and test report generation.

> **Browser driver:** All browser interaction commands are abstracted in this
> skill. For the concrete command syntax of the active driver, read
> [`references/browser-drivers.md`](./references/browser-drivers.md) only when
> you need the exact commands. The detection logic runs in Phase 0.

> **Scope:** this skill does ONLY browser-based UI simulation. It does NOT
> seed the database or run API acceptance tests — those are out of scope. The
> environment must already contain the test accounts below (see
> "Prerequisites").

Covers **twenty** feature areas (detailed cases split by area under
[`test-cases/`](./test-cases/), shared conventions in
[`test-cases/_common.md`](./test-cases/_common.md), role matrix in
[`test-cases/role-capabilities.md`](./test-cases/role-capabilities.md)):
1. **Child app** (`$CHILD_BASE`) — 儿童页面优化
2. **Main app financial management** (`$BASE`) — 财务管理能力优化
3. **AI capabilities** — PDF识别 / AI资产报告 / 数鸣智能体 / AI对话
4. **Main app navigation coverage** (`$BASE`) — 每个页签 + 子页面 + 币种切换校验 ([`test-cases/groups/g2-adult-currency/area4-navigation.md`](./test-cases/groups/g2-adult-currency/area4-navigation.md))
5. **Child app navigation coverage** (`$CHILD_BASE`) — 每个页签 + 子页面 ([`test-cases/groups/g3-child/area5-child-navigation.md`](./test-cases/groups/g3-child/area5-child-navigation.md))
6. **AI chat DeerFlow-fidelity parity** — 输入/输出/系统集成 + 设计出入 ([`test-cases/groups/g1-adult-stable/area6-ai-chat-parity.md`](./test-cases/groups/g1-adult-stable/area6-ai-chat-parity.md))
7. **Regression sweep** — 历史缺陷回归 (R1–R9) ([`test-cases/groups/g1-adult-stable/area7-regression.md`](./test-cases/groups/g1-adult-stable/area7-regression.md))
8. **Expanded feature coverage** — Manifesto / 盲盒 / Baby / Settings / Guest / 权限边界 (F.1–F.8, F.11, F.12) ([`test-cases/groups/g1-adult-stable/area8-expanded-features.md`](./test-cases/groups/g1-adult-stable/area8-expanded-features.md))
9. **Account security + notification** — WebAuthn / 2FA / 设备管理 / 通知规则 (C9.1–C9.7) ([`test-cases/groups/g1-adult-stable/area9-security-notification.md`](./test-cases/groups/g1-adult-stable/area9-security-notification.md))
10. **Guest 端到端注册 + 加入家庭** — 注册 / 邀请码 / 已登录守卫 (C10.1–C10.4) ([`test-cases/groups/g1-adult-stable/area10-guest-join-flow.md`](./test-cases/groups/g1-adult-stable/area10-guest-join-flow.md))
11. **AI/agent adversarial security** — 提示词注入 / 跨租户隔离 / 工具越权 / 自定义智能体隔离 / 输入边界 (C11.1–C11.20) ([`test-cases/groups/g1-adult-stable/area11-ai-security-adversarial.md`](./test-cases/groups/g1-adult-stable/area11-ai-security-adversarial.md))
12. **AI task resilience** — 前端不稳定处理：离开/刷新恢复、失败/中断重试、用户取消 (C12.1–C12.9) ([`test-cases/groups/g1-adult-stable/area12-ai-task-resilience.md`](./test-cases/groups/g1-adult-stable/area12-ai-task-resilience.md))
13. **AI 资产报告深度验证** — Hub 弹窗内容/z-index、报告重入步骤去重/SSE 重连/取消按钮、narrative 缓存推导 (C13.1–C13.5) ([`test-cases/groups/g1-adult-stable/area13-ai-asset-report-deep.md`](./test-cases/groups/g1-adult-stable/area13-ai-asset-report-deep.md))
14. **Travel core (Trip/Expense/Split/Dashboard)** — 旅行 Tab / 行程 CRUD / 费用记账 / 多币种 / 心愿转化 / 分摊结算 / 魔法链接 / Dashboard travel_float (C14.1–C14.22) ([`test-cases/groups/g1-adult-stable/area14-travel.md`](./test-cases/groups/g1-adult-stable/area14-travel.md)) + **Itinerary planning** (C14.23–C14.40) ([`test-cases/groups/g1-adult-stable/area14-itinerary.md`](./test-cases/groups/g1-adult-stable/area14-itinerary.md))
15. **UI quality & design system audit** — 移动端 H5/PWA 适配 / 深色模式 / Vant4 组件规范 / 无障碍 / 安全区域 / 跨应用风格一致性 (UIQ.1–UIQ.10) ([`test-cases/groups/g1-adult-stable/area15-ui-quality.md`](./test-cases/groups/g1-adult-stable/area15-ui-quality.md))
16. **Learning OS taxonomy Beijing + curriculum/edge-status** — 课标徽章/callout / AI 生成边标识别 / locale 知识图谱过滤 / 深色模式可读性 (C16.1–C16.14) ([`test-cases/groups/g3-child/area16-learning-os-taxonomy.md`](./test-cases/groups/g3-child/area16-learning-os-taxonomy.md))
17. **Learning OS core flows (child)** — 知识地图 / Topic 详情 / AI 导师对话 / 学习进度 / 今日学习卡片 / 自选学习难度提示 (C17.1–C17.21) ([`test-cases/groups/g3-child/area17-learning-os-core.md`](./test-cases/groups/g3-child/area17-learning-os-core.md))
18. **Learning OS (家长端 + 端到端闭环)** — 学习 Hub / 智能推荐 / 预设路径 / DNA图谱 / 双轨审核 / 来源标签 / 闭环流程 (C18.1–C18.24) ([`test-cases/groups/g1-adult-stable/area18-learning-os.md`](./test-cases/groups/g1-adult-stable/area18-learning-os.md))
19. **MCP external API token & governance** — Token 生命周期 / 认证 / 两级访问控制 / 审计日志 / 速率限制 (M20.1–M20.15) ([`test-cases/groups/g1-adult-stable/area20-mcp-external-token.md`](./test-cases/groups/g1-adult-stable/area20-mcp-external-token.md))

> Areas 4–6 are navigation-coverage + parity suites. Area 4 includes the
> **currency-switch bug class** (amounts not re-converted by rate after switching
> `default_currency`) — confirmed by source audit, see
> [`test-cases/groups/g2-adult-currency/area4-navigation.md`](./test-cases/groups/g2-adult-currency/area4-navigation.md) "Currency-switch
> bug class". Area 6 tests numina's AI chat against DeerFlow's interaction contract
> and flags **design divergences** (D1 `/goal`, D2 `/compact`, D3 input-polish,
> D4 user-selectable reasoning_effort, D5 TodoList bar, D6 Scheduled Tasks,
> D7 Thread Channel Source).
>
> Areas 16–18 form the **Learning OS** cluster: Area 16/17 run in the child app
> (G3), Area 18 runs in the adult app (G1) with some child-side cases
> (C18.18–C18.24) that reuse `$SID_CHILD` within the G1 agent.

## Parallel Run Structure (3 agents, dev mode)

The eight area files are organized into **4 groups by state-isolation boundary**
under [`test-cases/groups/`](./test-cases/groups/) so 2-3 agents can run them in
parallel without racing on shared browser state. See
[`test-cases/groups/README.md`](./test-cases/groups/README.md) for the full
schedule + verified browser concurrency evidence.

> **Browser concurrency (verified 2026-07-21):** Concurrent browser sessions are
> supported. BUT all sessions share **one browser profile** — `cookie`/`localStorage`
> are shared **per origin** (a value written by session A is readable by session B
> on the same origin). So parallel agents must operate **different origins** (adult
> :5173 vs child :5174 in dev) OR non-overlapping global state. The groups are
> cut along those boundaries.

| Group | Dir | Areas | Session | State domain | Parallel with |
|-------|-----|-------|---------|--------------|---------------|
| **G0** preconditions | [`g0-preconditions/`](./test-cases/groups/g0-preconditions/) | Phase 0/1/1.5/2 | serial | establishes login | none — first |
| **G1** adult-stable | [`g1-adult-stable/`](./test-cases/groups/g1-adult-stable/) | 2, 3, 6, 7, 8, 9, 11, 12, 13, 14, 15, 18, 19, 20 | `$SID` (adult) | reads global; per-entity writes | **G3** |
| **G2** adult-currency | [`g2-adult-currency/`](./test-cases/groups/g2-adult-currency/) | 4 | adult (own) | **mutates `default_currency`** | **G3** |
| **G3** child | [`g3-child/`](./test-cases/groups/g3-child/) | 1, 5, 10, 16, 17 | `$SID_CHILD` | child origin (isolated dev) | **G1 or G2** |

**Schedule:** `G0 (serial) → G1 ‖ G3 (parallel) → G2 (after G1)`. Three agents
cover all cases; wall-clock ≈ G0 + max(G1, G3) + G2 instead of sequential.

> **G1 internal order:** area2 → area14 → area18 → area8 → area3 → area6 → area13 → area12 → area15 → area9 → area7 → area11 → area20. Area 7
> (regression) runs near the end, with R6 (auth expiry) destroying the
> session **last** so earlier areas have a live session. Area 14 (travel) runs
> after area2 since both create financial entities. Area 13 (AI report deep)
> runs after area6 (AI chat parity) since both exercise AI surfaces. Area 15
> (UI quality) runs before regression since it needs a stable session for
> dark-mode toggling and viewport tests. Area 9 (security/notification) runs
> after area15 since it exercises WebAuthn/2FA flows. Area 11 uses adult
> session read-only probes. Area 20 (MCP token) runs last since it
> generates/consumes tokens.

> **Docker mode caveat:** nginx serves adult + child under **one origin** (:80)
> → G3 is NOT parallel-safe with G1/G2 (shared cookie + localStorage). The
> adult `access_token` cookie causes the child SPA's `verifyChildSession()` to
> fail (backend returns 4xx for non-child role), redirecting to the adult
> login page. In docker, run G3 **serially after G1/G2**, with cookie +
> localStorage clearing + child session re-injection before G3 starts. See
> [`area1-child.md`](./test-cases/groups/g3-child/area1-child.md) "Docker mode
> — cookie clearing required" for the exact steps. The parallel benefit is
> **dev-mode-only** (child :5174 is a separate origin).

> **Agent rules:** (1) each agent reuses the G0 session id for its group — do
> NOT start a new session, do NOT stop a shared session;
> **exception:** in docker mode, G3 must stop the adult session, clear cookies,
> and start a fresh session for child testing (see Phase 5);
> (2) prefix failures in the report with the group (`G1-C2.3`, `G3-C1.10`);
> (3) never split a single group across two agents — they share that group's
> session and would race.
>
> **Chrome DevTools MCP caveat:** When MCP is the active driver, parallel
> agents share one MCP server — `select_page`/`navigate_page` calls from one
> agent affect the other's tabs. Each agent MUST open its own page via
> `new_page()` and call `select_page` before every interaction. If coordination
> issues arise, fall back to serial execution.

> `$BASE` / `$CHILD_BASE` / `$API_BASE` are set per deployment mode — see
> "Deployment Mode" below. Routes (`/login`, `/child/`, `/ai/chat`, …) are the
> same in every mode; only the host:port differs.

## Run Modes (运行模式)

根据时间和目的选择不同的运行粒度:

| Mode | 触发词 | 覆盖范围 | 预计耗时 |
|------|--------|----------|----------|
| **full** | "run sim test", "全量测试" | Area 1–20 (所有用例) | ~220-270 min |
| **smoke** | "smoke test", "快速检查" | C2.1, C2.2, C2.5, C2.8, C3.1, C3.2, C4.0, R1, R2, C9.4 | ~18-25 min |
| **child** | "child test", "儿童测试" | Area 1 + Area 5 (G3 only) | ~20-30 min |
| **finance** | "finance test", "财务测试" | Area 2 only (G1 subset, C2.1–C2.25) | ~20-25 min |
| **ai** | "ai test", "AI测试" | Area 3 + Area 6 + Area 12 + Area 13 (G1 subset, AI 必须启用) | ~35-45 min |
| **regression** | "regression test", "回归测试" | Area 7 only (R1–R9) | ~10-15 min |
| **security** | "security test", "安全测试" | Area 9 (C9.1–C9.7) + Area 11 (C11.1–C11.20) + R6 | ~25-35 min |
| **travel** | "travel test", "旅行测试" | Area 14 only (C14.1–C14.40, two files) | ~45-55 min |
| **ui-quality** | "ui quality", "设计审查", "UI 质量检查" | Area 15 only (UIQ.1–UIQ.10) | ~25-35 min |
| **learning** | "learning test", "学习测试" | Area 16 + Area 17 (G3) + Area 18 (G1) + Area 19 (G1) + Area 20 (G1) | ~70-85 min |
| **area-N** | "test area N", "测试区域N" | 指定 Area N 的用例 | varies |

**选择逻辑:**
1. 用户未指定模式 → 默认 `full`
2. 用户说"快速检查" / "smoke" → `smoke` (仅跑关键路径的 10 个用例)
3. 用户明确指定某个 area 或功能域 → 跑对应的 area
4. `smoke` 模式跳过 Area 1/5/7/8/9/10/11/12/14/15, 仅验证核心 adult 功能 + 币种回归 + 通知触发
5. `ui-quality` 模式需要 adult + child 两个 session; 先跑 G0 前置, 再跑 Area 15
6. 域别名（`child`/`finance`/`ai`/`regression`/`security`/`travel`/`ui-quality`）等同于对应的 Area 组合，执行路径与 `area-N` 相同——别名仅用于触发词匹配，不引入额外执行逻辑

---

## Deployment Mode (declare before running)

This pipeline supports **two deployment targets**. All subsequent phases use
the mode-specific `BASE` / `CHILD_BASE` / `API_BASE` values instead of a
hard-coded URL.

### Mode selection — probe order (run FIRST, before Phase 0)

用户明确说 "用 docker 测试" / "用 dev 测试" / 指定了 BASE → 直接采用, 跳过探测。
用户未指定 → 按以下顺序探测, 取第一个命中的规则:

1. **dev server 同源探测 (优先)** — :5173 有进程监听 **且** 该进程的 cwd
   在**当前仓库路径**下 (`git rev-parse --show-toplevel` 的子路径) → 选
   `dev`。理由: vite HMR 让大部分前端修复无需 rebuild 即刻生效, 修复-复测
   循环最快。
2. **docker 探测** — `curl -sf http://localhost/` 返回 200 → 选 `docker`。
3. **两者都不可用** → 停止, 按 Phase 1 的提示语让用户先启动服务。
4. **两者同时可用** → 仍选 `dev` (规则 1 优先), 在报告 "测试环境" 段注明
   `探测: 5173 同源 dev server (docker 亦可用)`; 用户可随时说 "用 docker 重跑"。

```bash
# Mode probe (在仓库根执行)
ROOT="$(git rev-parse --show-toplevel)"
PID=$(lsof -tiTCP:5173 -sTCP:LISTEN 2>/dev/null | head -1)
DEV_MATCH=0
if [ -n "$PID" ]; then
  CWD=$(lsof -p "$PID" 2>/dev/null | awk '/cwd/ {print $NF}')
  case "$CWD" in "$ROOT"/*) DEV_MATCH=1 ;; esac
fi
if [ "$DEV_MATCH" = "1" ]; then
  echo "MODE=dev (5173 同源 dev server, cwd=$CWD)"
elif curl -sf -o /dev/null --max-time 3 http://localhost/; then
  echo "MODE=docker"
else
  echo "未探测到可用部署 — 先启动 dev servers (make dev-all) 或 docker (make up)"; exit 1
fi
```

> **不要只看 `docker ps` 判定 docker 模式。** 容器可能全部 `Up` 但 nginx
> 处于重启循环 (:80 死)。已验证 (2026-10-14): `docker ps | grep numina`
> 全部 OK, `curl localhost/` 却失败 (numina-nginx Restarting)。docker 判定
> 必须以 curl 探测 BASE 为准。

### Mode `docker` (nginx proxy, single entry)

All services behind `docker-compose` + nginx on port 80.

| Var | Value |
|-----|-------|
| `BASE` | `http://localhost/` (adult SPA) |
| `CHILD_BASE` | `http://localhost/child/` (child SPA, nginx strips prefix) |
| `API_BASE` | `http://localhost/api/v1` (nginx → backend:8000) |
| Health check | `docker ps` + `curl http://localhost/` |
| Rebuild after code change | `docker-compose build frontend && docker-compose up -d frontend` (or `frontend-child`) |

### Mode `dev` (local vite + uvicorn, separate ports)

Local dev servers started manually (NOT by this skill — see CLAUDE.md "Never
run dev servers from automated agents"). The user must already have running:
`pnpm dev` (main:5173, child:5174) + `uv run uvicorn` (backend:8000, agent:8001,
worker:8002). Vite proxies `/api` → backend:8000 and `/api/threads` → agent:8001,
so the SPA still calls `/api/...` relatively.

| Var | Value |
|-----|-------|
| `BASE` | `http://localhost:5173/` (adult SPA, vite) |
| `CHILD_BASE` | `http://localhost:5174/child/` (child SPA, vite `base: '/child/'`) |
| `API_BASE` | `http://localhost:8000/api/v1` (backend direct; or `http://localhost:5173/api/v1` via vite proxy) |
| Health check | `curl` against :5173, :5174/child/, :8000 (no `docker ps`) |
| Rebuild after code change | none — vite HMR auto-reloads; verify via `pnpm typecheck` only |

> **Child path stays `/child/` in both modes** (vite `base: '/child/'`), so
> `test-cases/` routes are unchanged — only the host:port differs.

> **Cookie sharing caveat:** In **dev mode**, adult (:5173) and child (:5174)
> are different origins, so the adult session cookie does NOT carry over to the
> child port. In dev mode, log into the child SPA directly at
> `http://localhost:5174/child/` (the child login/PIN flow re-establishes
> the session for that origin). In **docker mode**, both apps share one
> origin (:80) — the adult `access_token` cookie interferes with the child
> SPA's route guard. Before child testing in docker, clear all cookies +
> localStorage and re-inject the child session (see
> [`area1-child.md`](./test-cases/groups/g3-child/area1-child.md) "Docker mode
> — cookie clearing required").

### Setting the vars for the run

After the mode is determined (user-specified or auto-probed above), export the three vars once and reference
`$BASE` / `$CHILD_BASE` / `$API_BASE` in every Phase below:

```bash
# docker
export BASE=http://localhost/ CHILD_BASE=http://localhost/child/ API_BASE=http://localhost/api/v1

# dev
export BASE=http://localhost:5173/ CHILD_BASE=http://localhost:5174/child/ API_BASE=http://localhost:8000/api/v1
```

---

## Project Context

- **Base URLs**: see "Deployment Mode" above — `$BASE`, `$CHILD_BASE`, `$API_BASE`
- **Adult demo account**: `demouser` / `DemoPass123`
- **Child accounts** (under demouser family):
  - Display_names are **discovered at gate time** (Phase 1.5) via
    `/family/members` where `role=="child"` — not hard-coded.
  - Docker seed default: 小宝 (`xiaobao`), 大宝 (`dabao`), PIN `🐱🐶🌟🌈`.
  - Dev/other deployments may differ (e.g. `demochild`, 小明). See
    [`test-cases/_common.md`](./test-cases/_common.md) for the convention.
- **Regression test accounts**:
  - `test_rich` / `TestRich123!` — full data (assets + liabilities + wishes + children)
  - `test_child`: `testchild`, PIN `🐱🐶🌟🌈` (under test_rich family)
- **Frontend**: Vue 3 + TypeScript + Vant 4 + ECharts, mobile-first (375×812)
- **UI language**: 简体中文
- **Output paths** (gitignored — local only):
  - Screenshots: `dogfood-output/<name>.png`
  - Report: `tests/reports/ui-audit-YYYY-MM-DD.md` (one file per day; gitignored — local only. Historical reports already tracked under this path remain tracked; new daily reports are not committed)

### Prerequisites (NOT handled by this skill)

This skill only drives the browser. The following must already be true before
Phase 0:
1. Services are running in the chosen deployment mode (docker or dev).
2. The test accounts above exist in the database with the listed credentials
   and have the expected data (assets/liabilities/wishes/children). If login
   fails or pages render empty, the database has not been prepared — ask the
   user to seed it out-of-band (e.g. via `tests/data/seed-data.sh` run
   separately); do **not** run seed-data from this skill.

### Monorepo Structure

```
frontend/
  apps/
    main/        ← adult frontend source
    child/       ← child frontend source
  packages/
    auth/        ← shared auth package
```

> Always edit `frontend/apps/child/` for child frontend, `frontend/apps/main/`
> for adult frontend. Old `frontend-child/` path no longer exists.

---

## Phase 0 — Browser Driver Detection (MANDATORY first step)

Before any UI testing, detect which browser driver is available. Priority order:
**browser-use** → **bsk** → **Chrome DevTools MCP**.

```bash
# 1. Check browser-use (highest priority)
if command -v browser-use &>/dev/null; then
  BROWSER_DRIVER="browser-use"
  browser-use --doctor 2>/dev/null && echo "browser-use: OK" || echo "browser-use: daemon issue"

# 2. Check bsk (second priority)
elif command -v bsk &>/dev/null; then
  BROWSER_DRIVER="bsk"
  bsk doctor 2>/dev/null && echo "bsk: OK" || echo "bsk: extension issue"

# 3. Chrome DevTools MCP — agent must self-check tool list BEFORE running this script.
# If mcp__chrome-devtools__navigate_page is in the session's available tools,
# set MCP_CHROME_DEVTOOLS=1 before invoking this detection script.
elif [ "${MCP_CHROME_DEVTOOLS:-0}" = "1" ]; then
  BROWSER_DRIVER="chrome-devtools"
  echo "chrome-devtools MCP: OK"

else
  echo "ERROR: No browser driver found."
  echo "Install browser-use (recommended):"
  echo "  uv tool install browser-use"
  echo "  browser-use --doctor   # verify connection"
  exit 1
fi
```

**If none are available**, stop and tell the user:

> No browser driver detected. Install one to proceed:
> - **browser-use** (recommended): `uv tool install browser-use` then `browser-use --doctor`
> - **bsk**: install browser-skill CLI + extension
> - **Chrome DevTools MCP**: configure the chrome-devtools MCP server in Claude settings

**Do not proceed to later phases until a driver is confirmed working.**

### Browser interaction (all phases)

All subsequent phases describe steps abstractly (navigate → observe → interact → screenshot).
For the concrete commands of the active driver, read
[`references/browser-drivers.md`](./references/browser-drivers.md).

Key concepts common to all drivers:
- **Session/tab lifecycle**: Open a tab for the test session, close it when done
- **Observation priority**: Accessibility tree / snapshot first; screenshot or raw HTML only when snapshot is insufficient
- **Refs invalidate after navigation**: Always re-snapshot before interacting on a new page
- **Mobile viewport**: Numina is mobile-first (375×812); set viewport if the driver supports it

---

## Phase 1 — Service Health Check

```bash
# Common (both modes): probe the three entry points
curl -sf "$BASE" -o /dev/null && echo "adult: UP" || echo "adult: DOWN"
curl -sf "$CHILD_BASE" -o /dev/null && echo "child: UP" || echo "child: DOWN"
curl -sf "${API_BASE%/v1}/health" -o /dev/null && echo "api: UP" || echo "api: DOWN"
```

### docker mode — also check containers

```bash
docker ps --format "{{.Names}}\t{{.Status}}" | grep numina
```

If any service is DOWN, tell the user:
- **docker**: `Services are not running. Start them with 'docker-compose up -d', then re-run this skill.`
- **dev**: `Dev servers not running. Start: 'pnpm dev' in frontend/apps/main (and /child) + 'uv run uvicorn apps.backend.app.main:app --port 8000' (+ agent :8001, worker :8002) from server/. The user must run these — agents must not start dev servers.`

**Child frontend specific checks:**
- **docker**: verify `numina-frontend-child` container running; nginx routes `/child/` → assets from `/child/assets/`. If 404, check `nginx.conf` `proxy_pass http://frontend-child/` (no `/child/` suffix).
- **dev**: child served by vite at `:5174` with `base: '/child/'`; assets from `/child/assets/`. No nginx.

---

## Phase 1.5 — Precondition Gate (MANDATORY before UI phases)

Verify the `demouser` family has enough data to satisfy test assertions.
The gate runs 8 checks via curl (login, /auth/me role, ≥1 child member,
assets > 0, AI provider, wish savings, high-interest liabilities, child auth).
Stop at first failure — do NOT proceed to Phase 2 if gate fails.

> **Full gate script:** [`references/phase-1-5-gate.md`](./references/phase-1-5-gate.md)

## Phase 2 — Login + Session Setup (browser)

Establish the authenticated adult session that all subsequent UI phases share.

**Steps:**
1. Open a browser session/tab and navigate to `${BASE}login`
2. Wait for the page to fully load
3. Take a snapshot to identify form field elements
4. Fill the username field with `demouser`
5. Fill the password field with `DemoPass123`
6. Take a snapshot to identify the submit button
7. Click submit
8. Wait for navigation to complete
9. Take a snapshot to confirm landed on Dashboard

**Driver-specific commands:** See [`references/browser-drivers.md`](./references/browser-drivers.md) for the exact navigate/fill/click/snapshot commands of the active driver.

Assertions:
- [ ] After submit, URL is `$BASE` (Dashboard)
- [ ] No `401` blocking the initial load (cookie auth set)
- [ ] Keep the session/tab for all Area 2 + Area 3 cases

> **Do not close the session yet** — reuse it for Areas 2 & 3.
> Stop/close it only at the end of Phase 5.

> **Login failure = unmet prerequisite.** If `demouser` login fails or the
> dashboard renders empty, the database has not been prepared. Do not seed
> from here — tell the user to prepare the DB out-of-band and re-run.

### Phase 2 fallback — cookie + localStorage injection (password-manager conflict)

If filling the password field activates a password-manager browser extension
that hijacks the tab (observed: tab redirects to `chrome-extension://…` and the
session crashes), do **not** retry the fill. Instead, bypass the password field
entirely by establishing the session from page context via `fetch`:

**Steps:**
1. Navigate to the app root (wait for `domcontentloaded`, NOT `networkidle`)
2. Evaluate JS to POST `/api/v1/auth/login` with `credentials: 'include'` — the browser stores the httpOnly cookie automatically
3. Evaluate JS to fetch `/api/v1/auth/me` and populate `localStorage.setItem('numina_user', ...)` with user data
4. Reload the page so the route guard re-reads localStorage
5. Snapshot to confirm landed on Dashboard

**Driver-specific JS evaluation:** See [`references/browser-drivers.md`](./references/browser-drivers.md) for how each driver evaluates JavaScript.

**Why this is clean (not a red-line violation):**
- `fetch('/auth/login')` from page context is the standard auth flow — the
  httpOnly cookie is set by the server's `Set-Cookie` response header, not by
  JS writing the token.
- No token is read out of storage or logged. The red line "no token theft"
  targets reading `localStorage`/cookies/auth headers on sensitive sites to
  exfiltrate credentials — this injects a session, it does not extract one.
- Prefer the form-login path by default; use this fallback **only** when the
  password-manager extension blocks form login.

**Dev-mode child app (separate origin :5174):** the adult cookie does NOT
carry to the child port. Establish the child session with the two-step emoji
PIN flow from the child origin's page context (step1 → temp_token, step2 →
`set_child_auth_cookies`), then populate `localStorage` so the child SPA
guard's fast-path (`cachedUser?.role === 'child'`) admits without a fetch.
See `test-cases/_common.md` "Child session injection (dev mode — password-manager
fallback)" for the full step1/step2 fetch chain and the domcontentloaded-race
trick.

---

## AI Pre-check (MANDATORY before Area 3/6/12/13)

Area 3 (AI capabilities), Area 6 (AI chat parity), Area 12 (AI task resilience),
and Area 13 (AI report deep) require AI to be enabled. Before running these
areas, verify:

```bash
# Check AI status via API (correct endpoint: /ai/config for per-family configs)
curl -s -H "Authorization: Bearer $TOKEN" "${API_BASE}/ai/config" | jq '[.data.configs[]? | select(.is_active == true)] | length'
```

Or via browser: navigate to `${BASE}ai`, take a snapshot, look for "AI 已启用" or provider config present.

- If AI is **not enabled** → skip Area 3 + Area 6 + Area 12 + Area 13 cases, mark as `SKIP-AI` in
  the report, and continue with other areas.
- If AI provider has no model configured → same skip, note "provider 无模型" in report.

---

## Test Execution (Phases 3–5.7)

Each phase below references a test case file with detailed assertions,
expected results, and step-by-step instructions. Read the case file for
full details before executing.

### Phase 3 — Area 2: Financial Management

Run [area2-finance](./test-cases/groups/g1-adult-stable/area2-finance.md)
(C2.1–C2.25) using the session from Phase 2. Covers Dashboard, wishes,
liabilities, assets.

### Phase 4 — Area 3: AI Capabilities

Run [area3-ai](./test-cases/groups/g1-adult-stable/area3-ai.md)
(C3.1–C3.23). AI must be enabled.
**Streaming wait:** AI generation is slow — wait between snapshots (e.g. 5s),
do not assume one snapshot suffices.
**PDF upload (C3.5):** Click on `<van-uploader>` does not open file picker.
See `test-cases/_common.md` "File upload note" for JS DataTransfer or
curl fallback.

### Phase 5 — Area 1: Child App

Run [area1-child](./test-cases/groups/g3-child/area1-child.md)
(C1.1–C1.17).
**Docker mode:** child shares adult origin — clear cookies + localStorage
before child testing (adult cookie breaks child routes). See area1-child.md.
**Dev mode:** separate child origin (:5174) — start fresh session, inject
child auth via step1/step2 emoji PIN.
End browser session(s) when done. Revoke auth token:
`curl -sf -X POST ${API_BASE}/auth/logout -H "$AUTH" 2>/dev/null || true`
**Driver crash recovery:** verify driver alive → mark remaining as
`SKIP-INFRA` → preserve partial report → attempt recovery → resume.

### Phase 5.5 — Navigation Coverage + AI Chat Parity

**Area 4** — [area4-navigation](./test-cases/groups/g2-adult-currency/area4-navigation.md) (C4.0–C4.16):
nav coverage + currency-switch bug class.
**Area 5** — [area5-child-navigation](./test-cases/groups/g3-child/area5-child-navigation.md) (C5.1–C5.10):
child nav coverage.
**Area 6** — [area6-ai-chat-parity](./test-cases/groups/g1-adult-stable/area6-ai-chat-parity.md)
(C6.1–C6.27): DeerFlow parity. **Design divergences (D1–D7): flag, do NOT fail.**
**Area 7** — [area7-regression](./test-cases/groups/g1-adult-stable/area7-regression.md) (R1–R9):
regression sweep. **R6 destroys session — run last.**
**Area 8** — [area8-expanded](./test-cases/groups/g1-adult-stable/area8-expanded-features.md)
(F.1–F.12): expanded feature coverage.
**Area 9–14** — run per G1 internal order (see "Parallel Run Structure" above).
**Mobile viewport:** All functional cases at **375×812** when possible.
Watch for: `UI-OVERFLOW` (horizontal scroll), `UI-DARK` (unreadable text),
`UI-VANT` (popup clipped in tabs), `UI-TOUCH` (< 44×44px target),
`UI-SAFE` (content behind notch).

### Phase 5.6 — Area 15: UI Quality Audit

Run [area15-ui-quality](./test-cases/groups/g1-adult-stable/area15-ui-quality.md)
(UIQ.1–UIQ.10). Viewport 375×812 required. Both adult + child sessions needed.
> **Details:** [`references/phase-5-6-7-ui-audit.md`](./references/phase-5-6-7-ui-audit.md)

### Phase 5.7 — UX Review Agent

After functional cases complete, spawn a **UX review sub-agent** to review
screenshots from user perspective. Issues tagged `UI-EXP`.
Skip in smoke mode.
> **Agent template + orchestration:** [`references/phase-5-6-7-ui-audit.md`](./references/phase-5-6-7-ui-audit.md)

---

## Phase 6 — Generate Test Report

After all Area cases (Phase 3/4/5) are run, produce a single test report.
Read the screenshots you captured (Read tool supports images) to confirm each
case's outcome, then write the report.

> **Parallel run merging:** When running in parallel mode (G1 ‖ G3 → G2), each
> agent's output is available in the parent context via the Agent tool. Collect
> pass/fail/skip results from all group agents, merge failures by case ID
> (preserving group prefixes like `G1-C2.3`), and produce a unified report.

> **MANDATORY: The report content MUST appear inline in your final response.**
> Do NOT just say "报告已生成: path". The response itself must contain the
> full report with these three required sections:
> 1. **测试环境** — deployment mode, URLs, driver, health, gate results
> 2. **成功摘要** — pass/fail/skip counts + case ID list
> 3. **失败详情** — per-failure details (or "无失败" if all passed)
>
> Also write the report to a file if the environment allows, but the inline
> content is the primary deliverable.
>
> **Evidence priority:** Use snapshot/AX-tree data captured during test execution
> as the primary assertion evidence (element refs, expected text presence).
> Screenshots are supplementary visual confirmation. For each case, review
> snapshot text before screenshot when determining pass/fail.

> **Report scope:** success summary + failure details + UI quality observations.
> Do NOT include P0–P3 severity grading, effort estimates, or fix plans.
> This skill records test results. If the user wants follow-up fix commits,
> see Phase 7 (OPTIONAL — triggered by "修复" / "fix" / "按分类提交").
>
> **UI quality observations:** When Area 15 (UI quality) is run, include a
> fourth section "UI 质量观察" summarizing design-system findings (dark mode
> defects, touch target violations, viewport overflow, accessibility gaps).
> Use the `UI-*` failure codes from the taxonomy below.
>
> **Case-UI consistency check:** before writing "expected vs actual", verify the
> case's asserted route/label still matches the current source tree. If a case
> asserts `/settings/notification` but the router defines `/settings/notifications`,
> record it as a case defect (not a product bug) and note the correct route in the
> report. Use the same sources that grounded the test-cases (router files, i18n
> keys, API response schemas) to resolve mismatches.

### Output path

```bash
TODAY=$(date +%Y-%m-%d)
REPORT="tests/reports/ui-audit-${TODAY}.md"
# Screenshots already saved during Phase 3/4/5 at:
#   dogfood-output/<case>.png
```

### Report structure

The "测试环境" section consolidates the outcomes of Phase 0 (driver detection),
Phase 1 (service health), and Phase 1.5 (precondition gate) so the report is
self-contained — a reader can reconstruct the run conditions without re-reading
the skill log.

```markdown
# Numina 仿真测试报告 — {YYYY-MM-DD}

## 测试环境 (合并自 Phase 0 / 1 / 1.5)
- 部署模式: docker | dev  (含探测结论, 如 `dev (5173 同源 dev server; docker 亦可用)`)
- Base URL: {BASE}  /  Child URL: {CHILD_BASE}  /  API: {API_BASE}
- Browser driver (Phase 0): {driver_name} ✓ clean
- 服务健康 (Phase 1): adult UP / child UP / api UP  (docker 模式附 docker ps 摘要)
- 前置门禁 (Phase 1.5): ✓ 通过 — demouser (owner) / children {discovered_names} / {N} assets / 负债 {amount}
- 测试时间: {YYYY-MM-DD}
- 截图目录: dogfood-output/

## 成功摘要
- 测试用例总数: N (Area1: C1.1–C1.17, Area2: C2.1–C2.25, Area3: C3.1–C3.23, Area4: C4.0–C4.16, Area5: C5.1–C5.10, Area6: C6.1–C6.27, Area7: R1–R9, Area8: F.1–F.8/F.11/F.12, Area9: C9.1–C9.7, Area10: C10.1–C10.4, Area11: C11.1–C11.20, Area12: C12.1–C12.9, Area13: C13.1–C13.5, Area14: C14.1–C14.40, Area15: UIQ.1–UIQ.10, Area16: C16.1–C16.14, Area17: C17.1–C17.21, Area18: C18.1–C18.24, Area20: M20.1–M20.15)
- 通过: X
- 失败: Y
- 跳过: Z (注明原因, 如 AI 未启用、数据不足)
- 通过用例清单: C1.1, C1.2, C2.1, C2.3, …  (仅列举 case id, 不展开)

## 失败详情

### C2.3 — 心愿详情页 (savings log/record dialogs) `RENDER`
- **路由**: {BASE}wishes/{id}
- **截图**: dogfood-output/c2.3-wish-detail.png
- **预期表现**: 点击"记录储蓄"按钮弹出 WishSavingsRecordDialog, 含金额输入框
- **当前错误表现**: 点击后无反应, 控制台报 `Cannot read property 'open' of undefined`
- **初步判断**: WishSavingsRecordDialog 组件未挂载或 ref 未绑定; 需检查 WishDetailPage 模板中 dialog 的 v-model:show 绑定

### C3.4 — AI 资产报告生成 `AI`
- **路由**: {BASE}ai/report
- **截图**: dogfood-output/c3.4-ai-report.png
- **预期表现**: 3 步时间轴逐步 pending→running→done, 最终显示评分+摘要
- **当前错误表现**: step1 卡在 running 超过 60s, 无后续推进
- **初步判断**: 后端 stream 未返回终结帧, 或 worker agent 调用 LLM 超时; 建议查 agent 日志确认是否触达 LLM

### {C-x.x} — {case 标题}
- … (同结构)

## 跳过用例 (如有)
- C3.x — 原因: AI 未启用 (family aiEnabled=false), 建议在 /settings/ai 配置 provider 后补测

## UI 质量观察 (Area 15 — 仅当运行 ui-quality 模式或全量测试时)
- 深色模式: {N} 项缺陷 (列出 UI-DARK 用例)
- 触摸目标: {N} 项违规 (列出 UI-TOUCH 用例)
- 视口溢出: {N} 项 (列出 UI-OVERFLOW 用例)
- 无障碍: {N} 项 (列出 UI-A11Y 用例)
- 跨应用一致性: {通过/不通过} (UIQ.10 结论)
```

### Writing rules

- **测试环境段必须填实**（合并前文）：driver detection 结果、三服务健康、gate 的 demouser/资产数/孩子名都从 Phase 0/1/1.5 的实际输出抄入，不要留 `{id}`/`{N}` 占位符。不要包含 family_id 等内部 snowflake ID。这保证报告可独立追溯。
- **成功用例只进摘要清单**(case id 罗列), 不展开详情 —— 避免报告冗长。
- **每个失败用例必须有三段**: 预期表现 / 当前错误表现 / 初步判断。缺少任一段视为记录不完整。
- **初步判断**是基于截图 + 控制台错误 + 路由行为的推断, 不要求定位到根因; 写明"建议查 X"即可, 不展开修复方案。
- **截图路径**用相对仓库根的路径, 便于用户点击查看。
- 失败用例按 Area 顺序 (Area1 → Area2 → … → Area15) 再按 case id 排列。

### Failure taxonomy (失败分类)

每个失败用例在"初步判断"前标注分类代码，便于统计和趋势跟踪:

| 代码 | 含义 | 典型场景 |
|------|------|----------|
| `RENDER` | 渲染错误 | 组件未挂载、空白页、NaN/undefined |
| `NAV` | 导航/路由错误 | 404、route guard 错误跳转、activeTab 不对 |
| `AUTH` | 认证/权限错误 | 401/403、session 丢失、角色越权 |
| `DATA` | 数据/显示错误 | 金额精度丢失、双符号、空态缺失 |
| `I18N` | 国际化错误 | key 泄露、翻译缺失、语言切换崩溃 |
| `AI` | AI 功能错误 | stream 卡住、空白响应、report 生成失败 |
| `INTERACT` | 交互错误 | 按钮无响应、表单验证失效、dialog 不弹出 |
| `PERF` | 性能问题 | 页面加载超时、动画卡顿 |
| `REGRESS` | 回归 (已知 bug 重现) | Area 7 用例失败自动标此分类 |
| `SKIP-INFRA` | 基础设施故障 | 浏览器驱动崩溃、driver daemon 断开、MCP 服务器不可用 |
| `UI-OVERFLOW` | 视口溢出 | 375px 宽度出现水平滚动条 |
| `UI-DARK` | 深色模式缺陷 | inline style 未翻转, 文字不可读 |
| `UI-CONTRAST` | 对比度不足 | 文字在任一模式下不满足 WCAG AA (4.5:1) |
| `UI-TOUCH` | 触摸目标过小 | 交互元素 < 44×44px |
| `UI-SAFE` | 安全区域违规 | Tab bar 被 home indicator 遮挡 |
| `UI-PWA` | PWA 缺陷 | 无离线提示, SW 未注册 |
| `UI-A11Y` | 无障碍缺陷 | 缺少 aria-label, 无焦点环 |
| `UI-VANT` | Vant4 规范违反 | `:value` 替代 `:model-value`, popup 缺少 teleport |
| `UI-CONSIST` | 跨应用不一致 | 两个 app 的空态/骨架屏/Toast 风格不同 |
| `UI-PROGRESS` | NProgress 回归 | 闪烁 / 卡住 / 滚动后不可见 |
| `UI-EXP` | 体验审查发现 (Phase 5.7) | 输入输出正确但存在错位/图标丢失/交互不连贯等体验缺陷 |

### After writing

Your final response MUST contain the full report inline. Use this structure:

```markdown
# Numina 仿真测试报告 — {YYYY-MM-DD}

## 测试环境
- 部署模式: docker | dev
- Browser driver: {browser-use|bsk|chrome-devtools}
- 服务健康: adult UP / child UP / api UP
- 前置门禁: ✓ 通过 — {demouser info}

## 成功摘要
- 通过: X / 失败: Y / 跳过: Z (共 N)
- 通过用例: C2.1, C2.2, ...

## 失败详情
(如无失败, 写 "无失败, 全部通过。")

### {Case ID} — {标题} `{分类}`
- 路由: ...
- 截图: ...
- 预期表现: ...
- 当前错误表现: ...
- 初步判断: ...
```

Also write to file if possible: `tests/reports/ui-audit-{date}.md`

> 如需跟进修复, 说 "修复" 或 "按分类提交" 进入 Phase 7.

---

## Phase 7 — Checklist Todo + Categorized Fix Commits (OPTIONAL)

> **Trigger:** User says "修复" / "fix" / "按分类提交" after Phase 6 report.
> Default: do NOT execute — only records results.

Extract failures from report → categorize → create checklist → fix by
category → commit per category → verify each fix → final summary.

**Dev mode:** check `server/.dev-logs/*-app.log` in failure time window
(±5 min) for server-side error correlation.
**Docker mode:** `docker logs numina-backend --since 10m` equivalent.

> **Full fix workflow:** [`references/phase-7-fix-workflow.md`](./references/phase-7-fix-workflow.md)

---

## Quick Reference

```bash
# === Pick deployment mode first (see "Deployment Mode" section) ===
# docker: export BASE=http://localhost/ CHILD_BASE=http://localhost/child/ API_BASE=http://localhost/api/v1
# dev:    export BASE=http://localhost:5173/ CHILD_BASE=http://localhost:5174/child/ API_BASE=http://localhost:8000/api/v1

# Phase 0 — detect browser driver (browser-use → bsk → chrome-devtools MCP)
# See Phase 0 section for detection script

# Phase 1 — service health (both modes)
curl -sf "$BASE" -o /dev/null && echo "adult UP"
curl -sf "$CHILD_BASE" -o /dev/null && echo "child UP"
curl -sf "${API_BASE%/v1}/health" -o /dev/null && echo "api UP"
# docker only: docker ps --format "{{.Names}}\t{{.Status}}" | grep numina

# Browser interaction — driver-specific commands in references/browser-drivers.md
# Common pattern: navigate → snapshot → interact → re-snapshot → screenshot

# Rebuild after code changes
# docker: docker-compose build frontend && docker-compose up -d frontend   (or frontend-child)
# dev:    no rebuild (vite HMR); verify via cd frontend/apps/main && pnpm typecheck

# Test accounts (must pre-exist in DB — this skill does NOT seed them)
# demouser family: child display_names DISCOVERED at gate time (Phase 1.5)
#   docker seed default: 小宝 / 大宝  (PIN per test-cases/_common.md)
#   dev/other deployments may differ (e.g. demochild, 小明) — gate reads actual names
# test_rich family: test_child (testchild / 🐱🐶🌟🌈)
```

## Test Case Index

| Area | Group | Cases | File |
|------|-------|-------|------|
| 1 — Child app (儿童页面) | G3 | C1.1–C1.17 | [`test-cases/groups/g3-child/area1-child.md`](./test-cases/groups/g3-child/area1-child.md) |
| 2 — Financial management (财务管理) | G1 | C2.1–C2.25 | [`test-cases/groups/g1-adult-stable/area2-finance.md`](./test-cases/groups/g1-adult-stable/area2-finance.md) |
| 3 — AI (PDF/报告/数鸣/对话) | G1 | C3.1–C3.23 | [`test-cases/groups/g1-adult-stable/area3-ai.md`](./test-cases/groups/g1-adult-stable/area3-ai.md) |
| 4 — Main app nav coverage (页签+币种切换) | G2 | C4.0–C4.16 | [`test-cases/groups/g2-adult-currency/area4-navigation.md`](./test-cases/groups/g2-adult-currency/area4-navigation.md) |
| 5 — Child app nav coverage (页签+子页面) | G3 | C5.1–C5.10 | [`test-cases/groups/g3-child/area5-child-navigation.md`](./test-cases/groups/g3-child/area5-child-navigation.md) |
| 6 — AI chat DeerFlow parity (输入/输出/集成+设计出入) | G1 | C6.1–C6.27 (D1–D7) | [`test-cases/groups/g1-adult-stable/area6-ai-chat-parity.md`](./test-cases/groups/g1-adult-stable/area6-ai-chat-parity.md) |
| **7 — Regression sweep (历史缺陷回归)** | **G1** | **R1–R9** | [`test-cases/groups/g1-adult-stable/area7-regression.md`](./test-cases/groups/g1-adult-stable/area7-regression.md) |
| **8 — Expanded coverage (Manifesto/盲盒/Baby/Settings/Gift)** | **G1** | **F.1–F.8, F.11, F.12** | [`test-cases/groups/g1-adult-stable/area8-expanded-features.md`](./test-cases/groups/g1-adult-stable/area8-expanded-features.md) |
| **9 — Security + notification (WebAuthn/2FA/通知)** | **G1** | **C9.1–C9.7** | [`test-cases/groups/g1-adult-stable/area9-security-notification.md`](./test-cases/groups/g1-adult-stable/area9-security-notification.md) |
| **10 — Guest 端到端 (注册/邀请码/加入家庭)** | **G1** | **C10.1–C10.4** | [`test-cases/groups/g1-adult-stable/area10-guest-join-flow.md`](./test-cases/groups/g1-adult-stable/area10-guest-join-flow.md) |
| **11 — AI/agent adversarial security (提示词注入/租户隔离/越权)** | **G1** | **C11.1–C11.20** | [`test-cases/groups/g1-adult-stable/area11-ai-security-adversarial.md`](./test-cases/groups/g1-adult-stable/area11-ai-security-adversarial.md) |
| **12 — AI task resilience (前端不稳定处理)** | **G1** | **C12.1–C12.9** | [`test-cases/groups/g1-adult-stable/area12-ai-task-resilience.md`](./test-cases/groups/g1-adult-stable/area12-ai-task-resilience.md) |
| **13 — AI 资产报告深度验证 (Hub 弹窗/重入去重/SSE 重连)** | **G1** | **C13.1–C13.5** | [`test-cases/groups/g1-adult-stable/area13-ai-asset-report-deep.md`](./test-cases/groups/g1-adult-stable/area13-ai-asset-report-deep.md) |
| **14 — Travel core (行程/费用/分摊/转化/Dashboard)** | **G1** | **C14.1–C14.22** | [`test-cases/groups/g1-adult-stable/area14-travel.md`](./test-cases/groups/g1-adult-stable/area14-travel.md) |
| **14b — Itinerary planning (行程规划/跨天/购买日期)** | **G1** | **C14.23–C14.40** | [`test-cases/groups/g1-adult-stable/area14-itinerary.md`](./test-cases/groups/g1-adult-stable/area14-itinerary.md) |
| **15 — UI quality & design system (H5/PWA/深色模式/无障碍/一致性)** | **G1** | **UIQ.1–UIQ.10** | [`test-cases/groups/g1-adult-stable/area15-ui-quality.md`](./test-cases/groups/g1-adult-stable/area15-ui-quality.md) |
| **16 — Learning OS taxonomy Beijing (课标徽章/边标/locale)** | **G3** | **C16.1–C16.14** | [`test-cases/groups/g3-child/area16-learning-os-taxonomy.md`](./test-cases/groups/g3-child/area16-learning-os-taxonomy.md) |
| **17 — Learning OS core flows (child: 知识地图/Topic/AI 导师/进度/自选学习)** | **G3** | **C17.1–C17.21** | [`test-cases/groups/g3-child/area17-learning-os-core.md`](./test-cases/groups/g3-child/area17-learning-os-core.md) |
| **18 — Learning OS 家长端 + 端到端闭环 (Hub/推荐/路径/DNA/双轨审核/闭环)** | **G1** | **C18.1–C18.24** | [`test-cases/groups/g1-adult-stable/area18-learning-os.md`](./test-cases/groups/g1-adult-stable/area18-learning-os.md) |
| **20 — MCP external API token & governance (Token 生命周期/认证/审计/速率限制)** | **G1** | **M20.1–M20.15** | [`test-cases/groups/g1-adult-stable/area20-mcp-external-token.md`](./test-cases/groups/g1-adult-stable/area20-mcp-external-token.md) |

### Supporting References

| File | Purpose |
|------|---------|
| [`references/browser-drivers.md`](./references/browser-drivers.md) | Browser driver detection + command reference (browser-use / bsk / Chrome DevTools MCP) |
| [`references/ui-quality-checklist.md`](./references/ui-quality-checklist.md) | UI quality reference: design tokens, dark mode methodology, Vant4 patterns, accessibility checklist, cross-app consistency matrix |
| [`references/phase-1-5-gate.md`](./references/phase-1-5-gate.md) | Precondition gate bash script (login, family, assets, AI, child auth checks) |
| [`references/phase-5-6-7-ui-audit.md`](./references/phase-5-6-7-ui-audit.md) | UI audit case details (UIQ.1–10) + UX review agent template + orchestration rules |
| [`references/phase-7-fix-workflow.md`](./references/phase-7-fix-workflow.md) | Fix workflow: dev-logs correlation, checklist generation, categorized commits |
| [`test-cases/_common.md`](./test-cases/_common.md) | Shared conventions (session, refs, console capture, child injection) |
| [`test-cases/role-capabilities.md`](./test-cases/role-capabilities.md) | Role capability matrix (owner/member/child 权限边界 + 页面清单) |
| [`test-cases/groups/README.md`](./test-cases/groups/README.md) | Parallel run structure + state-isolation boundaries |

## Browser Red Lines (all drivers)

1. **No token theft** — never evaluate JS on sensitive sites to read `localStorage`/cookies/auth headers for exfiltration.
2. **No long borrow** — don't leave tabs/sessions open across unrelated tasks.
3. **No skip cleanup** — always close tabs / stop sessions when done; never assume idle timeout cleans up.
4. **Snapshot first** — observe via accessibility tree / snapshot before escalating to screenshot or raw HTML.
5. **JS evaluation is risky** — use only when snapshot + click/fill cannot suffice; never on credential surfaces.
6. **No credential logging** — never echo passwords, tokens, or API keys in command output. Use environment variables for credentials and redact sensitive values in error messages.
7. **No sensitive data in reports** — test reports must not contain tokens, internal IDs (family_id, user_id snowflake IDs), or credential values. Reports are for test result tracking, not identity documentation.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Skipping Phase 0 driver detection → browser commands fail | Always run Phase 0 first; do not proceed until a driver is confirmed working |
| Skipping Phase 1.5 gate → UI assertions fail on absent data, misread as bugs | Always run the precondition gate; if it blocks, seed the DB out-of-band before retrying |
| Using stale element refs after navigation → click misses | Re-snapshot on every new page / after DOM-changing click (all drivers) |
| Assuming click opens file picker for `<input type=file>` | It doesn't — see test-cases/_common.md "File upload note" |
| Relying on idle timeout to clean up | Always close/stop the session explicitly when done |
| Treating 401 auth-refresh as a bug | Expected on first load — filter from console errors |
| Treating child `/child/blind-box` 404 as a bug | It redirects to `/treasures` (route alias) — that's correct |
| Docker child page shows blank / redirects to adult login | Adult `access_token` cookie interferes with child SPA route guard. Clear cookies + localStorage before child testing in docker mode — see area1-child.md "Docker mode — cookie clearing required" |
| Navigating to `${BASE}wishes` / `${BASE}assets` / `${BASE}liabilities` → unexpected redirect | U6: these routes redirect to `${BASE}finance?tab=wishes\|assets\|liabilities`. Use the FinanceHub tab routes in test cases |
| Password-manager extension hijacks the tab on password field fill | Do not retry the fill. Use the Phase 2 cookie+localStorage injection fallback — no password field is focused, so the extension never activates |
| Screenshots are desktop-width, not mobile 375×812 | Note the viewport in the report; mobile-specific layout (Tab bar density, horizontal scroll) may not be validated depending on driver viewport support |
| Click registers but doesn't navigate (desktop-width coordinate offset hits a child element) | Prefer navigating directly to the target route via an id from the API (`/api/v1/wishes` → `/wishes/:id`) instead of clicking a list item in a wide viewport |
| Running Area 7 R6 (auth expiry) before other cases → breaks remaining session | Run R6 as the **very last** regression case; it clears localStorage and destroys the session |
| Testing Baby tab / family settings as non-owner → 403 | `demouser` is owner by default — these work. For member-role testing, see Area 8 F.8 (deferred: requires separate member account) |
| Manifesto wizard state lost between pages | `useManifestoWizard` persists via `sessionStorage` — do not clear storage mid-flow; the wizard state resets only on explicit cancel |
| Smoke mode accidentally running full suite | Smoke mode runs only 10 cases (C2.1, C2.2, C2.5, C2.8, C3.1, C3.2, C4.0, R1, R2, C9.4). Verify the mode before starting |
| Guest pages tested with authenticated session → redirected past welcome | Use a **fresh browser session** without cookies for F.5.x guest page tests |
| Area 15 dark mode test: toggling via CSS instead of app setting | Must toggle via the app's Settings → Appearance (or `van-config-provider` theme prop), not by manually setting `data-theme` — the app's JS controls `van-config-provider` which cascades Vant component themes |
| Area 15 touch target check: measuring visual size instead of tap area | `getBoundingClientRect()` on the element returns the visual box; the tap area may be larger due to padding on parent. Check `pointer-events` area, not just icon size |
| Area 15 viewport test at desktop width → misses all mobile issues | Set viewport to 375×812 BEFORE running UIQ cases. If driver doesn't support resize, note in report and skip viewport-dependent checks |
| Area 15 cross-app consistency: comparing main vs child screenshots at different widths | Both apps must be at the same viewport (375×812) for valid comparison. Child app has different design tokens (Clay vs Together AI) — compare pattern consistency, not pixel identity |
| Phase 0 chrome-devtools detection sets driver without verifying MCP availability | The agent must self-check its tool list for `mcp__chrome-devtools__*` tools and set `MCP_CHROME_DEVTOOLS=1` BEFORE running the detection script. The bash fallback `command -v echo` always succeeds and would set the driver unconditionally |
| Choosing docker mode just because `docker ps` shows containers Up | nginx may be in a restart loop with :80 dead (verified 2026-10-14). Docker-mode eligibility = `curl -sf http://localhost/` 200, nothing else |
| Dev-mode probe matches a 5173 from a DIFFERENT repo/worktree | cwd check must be under `git rev-parse --show-toplevel` of the current repo — a vite from another checkout answers on 5173 but tests the wrong code |
| Phase 7 fix loop in dev mode skips `.dev-logs` | Before localizing a fix, grep `server/.dev-logs/*-app.log` in the failure time window (±5 min); empty/missing dir = LOG=0 was on, note it, don't treat as test failure |

### bsk-specific Mistakes (only when bsk is the active driver)

| Mistake | Fix |
|---------|-----|
| Forgetting `--session <id>` → "unknown session" error | Every command after `session start` needs `--session` |
| `bsk wait-ms 2s` / `1500` rejected with a duration parse error | `wait-ms` accepts a narrow set of duration forms; if rejected, drop the wait and use `--wait-until` on the next `navigate`, or poll snapshot until the expected text appears |
| `bsk navigate` RPC times out at 30s but the page actually loaded | Navigation often completes before the RPC returns. Do not retry blindly — verify with `evaluate "location.href"`; if correct, proceed to `snapshot` |
| `bsk click` on form submit / picker items doesn't trigger Vue handler | Protocol drift (ext 1.3 vs daemon 1.0) breaks synthetic click events on some elements. Use `bsk evaluate` with `element.dispatchEvent(new MouseEvent('click', {bubbles:true}))` or `element.click()` as fallback. **This is a bsk limitation, NOT a product bug** — real touch events work correctly |
| `bsk snapshot` shows `` for `van-icon` elements | The a11y tree represents `van-icon` components as `` (private Unicode area). This is a snapshot artifact — verify icon rendering via `bsk screenshot` instead. Do NOT file icon bugs based on snapshot text alone |
| Vite proxy returns 404 for new API endpoints in dev mode | `vite.config.ts` may use `process.env.VITE_API_TARGET` which doesn't load `.env.development`. Must use `loadEnv(mode, process.cwd(), '')` to read env files in config. If itinerary/similar new routes 404 through proxy but work on direct backend, check proxy target — may be forwarding to stale port 80 instead of port 8000 |
