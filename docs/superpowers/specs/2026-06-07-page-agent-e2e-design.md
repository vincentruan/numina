# PageAgent E2E Testing — Design Spec

**Date:** 2026-06-07  
**Status:** Draft  
**Scope:** Introduce Alibaba PageAgent as a semantic DOM interaction layer for E2E testing in the Numina monorepo, complementing the existing `numina-sim-test` visual audit skill.

---

## 1. Problem Statement

Current E2E testing relies on either:
- **Playwright locators** — brittle when UI changes, requires manual selector maintenance
- **Screenshot + AI vision** (via `numina-sim-test`) — slow, high token cost (~10-50x more tokens than text), requires multimodal models

Neither approach provides **semantic DOM-based interaction** that understands page content through text structure rather than visual rendering.

### Goals

1. Enable AI-driven E2E flows that read text DOM directly — no screenshots, no OCR
2. Reduce token consumption by 10-50x compared to screenshot-based approaches
3. Support multi-page, multi-form workflows (login → CRUD → approval → verification)
4. Maintain deterministic assertions — never trust LLM "success" claims alone
5. Integrate as a complement to `numina-sim-test` (visual audit still uses screenshots when genuinely needed)
6. Work in CI, local development, and Claude Code debugging contexts

### Non-Goals

- Replacing unit tests (pytest, vitest stay as-is)
- Replacing stable Playwright locator tests that already work
- Visual regression testing (stays with numina-sim-test)
- Performance/load testing

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Code Skill: page-agent-e2e                           │
│  (.claude/skills/page-agent-e2e/SKILL.md)                   │
│  Triggers: e2e, PageAgent, semantic test, Vue E2E, etc.      │
└──────────────────────────┬──────────────────────────────────┘
                           │ invokes
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Runner: scripts/page-agent-e2e/page-agent-runner.ts         │
│  1. Reads YAML tasks from tests/tools/page-agent/*.yaml       │
│  2. Validates schema (Zod)                                   │
│  3. Launches Playwright Chromium (headless)                  │
│  4. Injects PageAgent into page context                      │
│  5. Executes natural-language tasks via PageAgent            │
│  6. Collects: history, token usage, console, network         │
│  7. Runs deterministic assertions (locator, URL, API, DB)    │
│  8. Outputs JSON + Markdown report                           │
│  9. Appends JSONL to run.log                                 │
└───────────┬─────────────────────────────┬───────────────────┘
            │                             │
            ▼                             ▼
┌────────────────────┐      ┌──────────────────────────────┐
│  PageAgent (npm)   │      │  Playwright (browser shell)   │
│  - Reads text DOM  │      │  - chromium.launch()          │
│  - LLM reasoning   │      │  - page.goto(route)           │
│  - click/type/     │      │  - console message capture    │
│    scroll/select   │      │  - network request capture    │
│  - No screenshots  │      │  - locator assertions         │
└────────────────────┘      └──────────────────────────────┘
            │
            ▼ LLM API (provider-agnostic)
┌──────────────────────────────────────────┐
│  PAGE_AGENT_LLM_BASE_URL                  │
│  PAGE_AGENT_LLM_MODEL                     │
│  PAGE_AGENT_LLM_API_KEY                   │
└──────────────────────────────────────────┘
```

### Relationship with numina-sim-test

| Concern | page-agent-e2e | numina-sim-test |
|---------|---------------|-----------------|
| Semantic interaction (login, forms, navigation) | Primary | Delegates to page-agent-e2e |
| Visual/UI audit (layout, colors, spacing) | Not used | Primary (screenshots + Chrome DevTools) |
| Deterministic assertions | Built-in | API/DB checks in acceptance.sh |
| Token cost | Low (text DOM only) | High (screenshots → multimodal) |
| CI suitability | Fast, cheap | Slower, optional visual phase |

A typical combined flow:
1. `page-agent-e2e` completes the semantic workflow (login → create asset → verify)
2. `numina-sim-test` takes a final screenshot for visual audit if needed
3. Both produce reports that can be combined

---

## 3. File Layout

```
.claude/skills/page-agent-e2e/
├── SKILL.md                              # Trigger rules + constraints (concise)
├── .env                                  # Local config (gitignored) — LLM keys, URLs, test creds
├── .env.example                          # Template with all supported vars (committed)
├── .gitignore                            # Ignores .env, never commit secrets
├── references/
│   ├── page-agent-e2e-architecture.md    # Full architecture (this doc, condensed)
│   ├── task-yaml-schema.md               # YAML schema reference + examples
│   ├── security-and-ci.md                # CI rules, secret handling, safe defaults
│   ├── project-gotchas.md                # 5+ real project-specific gotchas
│   ├── product-verification.md           # Verification requirements + commands
│   └── hooks-and-memory.md               # Safety hooks, /careful rules, log format
└── examples/
    └── smoke.yaml                        # Example smoke case (mirrors tests/tools/page-agent/smoke.yaml)

scripts/page-agent-e2e/
├── README.md                             # Setup + usage instructions
├── .env                                  # Runner-local overrides (optional, gitignored)
├── .gitignore                            # Ignores .env
├── page-agent-runner.ts                  # Main orchestrator
├── page-agent-injector.ts                # PageAgent browser injection
├── task-schema.ts                        # Zod schema + CLI validator
├── report.ts                             # JSON + Markdown report generator
├── start-services.ts                     # Optional service launcher
├── fixtures.ts                           # Test data seed interface
├── verify-smoke.ts                       # Verification script
├── tsconfig.json                         # TypeScript config (tsx runner)
└── package.json                          # Dependencies (playwright, page-agent, yaml, zod, tsx)

tests/tools/page-agent/
├── smoke.yaml                            # Primary smoke test cases
└── tasks.example.yaml                    # Template for new cases

logs/page-agent-e2e/
└── run.log                               # Append-only JSONL (gitignored except .gitkeep)

reports/page-agent-e2e/                   # Generated reports (gitignored)
└── <timestamp>.{json,md}

docs/page-agent-e2e-ci.md                 # CI integration guide
```

---

## 4. YAML Test Case Schema

```yaml
cases:
  - id: string                    # Unique case identifier
    app: string                   # "main" | "child" — which Vue app
    description: string           # Human-readable purpose (optional)
    baseUrl: string               # Override base URL (optional, default from env)
    route: string                 # Path to navigate to (e.g., /login, /assets)
    task: |                       # Natural-language instruction for PageAgent
      Multi-line business-language task description.
      PageAgent will read text DOM and execute this.
    maxSteps: number              # Max PageAgent actions (default: 20)
    timeoutMs: number             # Per-case timeout (default: 30000)
    storageState: string          # Path to Playwright storage state (optional)
    tags: [string]                # For filtering (optional)
    fixtures:                     # Test data setup (optional)
      seed: string                # Seed script path
      user: string                # Env var name for username
      role: string                # Expected role
    assertions:                   # Deterministic checks (required, 1+)
      - type: url_contains | url_equals | text_visible | text_not_visible |
              locator_visible | locator_count | api_response | db_query |
              log_contains | console_no_errors | network_no_failures
        value: string             # Expected value (for url/text types)
        selector: string          # CSS selector (for locator types)
        count: number             # Expected count (for locator_count)
        timeoutMs: number         # Assertion-specific timeout
        query: string             # SQL or API query (for db/api types)
        expected: string          # Expected query result
```

### Rules

- `task` uses business language — PageAgent translates to DOM operations
- `assertions` are always deterministic — no "AI thinks it passed"
- `maxSteps` is mandatory to prevent runaway LLM calls
- Random test data uses unique prefix (e.g., `e2e_<timestamp>_`)
- Login state via `storageState` or `fixtures.user` env var reference
- Failure produces a reproducibility report, never auto-modifies business code

---

## 5. PageAgent Injector Configuration

```typescript
// page-agent-injector.ts creates window.__pageAgentE2E in browser context

const config = {
  model: process.env.PAGE_AGENT_LLM_MODEL,         // e.g., "gpt-4o"
  baseURL: process.env.PAGE_AGENT_LLM_BASE_URL,    // e.g., "https://api.openai.com/v1"
  apiKey: process.env.PAGE_AGENT_LLM_API_KEY,
  language: process.env.PAGE_AGENT_LANGUAGE || 'zh-CN',
  maxSteps: caseConfig.maxSteps || 20,
  stepDelay: 0.3,                                   // seconds between steps
  enableMask: false,                                // no visual mask by default
  experimentalScriptExecutionTool: false,           // DISABLED — no arbitrary JS
  instructions: {
    system: `你是 E2E 测试执行器。优先使用页面可见文本、表单标签、按钮文本和 DOM 语义完成操作。
不要依赖截图。不要等待超过必要时间。任务完成后必须调用 done，并说明完成状态。
自然语言完成说明不能替代确定性断言。`
  },
  transformPageContent: (content: string) => {
    // Redact sensitive patterns before sending to LLM
    return content
      .replace(/Bearer\s+[A-Za-z0-9\-._~+/]+=*/g, 'Bearer [REDACTED]')
      .replace(/Authorization:\s*.+/gi, 'Authorization: [REDACTED]')
      .replace(/1[3-9]\d{9}/g, '[PHONE_REDACTED]')
      .replace(/\w+@\w+\.\w+/g, '[EMAIL_REDACTED]')
      .replace(/\d{6}(18|19|20)\d{2}(0[1-9]|1[0-2])\d{6}/g, '[ID_REDACTED]')
      .replace(/access_token["\s:=]+[^\s"&]+/gi, 'access_token=[REDACTED]')
      .replace(/refresh_token["\s:=]+[^\s"&]+/gi, 'refresh_token=[REDACTED]')
      .replace(/password["\s:=]+[^\s"&]+/gi, 'password=[REDACTED]');
  }
};
```

### Security Constraints

- `experimentalScriptExecutionTool: false` — no arbitrary JS execution
- `enableMask: false` — no screenshot dependency
- `transformPageContent` redacts secrets before LLM sees DOM
- Custom tools limited to safe assertion helpers only:
  - `assert_text` — check text presence
  - `assert_url_contains` — check URL
  - `assert_element_count` — count elements

---

## 6. Runner Behavior (page-agent-runner.ts)

### Input
- YAML file path (or glob pattern)
- Configuration loaded from: (1) shell env vars, (2) runner `.env`, (3) skill `.env`, (4) defaults

### Process per case
1. Validate YAML schema (Zod) — fail fast on malformed input
2. Start Playwright Chromium (headless unless `PAGE_AGENT_DEBUG=1`)
3. Navigate to `baseUrl + route`
4. Inject PageAgent via `page.addInitScript()`
5. Execute `window.__pageAgentE2E.run(task, options)`
6. Collect result: `{ success, data, history, usage }`
7. Collect browser context: console messages, failed network requests, final URL
8. Extract text DOM summary (truncated to 20k chars)
9. Execute each assertion sequentially
10. Record pass/fail per assertion

### Output
- `reports/page-agent-e2e/<timestamp>.json` — structured results
- `reports/page-agent-e2e/<timestamp>.md` — human-readable report
- Append to `logs/page-agent-e2e/run.log` — JSONL entry
- Exit code: 0 if all pass, 1 if any fail

### Report Content (Markdown)
- Summary table (cases × pass/fail × duration × tokens)
- Per-failed-case: PageAgent step history, console errors, failed requests, final URL, DOM summary, assertion failures, most likely cause, suggested next step
- Token usage breakdown (prompt/completion/cached/reasoning)
- Does NOT include: API keys, cookies, passwords, auth tokens, full PII

---

## 7. Append-Only Execution Log

**Path:** `logs/page-agent-e2e/run.log`  
**Format:** JSONL (one JSON object per line)

### Schema per entry

```json
{
  "timestamp": "2026-06-07T12:00:00Z",
  "command": "pnpm page-agent:e2e:smoke",
  "gitBranch": "feat/frontend-interaction",
  "gitCommit": "2d715d33",
  "targetApp": "main",
  "targetBaseUrl": "http://localhost:5173",
  "taskFile": "tests/tools/page-agent/smoke.yaml",
  "caseCount": 3,
  "passCount": 2,
  "failCount": 1,
  "durationMs": 45000,
  "reportJson": "reports/page-agent-e2e/20260607-120000.json",
  "reportMd": "reports/page-agent-e2e/20260607-120000.md",
  "tokenUsage": {
    "totalTokens": 12345,
    "promptTokens": 8000,
    "completionTokens": 4000,
    "cachedTokens": 2000
  },
  "failedCaseIds": ["login-smoke"],
  "safetyWarnings": [],
  "verificationResult": "partial"
}
```

### Rules
- Append-only — never truncate or overwrite
- No secrets (API key, cookie, password, Authorization, tokens, PII)
- Read recent entries before starting a new debugging session for context
- Historical failures are context, not current truth — always re-verify

---

## 8. Configuration: Skill-local `.env` + Environment Variables

### Resolution Order

The runner loads configuration with the following priority (highest wins):

1. **Shell environment variables** — override everything (CI-friendly)
2. **`scripts/page-agent-e2e/.env`** — runner-local overrides
3. **`.claude/skills/page-agent-e2e/.env`** — skill-level defaults (recommended for local dev)
4. **Hardcoded defaults** — language=zh-CN, debug=0, maxSteps=20, etc.

This means developers can configure once in the skill `.env` and forget about it, while CI pipelines inject secrets via environment variables as usual.

### Skill-local `.env` (recommended for local development)

**Path:** `.claude/skills/page-agent-e2e/.env`  
**Committed:** NO — listed in `.claude/skills/page-agent-e2e/.gitignore`  
**Template:** `.claude/skills/page-agent-e2e/.env.example` (committed, no real secrets)

```env
# .claude/skills/page-agent-e2e/.env.example
# Copy to .env and fill in real values. Never commit .env itself.

