# Numina Simulation Test Cases — Shared Conventions

Shared conventions used by all area case files:
- [`area1-child.md`](./area1-child.md) — Child app (儿童页面优化)
- [`area2-finance.md`](./area2-finance.md) — Main app financial management (财务管理能力优化)
- [`area3-ai.md`](./area3-ai.md) — AI capabilities (PDF/AI报告/数鸣/对话)
- [`area4-navigation.md`](./area4-navigation.md) — Main app nav coverage (页签+子页面+币种切换)
- [`area5-child-navigation.md`](./area5-child-navigation.md) — Child app nav coverage (页签+子页面)
- [`area6-ai-chat-parity.md`](./area6-ai-chat-parity.md) — AI chat DeerFlow-fidelity parity (输入/输出/集成+设计出入 D1–D7)
- [`area7-regression.md`](./area7-regression.md) — Regression sweep (历史缺陷回归 R1–R9)
- [`area8-expanded-features.md`](./area8-expanded-features.md) — Expanded coverage (Manifesto/盲盒/Baby/Settings/Guest F.1–F.8)

**角色能力矩阵 (Role Capabilities Matrix):** [`role-capabilities.md`](./role-capabilities.md)
— 每个角色 (owner/member/child) 的权限边界和可见页面清单。

## Case conventions

- `<id>` = the 4-letter session id from `bsk session start`
- `@eN` refs come from the **latest** `bsk snapshot`; they invalidate on
  navigation — always re-snapshot before clicking/filling a new page.
- `demouser` / `DemoPass123` is the adult demo account. Child display_names
  under it are **discovered at gate time** (Phase 1.5 reads `/family/members`
  where `role=="child"`) — they are NOT hard-coded. Docker seed default:
  小宝 (`xiaobao`) + 大宝 (`dabao`), PIN `🌟🌈`. Dev/other deployments may
  differ (e.g. `demochild`, 小明); always use the names the gate printed, not
  a fixed string. See "Child account names" below.
- Assertions marked `[console]` are checked via `bsk evaluate` reading
  `window.__consoleErrors` (see "Console error capture" below) — or by
  watching stderr from the prior command.
- `${BASE}` / `${CHILD_BASE}` / `${API_BASE}` are set per deployment mode —
  see `../SKILL.md` "Deployment Mode". Routes are the same in every mode;
  only the host:port differs.

## Prerequisite data (must pre-exist in DB; this skill does NOT seed it)

`demouser` family must contain: **at least 1 child member** (any
`display_name` — the gate discovers it, see "Child account names" below),
plus assets/liabilities/wishes matching the per-case assertions. Run
`tests/data/seed-data.sh` out-of-band if missing — do NOT seed from this
skill. The Phase 1.5 gate verifies presence (≥1 child + assets>0) before
any case runs.

## Child account names

Child `display_name`s are **not fixed** — they are discovered at gate time
(Phase 1.5) by filtering `/family/members` for `role=="child"`. The gate
prints the discovered names and exports `SIM_CHILD_NAMES` (comma-joined)
for downstream phases and the report.

