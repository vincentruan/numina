# PageAgent E2E Architecture

## Overview

```
┌─────────────────────────────────────────────────────────┐
│  Claude Code Skill (.claude/skills/page-agent-e2e/)     │
│  - SKILL.md (trigger rules + constraints)               │
│  - references/ (gotchas, schema, security)              │
│  - examples/ (YAML templates)                           │
└────────────────────────┬────────────────────────────────┘
                         │ invokes
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Runner (scripts/page-agent-e2e/)                       │
│  page-agent-runner.ts  ← main orchestrator              │
│  ├── config.ts         ← dotenv + env resolution        │
│  ├── task-schema.ts    ← Zod YAML validation            │
│  ├── page-agent-injector.ts ← browser injection         │
│  ├── assertions.ts     ← deterministic checks           │
│  ├── report.ts         ← JSON + Markdown output         │
│  └── logger.ts         ← append-only JSONL              │
└────────────────────────┬────────────────────────────────┘
                         │ reads
                         ▼
┌─────────────────────────────────────────────────────────┐
│  Test Cases (tests/tools/page-agent/*.yaml)               │
│  - smoke.yaml (core flows)                              │
│  - custom/*.yaml (feature-specific)                     │
└─────────────────────────────────────────────────────────┘
```

## Runner Process

1. Load config (dotenv cascade: shell > runner .env > skill .env)
2. Parse and validate YAML task file via Zod schema
3. For each case:
   a. Launch headless Chromium via Playwright
   b. Set viewport (390×844 mobile by default)
   c. Navigate to `baseUrl + route`
   d. Inject PageAgent config into page context
   e. Run PageAgent task (semantic DOM interaction)
   f. Execute deterministic assertions
   g. Capture console errors, network failures, final URL, DOM summary
   h. Close browser
4. Generate JSON + Markdown reports
5. Append entry to JSONL execution log
6. Exit 0 (all pass) or 1 (any failure)

## PageAgent Injector

The injector configures PageAgent with:
- `enableMask: false` — no screenshots, text DOM only
- `experimentalScriptExecutionTool: false` — no arbitrary JS
- `transformPageContent` — redacts Bearer tokens, passwords, phone numbers, emails, ID numbers before sending to LLM
- System instruction in Chinese directing task-focused behavior

## Relationship with numina-sim-test

| Aspect | page-agent-e2e | numina-sim-test |
|--------|---------------|-----------------|
| Primary use | Business logic flows | Visual/UI audit |
| Page understanding | Text DOM | Screenshots |
| Token cost | Low (text only) | High (vision) |
| Assertions | Deterministic (URL, text, API) | Visual comparison |
| Speed | Fast (no image processing) | Slower |
| When to use | Login, CRUD, navigation, forms | Layout, colors, responsiveness |

## Token Cost Advantage

Text DOM for a typical page: 2-8K tokens per step.
Screenshot-based (vision): 50-200K tokens per step.
Savings: 10-50x per interaction step.

For a 10-step test case:
- Text DOM: ~50K tokens total
- Vision: ~500K-2M tokens total

## Known Limitations

- Cannot verify visual elements (colors, spacing, animations)
- Depends on text content being meaningful (empty pages fail)
- PageAgent LLM quality varies by model — gpt-4o recommended
- Rate limits from LLM provider apply per step
- Network errors during PageAgent execution are non-retriable by default
