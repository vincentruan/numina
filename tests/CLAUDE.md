# tests/CLAUDE.md

E2E, visual regression, and test infrastructure guidance.

## Directory Structure

```
tests/
├── e2e/              # Playwright specs (*.spec.ts) + Python smoke
│   └── scripts/      # Shell runners (acceptance.sh, extended.sh …)
├── visual/           # Visual regression (visual.config.ts, visual-check.*)
├── lib/              # TS shared utilities (auth, fixtures, routes)
├── data/             # Python test data (factories/, scenarios/, seed_data.py)
├── fixtures/         # Static fixtures (openapi.snapshot.json)
├── tools/            # Standalone tools (screenshot/, page-agent/ config)
├── scripts/          # Helper scripts (update-openapi-snapshot.js)
└── playwright.config.ts / tsconfig.json / package.json
```

## Commands

```bash
# E2E tests (from repo root)
pnpm exec playwright test                    # all specs
pnpm exec playwright test --project=chromium # specific browser

# Python backend tests (from server/)
uv run pytest tests/ -v                      # full suite

# Visual regression
pnpm exec playwright test --config=tests/visual/visual.config.ts
```

## Rules

- New E2E specs go in `tests/e2e/`, shell scripts in `tests/e2e/scripts/`
- Screenshot outputs (`.png`) are `.gitignore`-excluded — do not commit
- Backend tests live in `server/tests/` (see [`server/CLAUDE.md`](../server/CLAUDE.md) §Quality Commands)

## Solutions (Test/Seed Lessons Learned)

| Doc | Topic |
|-----|-------|
| [`audit-service-session-closure`](../docs/solutions/test-failures/audit-service-session-closure-test-isolation-2026-05-14.md) | SQLAlchemy session 关闭破坏测试隔离 |
| [`extraction-failure-samples`](../docs/solutions/test-failures/2026-05-19-extraction-failure-samples.md) | Agent 结果提取诊断协议 |

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, project overview
- [`server/CLAUDE.md`](../server/CLAUDE.md) — backend quality commands
- [`frontend/CLAUDE.md`](../frontend/CLAUDE.md) — frontend quality commands