# Required — PageAgent LLM (provider-agnostic)
PAGE_AGENT_LLM_BASE_URL=https://api.openai.com/v1
PAGE_AGENT_LLM_MODEL=gpt-4o
PAGE_AGENT_LLM_API_KEY=sk-...

# Optional — PageAgent behavior
PAGE_AGENT_LANGUAGE=zh-CN
PAGE_AGENT_DEBUG=0
PAGE_AGENT_STEP_DELAY=0.3

# Optional — Service URLs (skip auto-start if services already running)
PAGE_AGENT_BASE_URL=http://localhost:5173
PAGE_AGENT_BACKEND_URL=http://localhost:8000
PAGE_AGENT_E2E_SKIP_START=0

# Test credentials (from existing numina-sim-test accounts)
E2E_TEST_USER=demouser
E2E_TEST_PASSWORD=DemoPass123

# Optional — Child app
PAGE_AGENT_CHILD_BASE_URL=http://localhost:5174
E2E_CHILD_PIN=1234
E2E_CHILD_USER=child_test
```

### `.gitignore` for the skill

**Path:** `.claude/skills/page-agent-e2e/.gitignore`

```gitignore
# Secrets — never commit
.env

# Generated at runtime
*.log
```

### Runner `.env` loading logic (in page-agent-runner.ts)

```typescript
import { config } from 'dotenv';
import { resolve } from 'path';

