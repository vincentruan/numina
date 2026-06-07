# Security and CI Rules

## Dangerous Operation Interception

The following operations are intercepted and blocked in PageAgent E2E:

| Operation | Risk | Mitigation |
|-----------|------|-----------|
| `experimentalScriptExecutionTool: true` | Arbitrary JS execution in browser | Always set to `false` |
| Hardcoded credentials in YAML | Secret exposure in reports/logs | Use env var references only |
| Screenshot capture | Exposes sensitive UI data | Disabled (`enableMask: false`) |
| Direct database writes | Data corruption | Read-only assertions only |
| `git push` from runner | Accidental code deployment | Never called by runner |
| Unrestricted network access | Data exfiltration | PageAgent sees only DOM text |

## CI Defaults

```yaml
# Required CI environment constraints
PAGE_AGENT_DEBUG: "0"           # No headed browser in CI
PAGE_AGENT_STEP_DELAY: "0.1"   # Faster execution in CI
```

- **No screenshots** — `enableMask: false` means no visual capture
- **No execute_javascript** — `experimentalScriptExecutionTool: false` always
- **Artifacts** — only reports (JSON/MD) and JSONL logs are uploaded
- **Secrets** — only via repository secrets, never in files

## Secret Detection in Output

The runner performs content redaction before any data reaches the LLM:

```
Bearer tokens       → Bearer [REDACTED]
Authorization headers → Authorization: [REDACTED]
Phone numbers (CN)  → [PHONE_REDACTED]
Email addresses     → [EMAIL_REDACTED]
ID card numbers     → [ID_REDACTED]
access_token values → access_token=[REDACTED]
refresh_token values → refresh_token=[REDACTED]
password values     → password=[REDACTED]
```

If a report or log entry contains any of these patterns un-redacted, the run should be considered compromised and the output should be deleted.

## Content Redaction Implementation

The `transformPageContent` function in `page-agent-injector.ts` applies regex-based redaction before the DOM content is sent to the LLM. This runs in the browser context before any data leaves the page.

## CI Pipeline Integration

```yaml
# Recommended CI job structure
steps:
  1. Checkout code
  2. Install runner deps (npm ci in scripts/page-agent-e2e/)
  3. Install Playwright browsers (npx playwright install chromium)
  4. Start services (docker-compose or scripts)
  5. Wait for health checks
  6. Validate YAML schemas (tsx task-schema.ts --validate)
  7. Run smoke tests (tsx page-agent-runner.ts)
  8. Upload reports as artifacts (always, even on failure)
  9. Check exit code (0 = pass, 1 = fail)
```

## Secret Scanning in Reports

Before uploading any artifact in CI, scan for leaked secrets:

```bash
# Fail if any secrets found in reports
grep -rn "sk-\|Bearer [A-Z]\|password:" reports/page-agent-e2e/ && exit 1 || echo "Clean"
```

## Network Isolation

PageAgent communicates only with:
1. The LLM API (configured via `PAGE_AGENT_LLM_BASE_URL`)
2. The target application (configured via `PAGE_AGENT_BASE_URL`)

No other outbound network access is required or expected.
