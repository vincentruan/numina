# Browser Driver Reference

> **When to read this file:** Only when you need the exact command syntax for a
> specific browser driver. The main SKILL.md describes the test flow abstractly;
> this file maps each step to the concrete commands for the active driver.

## Driver Detection (Priority Order)

At the start of the sim-test run, detect which browser driver is available:

```bash
# 1. Check browser-use (highest priority)
if command -v browser-use &>/dev/null; then
  BROWSER_DRIVER="browser-use"
  browser-use --doctor 2>/dev/null && echo "browser-use: OK" || echo "browser-use: daemon issue"

# 2. Check bsk (second priority)
elif command -v bsk &>/dev/null; then
  BROWSER_DRIVER="bsk"
  bsk doctor 2>/dev/null && echo "bsk: OK" || echo "bsk: extension issue"

# 3. Check Chrome DevTools MCP (third priority — MCP tools are available if listed)
# Chrome DevTools MCP is available when mcp__chrome-devtools__navigate_page etc. appear
# in the tool list. No CLI check needed — the MCP server handles its own lifecycle.
elif # check if mcp__chrome-devtools__navigate_page is in available tools; then
  BROWSER_DRIVER="chrome-devtools"
  echo "chrome-devtools MCP: OK"

# 4. None available
else
  echo "ERROR: No browser driver found."
  echo "Install browser-use (recommended):"
  echo "  uv tool install browser-use"
  echo "  browser-use --doctor   # verify connection"
  echo ""
  echo "Or install bsk:"
  echo "  See browser-skill skill for install instructions"
  echo ""
  echo "Or configure chrome-devtools MCP server."
  exit 1
fi
```

**If none are available, stop and tell the user:**

> No browser driver detected. Install one to proceed:
> - **browser-use** (recommended): `uv tool install browser-use` then `browser-use --doctor`
> - **bsk**: install browser-skill CLI + extension
> - **Chrome DevTools MCP**: configure the chrome-devtools MCP server in Claude settings

---

## Driver: browser-use (Preferred)

### CLI Invocation

```bash
browser-use <<'PY'
# Python code — helpers are pre-imported
print(page_info())
PY
```

### Session / Tab Lifecycle

```bash
# First navigation for a task: use new_tab()
browser-use <<'PY'
new_tab("http://localhost/")
print(page_info())
PY

# Subsequent navigations in same task: reuse tab
browser-use <<'PY'
goto_url("http://localhost/finance")
wait_for_load()
print(page_info())
PY

# Check current tab / switch tabs
browser-use <<'PY'
print(current_tab())
print(list_tabs())
switch_tab(target)
PY
```

### Observation (Accessibility Tree / Snapshot)

```bash
# Get full accessibility tree (preferred over screenshots)
browser-use <<'PY'
nodes = cdp("Accessibility.getFullAXTree")["nodes"]
# Filter nodes by role/name before printing
for n in nodes:
    role = n.get("role", {}).get("value", "")
    name = n.get("name", {}).get("value", "")
    if role in ("button", "textbox", "link", "heading") and name:
        print(f"{role}: {name} (id={n['backendDOMNodeId']})")
PY
```

### Interaction

```bash
# Click by coordinates (from AX tree box model)
browser-use <<'PY'
q = cdp("DOM.getBoxModel", backendNodeId=node_id)["model"]["content"]
x, y = sum(q[0::2])/4, sum(q[1::2])/4
click_at_xy(x, y)
PY

# Type text
browser-use <<'PY'
type_text("demouser")
PY

# Fill form field (find element, click, type)
browser-use <<'PY'
# Use AX tree to locate, click_at_xy, then type
PY

# Press key
browser-use <<'PY'
press_key("Enter")
PY
```

### Screenshot

```bash
browser-use <<'PY'
screenshot("dogfood-output/c2.1-dashboard.png")
PY
```

### JavaScript Evaluation

```bash
browser-use <<'PY'
result = js("document.title")
print(result)

# Async evaluation
result = js("""(async () => {
  const r = await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    credentials: 'include',
    body: '{"username":"demouser","password":"DemoPass123"}',
  });
  return String(r.status);
})()""")
PY
```

