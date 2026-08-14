# PageAgent E2E — Setup Guide

Semantic DOM-based E2E testing using [Alibaba PageAgent](https://github.com/anthropics/anthropic-cookbook). Reads text DOM instead of screenshots — 10-50x cheaper in tokens than vision-based approaches.

## Prerequisites

| Dependency | Version | Purpose |
|-----------|---------|---------|
| Node.js | ≥18 | Runner runtime |
| pnpm | ≥8 | Package manager |
| Playwright | (installed by runner) | Browser automation |
| An OpenAI-compatible LLM API | — | PageAgent semantic interaction |

## Quick Start

```bash
# 1. Install runner dependencies
cd scripts/page-agent-e2e
pnpm install

# 2. Install browser
npx playwright install chromium

# 3. Configure environment
cp .claude/skills/page-agent-e2e/.env.example .claude/skills/page-agent-e2e/.env
# Edit .env — at minimum fill in PAGE_AGENT_LLM_API_KEY and E2E_TEST_PASSWORD

# 4. Start the app (or use Docker)
cd frontend/apps/main && pnpm dev &
cd server && uv run uvicorn apps.backend.app.main:app --port 8000 &

# 5. Run smoke tests
cd scripts/page-agent-e2e
npx tsx page-agent-runner.ts ../../tests/tools/page-agent/smoke.yaml
```

## Configuration

Copy `.env.example` to `.env` in this directory and fill in values.

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `PAGE_AGENT_LLM_API_KEY` | API key for the LLM provider | `sk-...` |
| `PAGE_AGENT_LLM_BASE_URL` | OpenAI-compatible API base URL | `https://api.openai.com/v1` |
| `PAGE_AGENT_LLM_MODEL` | Model name for semantic interaction | `gpt-4o` |
| `E2E_TEST_USER` | Pre-seeded test username | `test_rich` |
| `E2E_TEST_PASSWORD` | Password for the test user | — |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PAGE_AGENT_BASE_URL` | `http://localhost:5173` | Main app URL |
| `PAGE_AGENT_CHILD_BASE_URL` | `http://localhost:5174` | Child app URL |
| `PAGE_AGENT_BACKEND_URL` | `http://localhost:8000` | Backend API URL |
| `PAGE_AGENT_LANGUAGE` | `zh-CN` | PageAgent system prompt language |
| `PAGE_AGENT_DEBUG` | `0` | `1` = headed browser for debugging |
| `PAGE_AGENT_STEP_DELAY` | `0.3` | Seconds between PageAgent steps |
| `PAGE_AGENT_E2E_SKIP_START` | `0` | `1` = skip auto-starting dev servers |
| `E2E_CHILD_USER` | — | Child app test username |
| `E2E_CHILD_PIN` | — | Comma-separated emoji PIN (e.g. `🐱,🐶,🌟,🌈`) |

### Env Priority

```
shell env  >  runner .env (scripts/page-agent-e2e/.env)  >  skill .env (.claude/skills/page-agent-e2e/.env)  >  defaults
```

## LLM Provider Options

PageAgent uses any OpenAI-compatible chat API. Tested configurations:

| Provider | BASE_URL | MODEL | Notes |
|----------|----------|-------|-------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` | Recommended, best accuracy |
| Azure OpenAI | `https://<endpoint>.openai.azure.com/openai/deployments/<deployment>/` | `gpt-4o` | Set API key via `PAGE_AGENT_LLM_API_KEY` |
| Deepseek | `https://api.deepseek.com/v1` | `deepseek-chat` | Cheaper, slightly less accurate |
| Local (Ollama) | `http://localhost:11434/v1` | `qwen2.5:72b` | Free, needs beefy hardware |

## File Structure

```
.claude/skills/page-agent-e2e/
├── SKILL.md              ← Skill definition (triggers, constraints)
├── .env.example          ← Configuration template (this guide)
├── .env                  ← Your local config (git-ignored)
├── .gitignore
├── README.md             ← You are here
├── examples/
│   └── smoke.yaml        ← Example test case
└── references/
    ├── page-agent-e2e-architecture.md
    ├── project-gotchas.md
    ├── task-yaml-schema.md
    ├── security-and-ci.md
    ├── product-verification.md
    └── hooks-and-memory.md

scripts/page-agent-e2e/       ← Runner implementation
tests/tools/page-agent/         ← Test YAML files
reports/page-agent-e2e/       ← Generated reports (git-ignored)
logs/page-agent-e2e/          ← Execution logs (git-ignored)
```

## Writing Test Cases

Test cases are YAML files. See `examples/smoke.yaml` for the structure:

```yaml
cases:
  - id: my-flow          # Unique identifier
    app: main            # main | child
    route: /login        # Starting route
    task: |              # Natural language task for PageAgent
      描述 PageAgent 需要执行的操作步骤。
      使用自然语言，就像告诉一个人怎么操作一样。
    maxSteps: 12         # Hard cap on LLM calls (mandatory)
    assertions:          # Deterministic verification (mandatory)
      - type: url_contains
        value: /dashboard
      - type: text_not_visible
        value: 错误
      - type: console_no_errors
```

### Assertion Types

| Type | Description |
|------|-------------|
| `url_contains` | Final URL includes the value |
| `url_equals` | Final URL exactly matches |
| `text_visible` | Text appears in the DOM |
| `text_not_visible` | Text does NOT appear in the DOM |
| `locator_visible` | CSS selector matches a visible element |
| `locator_count` | CSS selector matches N elements |
| `console_no_errors` | No `console.error` calls during test |
| `network_no_failures` | No 4xx/5xx network responses |

Full schema: `references/task-yaml-schema.md`

## Running Tests

```bash
cd scripts/page-agent-e2e

# Run a specific test file
npx tsx page-agent-runner.ts ../../tests/tools/page-agent/smoke.yaml

# Validate YAML without running
npx tsx task-schema.ts --validate ../../tests/tools/page-agent/smoke.yaml

# Debug mode (headed browser, pauses on failure)
PAGE_AGENT_DEBUG=1 npx tsx page-agent-runner.ts ../../tests/tools/page-agent/smoke.yaml
```

## CI Integration

```yaml
# GitHub Actions example
- name: Run PageAgent E2E
  env:
    PAGE_AGENT_LLM_API_KEY: ${{ secrets.PAGE_AGENT_LLM_API_KEY }}
    E2E_TEST_USER: ${{ secrets.E2E_TEST_USER }}
    E2E_TEST_PASSWORD: ${{ secrets.E2E_TEST_PASSWORD }}
    PAGE_AGENT_DEBUG: "0"
    PAGE_AGENT_STEP_DELAY: "0.1"
  run: |
    cd scripts/page-agent-e2e
    npx playwright install chromium
    npx tsx page-agent-runner.ts ../../tests/tools/page-agent/smoke.yaml

- name: Upload reports
  if: always()
  uses: actions/upload-artifact@v4
  with:
    name: page-agent-reports
    path: reports/page-agent-e2e/
```

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `401 Unauthorized` from LLM | Invalid API key | Check `PAGE_AGENT_LLM_API_KEY` |
| PageAgent hangs on step | Rate limit or model timeout | Increase `PAGE_AGENT_STEP_DELAY`, check provider status |
| `text_visible` assertion fails | i18n key mismatch | Check exact string in `src/i18n/locales/zh-CN.ts` |
| `network_no_failures` fails on login | Auth returns 200, not 201 | Expected — see `references/project-gotchas.md` |
| 307 redirects in network log | Trailing slash in route | Remove trailing slash from `route` in YAML |
| Child PIN login fails | Wrong PIN format | PIN must be comma-separated emojis: `🐱,🐶,🌟,🌈` |
| Browser doesn't launch | Missing Playwright browsers | Run `npx playwright install chromium` |

## Security

- Secrets are **never** stored in YAML files or reports
- DOM content is redacted (tokens, passwords, PII) before reaching the LLM
- `experimentalScriptExecutionTool` is always `false`
- Screenshots are disabled (`enableMask: false`)
- See `references/security-and-ci.md` for full details
