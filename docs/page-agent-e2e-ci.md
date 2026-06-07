# PageAgent E2E — CI Integration Guide

## GitHub Actions Example

```yaml
name: PageAgent E2E
on:
  pull_request:
    paths:
      - 'frontend/**'
      - 'server/**'
      - 'tests/e2e/page-agent/**'

jobs:
  page-agent-e2e:
    runs-on: ubuntu-latest
    env:
      PAGE_AGENT_LLM_BASE_URL: ${{ secrets.PAGE_AGENT_LLM_BASE_URL }}
      PAGE_AGENT_LLM_MODEL: gpt-4o
      PAGE_AGENT_LLM_API_KEY: ${{ secrets.PAGE_AGENT_LLM_API_KEY }}
      PAGE_AGENT_BASE_URL: http://localhost:5173
      PAGE_AGENT_BACKEND_URL: http://localhost:8000
      E2E_TEST_USER: test_rich
      E2E_TEST_PASSWORD: ${{ secrets.E2E_TEST_PASSWORD }}

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 22

      - name: Install runner dependencies
        run: cd scripts/page-agent-e2e && npm ci

      - name: Install Playwright browsers
        run: cd scripts/page-agent-e2e && npx playwright install chromium

      - name: Start services
        run: |
          docker-compose up -d
          npx wait-on http://localhost:5173 http://localhost:8000/api/v1/health

      - name: Validate YAML schemas
        run: cd scripts/page-agent-e2e && npx tsx task-schema.ts --validate '../../tests/e2e/page-agent/**/*.yaml'

      - name: Run smoke tests
        run: cd scripts/page-agent-e2e && npx tsx page-agent-runner.ts ../../tests/e2e/page-agent/smoke.yaml

      - name: Upload reports
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: page-agent-e2e-reports
          path: |
            reports/page-agent-e2e/*.json
            reports/page-agent-e2e/*.md
            logs/page-agent-e2e/run.log
```

## Security Notes

- Never upload `.env` files as artifacts
- LLM API key comes from repository secrets only
- `experimentalScriptExecutionTool` is always `false` in CI
- Reports are scanned for secrets before upload (fail-fast)
- No screenshots are taken or uploaded by default

## Local Development

```bash
# First time setup
cd scripts/page-agent-e2e
npm install
npx playwright install chromium
cp .env.example .env
# Edit .env with your LLM API key

# Run tests (requires services running)
npm run e2e:smoke

# Validate YAML only (no services needed)
npm run e2e:validate

# View last report
npm run e2e:report

# Run verification checks
npm run e2e:verify
```

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `PAGE_AGENT_LLM_API_KEY is required` | Missing env var | Set in `.env` or CI secrets |
| Connection refused to localhost:5173 | Frontend not running | Start services first |
| Timeout on navigation | Slow startup | Increase `timeoutMs` in YAML |
| All assertions fail | Wrong base URL | Check `PAGE_AGENT_BASE_URL` |
| Token count very high | Too many maxSteps | Reduce `maxSteps` per case |
