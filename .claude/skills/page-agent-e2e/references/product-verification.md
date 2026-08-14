# Product Verification Standards

## What Counts as "Verified"

| Claim | Required Evidence | Method |
|-------|------------------|--------|
| "Test passes" | Exit code 0 + assertion results in report | `tsx page-agent-runner.ts` |
| "Login works" | `url_contains: /dashboard` assertion passes | YAML assertion |
| "No errors" | `console_no_errors` assertion passes | Browser console capture |
| "Page loads" | `url_contains` + `network_no_failures` | Combined assertions |
| "Form submits" | URL change + success text visible | `url_contains` + `text_visible` |
| "Data displays" | Specific text visible on page | `text_visible` assertion |
| "API responds" | No 4xx/5xx in network log | `network_no_failures` |

## Prohibited "Verification" Statements

Never claim verification based on:
- PageAgent's natural-language "I completed the task" response
- "The code looks correct" without running it
- "It should work" without evidence
- "No errors appeared" without `console_no_errors` assertion
- "The page loaded" without URL/content assertion
- Partial assertion passes (if any assertion fails, the case fails)

## Verification Commands

```bash
# Verify YAML is valid
cd scripts/page-agent-e2e && npx tsx task-schema.ts --validate ../../tests/tools/page-agent/smoke.yaml

# Run full smoke suite
cd scripts/page-agent-e2e && npx tsx page-agent-runner.ts ../../tests/tools/page-agent/smoke.yaml

# Check last report
cd scripts/page-agent-e2e && npx tsx report.ts --last

# Run post-run verification
cd scripts/page-agent-e2e && npx tsx verify-smoke.ts

# Check TypeScript compiles
cd scripts/page-agent-e2e && npx tsc --noEmit
```

## Post-Run Verification Checklist

After any test run, verify:

1. **Exit code** — 0 means all passed, 1 means at least one failed
2. **Report exists** — check `reports/page-agent-e2e/` for new JSON + MD files
3. **Log entry** — check `logs/page-agent-e2e/run.log` for new JSONL line
4. **No secrets** — scan report for leaked credentials
5. **Assertion detail** — read failed assertions for actionable information
6. **Token usage** — check total tokens are within expected bounds
7. **Duration** — check total duration is reasonable (not hung)

## Failure Triage

When a test fails:

1. Read the Markdown report's "Failed Cases" section
2. Check the final URL — did navigation succeed?
3. Check console errors — is the app broken?
4. Check network failures — are APIs down?
5. Check PageAgent history — did it take wrong actions?
6. Check DOM summary — is the expected content on the page?

Never auto-fix business code based on test failure. Produce a failure report and present it for human decision.
