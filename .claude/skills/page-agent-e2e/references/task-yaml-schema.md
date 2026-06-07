# Task YAML Schema Reference

## Top-Level Structure

```yaml
cases:
  - id: <string>           # Required. Unique identifier for the case.
    app: main | child      # Optional. Default: "main". Which frontend app.
    description: <string>  # Optional. Human-readable description.
    baseUrl: <url>         # Optional. Override the config's baseUrl.
    route: <string>        # Required. Path to navigate to (e.g., "/login").
    task: <string>         # Required. Natural-language instructions for PageAgent.
    maxSteps: <int>        # Optional. Default: 20. Max PageAgent interaction steps (1-100).
    timeoutMs: <int>       # Optional. Default: 30000. Navigation timeout in ms (min 1000).
    storageState: <path>   # Optional. Path to Playwright storage state JSON.
    tags: [<string>]       # Optional. Tags for filtering.
    fixtures:              # Optional. Test data context.
      seed: <string>       # Seed script name
      user: <string>       # Env var name for test user
      role: <string>       # User role
    assertions:            # Required. At least one assertion.
      - type: <enum>
        value: <string>    # For url_contains, url_equals, text_visible, text_not_visible
        selector: <string> # For locator_visible, locator_count
        count: <int>       # For locator_count
        timeoutMs: <int>   # Per-assertion timeout override
        query: <string>    # For db_query
        expected: <string> # For db_query
```

## Assertion Types

| Type | Required Fields | Description |
|------|----------------|-------------|
| `url_contains` | `value` | Current URL includes the value string |
| `url_equals` | `value` | Current URL exactly matches value |
| `text_visible` | `value` | Text is visible on page (fuzzy match) |
| `text_not_visible` | `value` | Text is NOT visible on page |
| `locator_visible` | `selector` | CSS/XPath selector element is visible |
| `locator_count` | `selector`, `count` | Number of matching elements equals count |
| `console_no_errors` | — | No console.error messages during test |
| `network_no_failures` | — | No HTTP 4xx/5xx responses during test |
| `api_response` | (custom) | Custom API response validation |
| `db_query` | `query`, `expected` | Database query returns expected result |
| `log_contains` | `value` | Server log contains the value string |

## Examples

### Login flow with credentials from env

```yaml
cases:
  - id: login-success
    app: main
    route: /login
    task: |
      输入用户名和密码登录。用户名来自 E2E_TEST_USER，密码来自 E2E_TEST_PASSWORD。
      点击登录按钮，等待页面跳转。
    maxSteps: 10
    fixtures:
      user: E2E_TEST_USER
    assertions:
      - type: url_contains
        value: /dashboard
      - type: text_not_visible
        value: 登录失败
      - type: console_no_errors
```

### Page load verification with stored auth

```yaml
cases:
  - id: assets-page-loads
    app: main
    route: /assets
    task: |
      确认资产列表页面已加载，检查是否有资产数据显示。
    maxSteps: 5
    storageState: tests/e2e/page-agent/.auth/main-user.json
    assertions:
      - type: url_contains
        value: /assets
      - type: text_visible
        value: 资产
      - type: network_no_failures
```

### Child app with PIN login

```yaml
cases:
  - id: child-pin-login
    app: child
    route: /
    task: |
      在 PIN 输入页面，依次输入 E2E_CHILD_PIN 中的表情符号。
      确认成功进入儿童主页。
    maxSteps: 12
    fixtures:
      user: E2E_CHILD_USER
    assertions:
      - type: url_contains
        value: /home
      - type: console_no_errors
```

## Validation

Run schema validation before executing tests:

```bash
cd scripts/page-agent-e2e
npx tsx task-schema.ts --validate ../../tests/e2e/page-agent/smoke.yaml
```

Output: `✓ tests/e2e/page-agent/smoke.yaml (3 cases)` or error details.