// Load skill-level .env first (lowest priority file)
config({ path: resolve(__dirname, '../../.claude/skills/page-agent-e2e/.env') });
// Load runner-level .env (overrides skill-level)
config({ path: resolve(__dirname, '.env') });
// Shell env vars already set take highest priority (dotenv won't overwrite)
```

`dotenv` does not overwrite existing `process.env` values, so shell env vars always win. This makes CI simple: set secrets in the workflow, no file needed.

### When to use which

| Context | Where to configure |
|---------|-------------------|
| Local dev (one developer) | `.claude/skills/page-agent-e2e/.env` |
| Local dev (runner-specific override) | `scripts/page-agent-e2e/.env` |
| CI / GitHub Actions | Workflow `env:` block or repository secrets |
| Docker | `docker-compose.yml` environment section |
| Shared team defaults (non-secret) | `.env.example` template + docs |

---

## 9. Smoke Test Cases

```yaml
# tests/tools/page-agent/smoke.yaml
cases:
  - id: login-smoke
    app: main
    route: /login
    task: |
      使用测试账号登录系统。账号来自环境变量 E2E_TEST_USER，密码来自环境变量 E2E_TEST_PASSWORD。
      如果看到用户名输入框，输入测试账号。
      如果看到密码输入框，输入测试密码。
      点击登录按钮。登录成功后停在首页或仪表盘。
    maxSteps: 12
    fixtures:
      user: E2E_TEST_USER
    assertions:
      - type: url_contains
        value: /dashboard
      - type: text_not_visible
        value: 登录失败
      - type: console_no_errors

  - id: asset-list-smoke
    app: main
    route: /assets
    task: |
      确认资产列表页面已加载。检查页面是否显示资产相关内容。
      如果有搜索框，尝试输入"测试"进行搜索。
    maxSteps: 8
    storageState: tests/tools/page-agent/.auth/main-user.json
    assertions:
      - type: url_contains
        value: /assets
      - type: network_no_failures

  - id: child-login-smoke
    app: child
    route: /
    task: |
      在儿童端输入 PIN 码登录。PIN 码来自环境变量 E2E_CHILD_PIN。
      找到 PIN 输入区域，输入数字。确认进入儿童主页。
    maxSteps: 10
    fixtures:
      user: E2E_CHILD_USER
    assertions:
      - type: url_contains
        value: /home
      - type: console_no_errors