### Wait

```bash
browser-use <<'PY'
import time
time.sleep(2)  # simple wait
# Or poll for condition
wait_for_load()
PY
```

### Cookie / localStorage Manipulation

```bash
browser-use <<'PY'
# Set localStorage
js("localStorage.setItem('numina_user', JSON.stringify({...}))")

# Clear cookies
js("document.cookie.split(';').forEach(c => document.cookie = c.replace(/^ +/, '').replace(/=.*/, '=;expires=' + new Date().toUTCString() + ';path=/'))")

# Clear localStorage
js("localStorage.clear()")
PY
```

---

## Driver: bsk (browser-skill CLI)

### Health Check

```bash
bsk doctor
```

### Session Lifecycle

```bash
SID=$(bsk session start --json | jq -r .session_id)
# ... all commands use --session "$SID" ...
bsk session stop "$SID"   # REQUIRED when done
bsk session stop --all    # emergency cleanup
```

### Core Commands

```bash
bsk navigate <url> --session <id> --wait-until networkidle
bsk snapshot --session <id>                    # aria tree with @e1, @e2 refs
bsk click @eN --session <id>
bsk fill @eN --value <text> --session <id>
bsk select @eN --value <val> --session <id>
bsk press <Key> --session <id>
bsk screenshot --session <id> --out dogfood-output/<name>.png
bsk evaluate --session <id> "<js-expression>"
bsk get-html --session <id>                    # raw HTML (use when snapshot insufficient)
bsk wait-ms <duration>                         # e.g. 2s, 1500
```

### Key Rules

- **Refs invalidate after navigation** — always re-`snapshot` before clicking on a new page
- **Observation priority:** `bsk snapshot` first; escalate to `get-html` or `screenshot` only when snapshot is insufficient
- **Session stop is mandatory** — never rely on idle timeout

---

## Driver: Chrome DevTools MCP

### Available Tools

| Tool | Purpose |
|------|---------|
| `mcp__chrome-devtools__navigate_page` | Navigate to URL |
| `mcp__chrome-devtools__take_snapshot` | Accessibility tree snapshot |
| `mcp__chrome-devtools__click` | Click element |
| `mcp__chrome-devtools__fill` | Fill input field |
| `mcp__chrome-devtools__fill_form` | Fill entire form |
| `mcp__chrome-devtools__type_text` | Type text |
| `mcp__chrome-devtools__press_key` | Press keyboard key |
| `mcp__chrome-devtools__hover` | Hover over element |
| `mcp__chrome-devtools__take_screenshot` | Capture screenshot |
| `mcp__chrome-devtools__evaluate_script` | Execute JavaScript |
| `mcp__chrome-devtools__wait_for` | Wait for condition |
| `mcp__chrome-devtools__list_pages` | List open pages |
| `mcp__chrome-devtools__select_page` | Switch to page |
| `mcp__chrome-devtools__new_page` | Open new page |
| `mcp__chrome-devtools__close_page` | Close page |
| `mcp__chrome-devtools__resize_page` | Set viewport size |
| `mcp__chrome-devtools__emulate` | Device emulation |
| `mcp__chrome-devtools__drag` | Drag and drop |
| `mcp__chrome-devtools__upload_file` | File upload |
| `mcp__chrome-devtools__list_console_messages` | Console logs |
| `mcp__chrome-devtools__list_network_requests` | Network traffic |
| `mcp__chrome-devtools__handle_dialog` | Handle alert/confirm |

### Typical Flow

```
# Navigate
mcp__chrome-devtools__navigate_page(url="http://localhost/", type="url")

# Snapshot (accessibility tree with element refs)
mcp__chrome-devtools__take_snapshot()

# Click / Fill using refs from snapshot
mcp__chrome-devtools__click(element="button[name='submit']")
mcp__chrome-devtools__fill(selector="input[name='username']", value="demouser")

# Screenshot
mcp__chrome-devtools__take_screenshot(filename="dogfood-output/c2.1-dashboard.png")

# Evaluate JS
mcp__chrome-devtools__evaluate_script(expression="document.title")

# Wait
mcp__chrome-devtools__wait_for(text="Dashboard", timeout=5000)
```

