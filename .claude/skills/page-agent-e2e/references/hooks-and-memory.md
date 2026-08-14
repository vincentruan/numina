# Hooks and Memory

## Append-Only Log

All test runs are recorded in `logs/page-agent-e2e/run.log` as JSONL (one JSON object per line).

### Schema

```json
{
  "timestamp": "ISO-8601",
  "command": "tsx page-agent-runner.ts <file>",
  "gitBranch": "string | null",
  "gitCommit": "string | null",
  "targetApp": "main | child",
  "targetBaseUrl": "http://localhost:5173",
  "taskFile": "tests/tools/page-agent/smoke.yaml",
  "caseCount": 3,
  "passCount": 2,
  "failCount": 1,
  "durationMs": 45000,
  "reportJson": "/path/to/report.json",
  "reportMd": "/path/to/report.md",
  "tokenUsage": {
    "totalTokens": 15000,
    "promptTokens": 12000,
    "completionTokens": 3000,
    "cachedTokens": 0
  },
  "failedCaseIds": ["login-smoke"],
  "safetyWarnings": [],
  "verificationResult": "partial"
}
```

### Rules

- **Append-only** — never modify or delete existing entries
- **One entry per run** — not per case
- **Git context** — always capture branch + commit for traceability
- **Token tracking** — enables cost analysis over time
- **Verification result** — `pass` (all green), `partial` (some pass), `fail` (none pass)

## Read-Before-Debug Requirement

Before debugging a test failure, ALWAYS read:

1. The latest JSONL log entry (tail -1 of run.log)
2. The Markdown report for the failed run
3. The specific failed case's assertions, console errors, and network failures
4. The DOM summary of the page at failure time

Never guess at the cause of a failure. Evidence first.

## Memory vs Log Distinction

| Aspect | Memory (Claude Code) | Log (JSONL) |
|--------|---------------------|-------------|
| Purpose | Cross-session context | Run history |
| Lifetime | Until manually deleted | Forever (append-only) |
| Format | Markdown with frontmatter | JSONL |
| Content | Decisions, patterns, gotchas | Run results, metrics |
| Use case | "How should I approach X?" | "What happened last run?" |

## Safety Hooks

### `/careful` Integration

When a dangerous operation is detected (modifying business code, changing auth, deleting data), the skill should:

1. Stop execution
2. Present the evidence of what was about to happen
3. Wait for explicit confirmation before proceeding

### What Triggers `/careful`

- Any attempt to modify files outside `scripts/page-agent-e2e/` or `tests/tools/page-agent/`
- Deleting test data or fixtures
- Changing environment variables that affect production
- Running PageAgent with `experimentalScriptExecutionTool: true`
- Any git push operation

### Logging Safety Warnings

If a safety boundary is approached but not crossed, record it in the JSONL log's `safetyWarnings` array:

```json
"safetyWarnings": [
  "Attempted to modify server/apps/backend/ — blocked",
  "Console error suggests auth token expired"
]
```