- When a case needs to refer to a specific child (e.g. "click the 小宝 card"
  in C1.2's ChildSelectPage), use the **first discovered child name** unless
  the case's prerequisite data specifies otherwise. Snapshot the select
  page and click the actual card `@eN` ref — do not hard-code the name in
  a `bsk fill`/assertion string.
- Docker seed default names (小宝, 大宝) appear in this file and in
  `area1-child.md` only as **examples** of what the docker deployment
  produces; dev/other deployments (demochild, 小明, …) are equally valid and
  must not cause a gate failure.

## Grounding

Every route and component referenced in the area files is verified against the
actual source tree on branch `feat/two-ai-apps-unified-dispatch`:

- **Child routes** (`frontend/apps/child/src/router/index.ts`): `/` (ChildHome),
  `tasks`, `ledger`, `wishes`, `wishes/new`, `wishes/:id`, `assets/:id`,
  `treasures`, `blind-box` (→ redirect `/treasures`), `calendar/day`, `settings`,
  `scenario`, `badges`, `manifesto/sign`.
- **Child components**: `components/celebration/` (FlyToTarget, CandleFlame);
  `components/wishes/` (WishConstellationGrid, WishConstellationCard); `composables/`
  (useHaptic, useReducedMotion); `@numina/math` (daysEstimate, previewSpend, reachabilityTint).
- **Main routes** (`frontend/apps/main/src/router/index.ts`): `/` (Dashboard),
  `finance` (FinanceHub — unified assets/liabilities/wishes via `?tab=` query),
  `finance?tab=assets`, `finance?tab=liabilities`, `finance?tab=wishes`,
  `assets` (→ redirect `finance?tab=assets`), `liabilities` (→ redirect `finance?tab=liabilities`),
  `wishes` (→ redirect `finance?tab=wishes`),
  `assets/new`, `assets/:id`, `assets/:id/edit`, `assets/:id/sell`,
  `liabilities/new`, `liabilities/:id`, `liabilities/:id/edit`,
  `wishes/new`, `wishes/:id`, `wishes/:id/edit`,
  `ai` (AIHub), `ai/chat`, `ai/report`,
  `ai/time-machine`, `settings/ai`, `settings/import-report`,
  `manifesto/template-select`, `manifesto/edit`, `manifesto/sign`, `manifesto/preview`,
  `blind-box/draws`, `blind-box/gifts`, `blind-box/gifts/new`, `blind-box/config`,
  `baby`, `baby/calendar/day`, `baby/chores/new`, `baby/chore-templates`,
  `baby/literacy-report`, `family/chore-approvals`,
  `settings/notifications`, `settings/password`, `settings/second-factor`,
  `settings/devices`, `settings/family/config`, `settings/family/coin-rates`,
  `settings/family/debt-thresholds`, `settings/family/manifesto`, `settings/user/config`,
  `welcome`, `register`, `join-family`, `promo/family`, `promo/developer`.
- **Main components**: `components/wishes/` (WishSavingsProgress, WishSavingsLogDialog,
  WishSavingsRecordDialog, WishAdviceCard, WishCostEditDialog, StarCoinSuggestion);
  `components/liability/` (LiabilityStrategyCard, InterestForecast,
  SimulateExtraDialog, PaymentCountdown, LiabilityCard, LiabilityForm);
  `components/dashboard/FinanceCoachCard.vue`; `composables/` (useAffordBar, useDebtWarning);
  `components/ai/AIChatBox.vue`; `components/ai-chat/InputBox.vue`.
- **AI skills** (`server/apps/agent/skills/builtin/public/`): `asset-report`,
  `import-parse`, `chat`, `chat-search`.

## Console error capture

`bsk` has no built-in console-message lister. Capture errors with a one-shot
evaluate at page load:

```bash
# Inject a console error collector, then check it after interactions
bsk evaluate --session <id> --expr "window.__consoleErrors = []; window.addEventListener('error', e => window.__consoleErrors.push(e.message)); const oe = console.error; console.error = (...a) => { window.__consoleErrors.push(a.join(' ')); oe(...a); }; 'installed'"
# ... run the case ...
bsk evaluate --session <id> --expr "JSON.stringify(window.__consoleErrors || [])"
```

Filter out expected 401 auth-refresh messages — those are not bugs.

## Child session injection (dev mode — password-manager fallback)

In **dev mode** the child app (`:5174`) is a separate origin from the adult
app (`:5173`), so the adult httpOnly cookie does NOT carry over, and the child
two-step emoji-PIN login (`/auth/login/step1` → `/auth/login/step2`) must be
driven from the child origin's page context. This is the dev-mode analog of
the adult cookie+localStorage injection in SKILL.md "Phase 2 fallback".

The child PIN is **not always known** for dev/other deployments (docker seed
defaults `🌟🌈` for 小宝/大宝; dev may use `demochild`/小明 with a different
or unknown PIN). If the PIN is unknown, reset it out-of-band via sqlite
before this step (bcrypt hash, NFC-normalized joined emoji sequence) — this
skill does not reset credentials.

```bash
# 1) Navigate to the child origin. wait-until domcontentloaded (NOT networkidle)
#    — the child SPA guard redirects to the adult login before any child
#    session exists, so networkidle never settles. domcontentloaded gives a
#    window to inject before the guard runs.
bsk navigate "$CHILD_BASE" --session "$SID_CHILD" --wait-until domcontentloaded

# 2) step1: username + password → temp_token (second_factor_type: 'emoji_pin')
bsk evaluate --session "$SID_CHILD" "(async () => {
  const r = await fetch('/api/v1/auth/login/step1', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    credentials: 'include',
    body: JSON.stringify({username:'<child_user>', password:'<child_pass>'}),
  });
  const j = await r.json();
  window.__tempToken = j.data.temp_token;
  return String(r.status);
})()"

# 3) step2: temp_token + factor_type + payload.pin_sequence (emoji array, IN ORDER)
#    → server set_child_auth_cookies writes child_access_token httpOnly cookie.
#    EmojiPinStrategy.verify NFC-normalizes ''.join(pin_sequence) then bcrypt-checks.
bsk evaluate --session "$SID_CHILD" "(async () => {
  const r = await fetch('/api/v1/auth/login/step2', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    credentials: 'include',
    body: JSON.stringify({
      temp_token: window.__tempToken,
      factor_type: 'emoji_pin',
      payload: { pin_sequence: ['🐱','🐶','🌟','🌈'] },
    }),
  });
  return String(r.status);
})()"

# 4) Populate localStorage so the child SPA guard fast-path
#    (cachedUser?.role === 'child') admits without a fetch. Fetch /auth/me
#    for the non-sensitive fields.
bsk evaluate --session "$SID_CHILD" "(async () => {
  const r = await fetch('/api/v1/auth/me', {credentials: 'include'});
  const u = (await r.json()).data;
  localStorage.setItem('numina_user', JSON.stringify({
    id: String(u.id), username: u.username, display_name: u.display_name,
    avatar_color: u.avatar_color, role: u.role, theme: u.theme,
    language: u.language, default_currency: u.default_currency,
  }));
  return u.role;
})()"

# 5) Reload — guard re-reads localStorage, fast-path admits, child app renders.
bsk navigate "$CHILD_BASE" --session "$SID_CHILD" --wait-until domcontentloaded
bsk snapshot --session "$SID_CHILD"     # confirm ChildHome rendered (not redirect)
```

**Schema note:** `LoginStep2Request` is `{ temp_token: str, factor_type: str,
payload: dict }` — the PIN goes in `payload.pin_sequence` (an emoji array),
**not** a top-level `pin` field. Sending `{pin: "..."}` returns
`VALIDATION_ERROR`.

**Cleanliness:** same as the adult fallback — `fetch` drives the app's own
login endpoints; the httpOnly cookie is set by the server's `Set-Cookie`
header, not by JS. No token is exfiltrated.

## File upload note (Area 3 — C3.5 PDF import)
`bsk click` on a `<van-uploader>` wrapper does not open the OS file picker
(headless Agent Window). Two options:
1. `bsk evaluate` to set `input.files` via a `DataTransfer` object (requires
   the file bytes reachable from the page context — usually via a fetch to a
   served test fixture).
2. Test the parse + preview + confirm flow by calling the backend parse
   endpoint directly with `curl` (bypassing the upload UI), then load the
   preview page with the returned parse token.

Prefer option 2 for CI-style runs; use option 1 only for manual UI validation.