```

---

## 10. Package Scripts

Added to `scripts/page-agent-e2e/package.json`:

```json
{
  "scripts": {
    "e2e": "tsx page-agent-runner.ts tests/tools/page-agent/**/*.yaml",
    "e2e:smoke": "tsx page-agent-runner.ts tests/tools/page-agent/smoke.yaml",
    "e2e:validate": "tsx task-schema.ts --validate tests/tools/page-agent/**/*.yaml",
    "e2e:report": "tsx report.ts --last",
    "e2e:verify": "tsx verify-smoke.ts"
  }
}
```

Root-level convenience scripts (via pnpm workspace or npm scripts in root package.json):

```
pnpm --filter page-agent-e2e e2e
pnpm --filter page-agent-e2e e2e:smoke
pnpm --filter page-agent-e2e e2e:validate
pnpm --filter page-agent-e2e e2e:verify
```

---

## 11. Verification Strategy

### What counts as "verified"

| Evidence | Method |
|----------|--------|
| YAML schema valid | `pnpm --filter page-agent-e2e e2e:validate` exits 0 |
| Smoke dry-run executable | Runner starts, connects to browser, attempts injection |
| JSON report generated | File exists at `reports/page-agent-e2e/<ts>.json` |
| Markdown report generated | File exists at `reports/page-agent-e2e/<ts>.md` |
| Failed report has evidence | Contains: final URL, console errors, failed requests, DOM summary, assertion failures |
| Exit code correct | 0 on all-pass, 1 on any-fail |
| Log entry appended | New line in `logs/page-agent-e2e/run.log` |
| No secrets in output | grep for Bearer/password/cookie/token in reports returns empty |

### Prohibited "verification"

- "Feels like it works"
- "PageAgent said task completed"
- "No visible errors in the code"
- "Logic seems correct"
- "Page should have redirected"

---

## 12. Safety & CI

### Dangerous operation interception

When any command touches:
- `rm -rf`, `sudo rm`, `chmod -R 777`
- `git push --force`, `git reset --hard`, `git clean -fdx`
- `kubectl delete`, `terraform destroy`, `docker system prune`
- `truncate/drop table`, delete migration, overwrite `.env`
- Print/upload API key/token/cookie
- Enable `execute_javascript` in CI
- Inject LLM API key into production frontend bundle

**Action:** Trigger `/careful` if available, otherwise enter manual careful mode (explain risk, propose alternative, require explicit confirmation).

### CI defaults

- No screenshots by default
- `experimentalScriptExecutionTool: false`
- Upload only JSON + Markdown reports as artifacts
- Never upload env files or secrets
- Fail-fast on secret detection in report output

---

## 13. Project Gotchas (from codebase analysis)

These will be fully documented in `references/project-gotchas.md`. Summary:

1. **Snowflake ID serialization** — All IDs are bigint serialized as strings in API responses. E2E assertions comparing IDs must treat them as strings, not numbers.

2. **No trailing slash on API routes** — Backend uses `redirect_slashes=False`. All API calls must omit trailing slash or they get 404/307. PageAgent tasks hitting API endpoints must respect this.

3. **Auth returns 200, not 201** — Login/register endpoints return 200 with TokenResponse. E2E must not assert 201 for auth flows.

4. **TokenResponse has no user field** — After login, frontend must call `/auth/me` to get user info. PageAgent login flow must wait for the `/auth/me` call to complete before asserting user-specific content is visible.

5. **Dashboard allocation returns `{items: [...], total: float}`** — Not a flat list. E2E assertions on dashboard data must expect nested structure.

6. **i18n required for all UI strings** — All visible text goes through `t('key')`. E2E text assertions must match i18n values (zh-CN default), not hardcoded strings that might drift.

7. **Child app uses PIN authentication** — Different auth flow from main app (no username/password). PageAgent cases for child app must use PIN entry pattern.

---

## 14. Token/Speed Advantage

| Metric | Screenshot-based (numina-sim-test) | PageAgent text DOM |
|--------|-----------------------------------|--------------------|
| Tokens per page interaction | ~5,000-20,000 (image encoding) | ~500-2,000 (text DOM) |
| Latency per step | 3-8s (screenshot + vision model) | 0.5-2s (text parse + LLM) |
| Model requirement | Multimodal (GPT-4V, Claude Vision) | Any text LLM (GPT-4o, Claude, local) |
| CI cost per run | High | 5-10x lower |
| Flakiness | High (rendering differences) | Lower (text is stable) |

---

## 15. Risks & Future Optimization

### Risks

- **PageAgent maturity** — Alibaba PageAgent is relatively new; API may change
- **Complex dynamic pages** — Heavy SPA rendering (ECharts, virtual scroll) may produce large DOM text
- **LLM cost** — Still requires LLM calls per step; costs accumulate on long flows
- **Auth state management** — StorageState serialization between Playwright and PageAgent needs testing

### Future optimizations

- Cache PageAgent DOM snapshots for repeated navigation patterns
- Use cheaper/faster models for simple interactions (GPT-4o-mini, Haiku)
- Parallel case execution when cases are independent
- Integration with existing `tests/lib/auth.ts` for shared login state
- PageAgent step recording → replay for deterministic regression without LLM

---

## 16. Dependencies

### New npm packages (for scripts/page-agent-e2e/)

```json
{
  "dependencies": {
    "page-agent": "latest",
    "@anthropic-ai/sdk": "^0.39.0",
    "openai": "^4.0.0"
  },
  "devDependencies": {
    "@playwright/test": "^1.52.0",
    "tsx": "^4.0.0",
    "typescript": "^5.7.0",
    "zod": "^3.23.0",
    "yaml": "^2.7.0",
    "dotenv": "^16.4.0"
  }
}
```

### No changes to existing packages

- Frontend apps unchanged
- Server Python packages unchanged
- Existing `tests/package.json` unchanged (PageAgent runner is a separate package)

---

## 17. Success Criteria

This implementation is complete when:

1. `.claude/skills/page-agent-e2e/SKILL.md` triggers correctly on E2E-related prompts
2. `pnpm --filter page-agent-e2e e2e:validate` passes on smoke.yaml
3. `pnpm --filter page-agent-e2e e2e:smoke` executes (connects to browser, attempts PageAgent injection)
4. Reports generate in both JSON and Markdown format
5. `logs/page-agent-e2e/run.log` receives JSONL entries
6. TypeScript compiles without errors
7. No secrets appear in any generated output
8. `numina-sim-test` continues to work independently

If services are not running locally, the runner must exit with a clear error message explaining what's needed, not pretend success.
