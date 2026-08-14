---
name: page-agent-e2e
description: "Triggers on: e2e, end-to-end, Playwright, Vue E2E, Python Vue integration test, smoke test, UI workflow test, login flow test, approval flow test, CRUD flow test, search/filter test, admin workflow test, avoid screenshots, stop using screenshots for AI testing, reduce token usage in browser tests, PageAgent, DOM-based UI automation, semantic browser test. Use when creating, fixing, optimizing, or running long-path UI automation in Python + Vue projects. Prefer Alibaba PageAgent for semantic page interaction through text DOM, and verify outcomes with deterministic Playwright/API/database assertions."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Edit
  - Write
  - Bash
---

# PageAgent E2E Skill

Semantic DOM-based E2E testing using Alibaba PageAgent. Reads text DOM instead of screenshots. 10-50x cheaper in tokens than vision-based approaches.

## When to Use

- Multi-page business workflows (login → CRUD → approval → verification)
- Forms, navigation, search/filter flows across Vue frontend + Python backend
- Replacing brittle Playwright locators with semantic natural-language steps
- Reducing token cost from screenshot-based AI testing
- Cases where `numina-sim-test` would be overkill (no visual audit needed)

## When NOT to Use

- Visual regression testing (colors, spacing, layout) → use `numina-sim-test`
- Pure API tests → use pytest
- Pure component tests → use vitest
- Stable locator-based tests that already work → leave as Playwright specs

## Architecture

Runner: `scripts/page-agent-e2e/page-agent-runner.ts`
Tests: `tests/tools/page-agent/*.yaml`
Reports: `reports/page-agent-e2e/`
Log: `logs/page-agent-e2e/run.log`

PageAgent handles semantic interaction (click, type, scroll via text DOM).
Playwright handles browser lifecycle, navigation, and deterministic assertions.
Never trust PageAgent's natural-language "success" — always verify with assertions.

## Workflow

1. Identify target app and flow to test
2. Write or update YAML case in `tests/tools/page-agent/`
3. Validate: `cd scripts/page-agent-e2e && npx tsx task-schema.ts --validate <file>`
4. Run: `cd scripts/page-agent-e2e && npx tsx page-agent-runner.ts <file>`
5. Check report in `reports/page-agent-e2e/`
6. On failure: read report evidence (URL, console, network, DOM), fix case or code
7. Never auto-modify business code on failure — produce a failure report first

## Constraints

- `experimentalScriptExecutionTool: false` — no arbitrary JS execution in PageAgent
- `enableMask: false` — no screenshot dependency
- Content redacted before LLM sees DOM (Bearer tokens, passwords, PII)
- Every case must have deterministic assertions (url, text, locator, API, DB)
- maxSteps is mandatory to prevent runaway LLM calls
- Random test data uses `e2e_<timestamp>_` prefix
- Exit code 1 on any failure
- No secrets in reports or logs

## Configuration

See `.env.example` in this directory. Copy to `.env` for local config.
Priority: shell env > runner .env > skill .env > defaults.

## References

Read these when context is needed:
- `references/project-gotchas.md` — before writing any assertion for this project
- `references/task-yaml-schema.md` — YAML format reference
- `references/security-and-ci.md` — CI rules and dangerous operation interception
- `references/product-verification.md` — what counts as "verified"
- `references/hooks-and-memory.md` — safety hooks and logging rules
- `references/page-agent-e2e-architecture.md` — full architecture details

## Prohibitions

- Never use screenshots to understand page content
- Never use OCR or multimodal vision as primary page understanding
- Never put API keys in production frontend bundles
- Never enable execute_javascript in CI
- Never claim success based only on PageAgent's natural-language response
- Never auto-modify business code on test failure without a failure report
- Never use "feels right" or "looks correct" as verification