### Mobile Viewport (important for Numina)

```
# Set mobile viewport 375×812
mcp__chrome-devtools__resize_page(width=375, height=812)
# Or emulate a device
mcp__chrome-devtools__emulate(device="iPhone 14")
```

---

## Cross-Driver Mapping

| Operation | browser-use | bsk | Chrome DevTools MCP |
|-----------|-------------|-----|---------------------|
| Health check | `browser-use --doctor` | `bsk doctor` | (auto — MCP lifecycle) |
| Open page | `new_tab(url)` | `bsk navigate <url> --session <id>` | `navigate_page(url=)` |
| Re-navigate | `goto_url(url)` | `bsk navigate <url> --session <id>` | `navigate_page(url=)` |
| Snapshot | `cdp("Accessibility.getFullAXTree")` | `bsk snapshot --session <id>` | `take_snapshot()` |
| Click | `click_at_xy(x, y)` | `bsk click @eN --session <id>` | `click(element=)` |
| Fill input | `type_text(text)` | `bsk fill @eN --value --session <id>` | `fill(selector=, value=)` |
| Press key | `press_key(key)` | `bsk press <Key> --session <id>` | `press_key(key=)` |
| Screenshot | `screenshot(path)` | `bsk screenshot --out path` | `take_screenshot(filename=)` |
| Evaluate JS | `js(expr)` | `bsk evaluate --session <id> "expr"` | `evaluate_script(expression=)` |
| Wait | `wait_for_load()` / `time.sleep()` | `bsk wait-ms <dur>` | `wait_for(text=, timeout=)` |
| Set localStorage | `js("localStorage.setItem(...)")` | `bsk evaluate --session <id> "localStorage..."` | `evaluate_script(expression="localStorage...")` |
| Clear cookies | `js("document.cookie...")` | `bsk evaluate --session <id> "..."` | `evaluate_script(expression="...")` |
| Close / stop | (tab managed by daemon) | `bsk session stop <id>` | `close_page()` |

---

## Driver-Specific Notes for Numina Sim-Test

### browser-use Specifics

- **No session management needed** — the daemon manages tabs. Use `new_tab()` once per task, then `goto_url()` for subsequent navigations.
- **AX tree is large** — always filter nodes by role/name before printing (thousands of nodes unfiltered).
- **Coordinate clicks** — `click_at_xy` is the default; works through iframes/shadow DOM.
- **Mobile viewport** — use `resize_page(width=375, height=812)` or `emulate(device="iPhone 14")` for proper mobile layout testing.
- **Background tab scroll** — if `scroll(...)` times out on a background tab, call `activate_tab(current_tab())` to bring it forward, then retry.

### bsk Specifics

- **Session required** — every command after `session start` needs `--session <id>`.
- **@eN refs invalidate** — re-snapshot after every navigation or DOM-changing click.
- **No viewport control** — Agent Window is desktop-sized; note viewport in report.
- **`wait-ms` duration parsing** — narrow set of accepted forms; if rejected, use `--wait-until` on next navigate or poll snapshot.
- **Password-manager conflict** — if `bsk fill` on password field triggers extension hijack, use cookie+localStorage injection fallback (see SKILL.md Phase 2).

### Chrome DevTools MCP Specifics

- **No CLI** — tools are invoked directly as MCP function calls.
- **Mobile emulation** — use `resize_page` or `emulate` for mobile viewport (unlike bsk which lacks this).
- **Network/console** — `list_network_requests` and `list_console_messages` for debugging.
- **Page management** — `list_pages` / `select_page` for multi-tab scenarios (e.g., parallel testing).

---

## Red Lines (All Drivers)

1. **No token theft** — never evaluate JS on sensitive sites to read `localStorage`/cookies/auth headers for exfiltration.
2. **No long borrow** — don't leave tabs open across unrelated tasks.
3. **No skip cleanup** — always close tabs / stop sessions when done.
4. **Snapshot first** — observe via accessibility tree / snapshot before escalating to screenshot or raw HTML.
5. **Evaluate is risky** — use JS evaluation only when snapshot + click/fill cannot suffice; never on credential surfaces.
