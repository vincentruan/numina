# AI Chat Development Processes

This document captures 5 key development processes for AI chat testing and verification.

## 1. Restart All AI Chat Services

**Purpose:** Start backend, agent, and frontend for local AI chat testing.

**Script:** `scripts/dev/restart-ai-chat-all.sh`

```bash
# Full restart (all services)
./scripts/dev/restart-ai-chat-all.sh

# Skip specific services
./scripts/dev/restart-ai-chat-all.sh --skip-backend
./scripts/dev/restart-ai-chat-all.sh --skip-agent
./scripts/dev/restart-ai-chat-all.sh --skip-frontend
```

**Manual Alternative:**
```bash
# Backend
cd server && uv run uvicorn apps.backend.app.main:app --host 0.0.0.0 --reload --port 8000

# Agent
cd server && uv run uvicorn apps.agent.app.main:app --host 0.0.0.0 --reload --port 8001

# Frontend
cd frontend/apps/main && pnpm dev --host 0.0.0.0
```

**Prerequisites:**
- `server/.env` with `AGENT_INTERNAL_TOKEN`, `AI_ENCRYPTION_KEY`
- Tenant AI resources configured (or model selector will be empty)
- `pnpm install` run in frontend
- `uv sync` run in server

---

## 2. Run AI Chat E2E Tests

**Purpose:** Execute Playwright E2E tests for AI chat parity verification.

**Command:**
```bash
cd tests

# Run all DeerFlow parity tests (requires demouser)
RUN_DEMOUSER_TESTS=1 npx playwright test deerflow-*.spec.ts

# Run specific test file
RUN_DEMOUSER_TESTS=1 npx playwright test deerflow-welcome-state.spec.ts

# Run with AI provider (full streaming tests)
RUN_DEMOUSER_TESTS=1 RUN_AI_TESTS=1 npx playwright test deerflow-streaming-state.spec.ts

# Run visual regression tests
RUN_VISUAL_TESTS=1 npx playwright test visual/deerflow/visual-regression.spec.ts
```

**Test Files:**
| File | Focus |
|------|-------|
| `deerflow-welcome-state.spec.ts` | New chat welcome screen |
| `deerflow-input-box.spec.ts` | Input interactions |
| `deerflow-mode-selection.spec.ts` | Mode selector (闪电/专业) |
| `deerflow-streaming-state.spec.ts` | Streaming response |
| `deerflow-message-rendering.spec.ts` | Message display & actions |
| `deerflow-header-navigation.spec.ts` | Header buttons & navigation |
| `deerflow-responsive-layout.spec.ts` | Viewport testing (375/390/1440) |
| `deerflow-error-states.spec.ts` | Error handling |

---

## 3. Capture Visual Baseline Screenshots

**Purpose:** Update reference screenshots for DeerFlow parity comparison.

**Manual Browser Testing:**
1. Open Chrome DevTools MCP
2. Navigate to DeerFlow reference: https://deerflow.tech/workspace/chats/new
3. Capture screenshots at 375×812, 390×844, 1440×900
4. Navigate to local: http://localhost:5173/ai/chat
5. Capture same states at same viewports

**Screenshot Storage:**
```
docs/screenshots/deerflow-baseline/
├── deerflow-*.png      # DeerFlow reference
└── local-*.png         # Numina local
```

**Playwright Visual Tests:**
```bash
# Update baseline
npx playwright test visual/deerflow/visual-regression.spec.ts --update-snapshots
```

---

## 4. Verify AI Chat State Machine

**Purpose:** Validate state transitions match documented behavior.

**State Machine Doc:** `docs/deerflow-state-machine.md`

**Manual Verification Steps:**

| State | Test Action |
|-------|-------------|
| INIT | Navigate to /ai/chat, observe loading |
| NEW_CHAT | Verify welcome prompt visible |
| INPUT_FOCUS | Click input, verify focus highlight |
| HAS_TEXT | Type text, verify send button enabled |
| SUBMITTING | Click send, observe "发送中" |
| STREAMING | Watch AI response appear |
| COMPLETE | Verify action buttons (复制/重新生成/有帮助) |
| ERROR | Trigger API failure, verify error message |

**Automated Verification:**
```bash
RUN_DEMOUSER_TESTS=1 RUN_AI_TESTS=1 npx playwright test deerflow-streaming-state.spec.ts -g "sending state"
```

---

## 5. Debug History Drawer Vue Errors

**Purpose:** Investigate and fix Vue errors when opening history drawer.

**Current Issue:**
```
[Vue warn]: Unhandled error during execution of render function
  at <VanPopup show=true position="left" ...>
Uncaught (in promise)
```

**Debug Steps:**
1. Open browser DevTools console
2. Navigate to /ai/chat
3. Click "会话历史" button
4. Observe console errors
5. Check van-popup props and transition handling

**Potential Fixes:**
- Verify van-popup destroy-on-close prop
- Check onAfterEnter/onAfterLeave handlers
- Ensure popup state cleanup on close

**Related Files:**
- `frontend/apps/main/src/pages/AIChatPage.vue` - history drawer implementation
- `frontend/apps/main/src/components/ai/HistoryDrawer.vue` - if exists

---

## Quick Reference

| Task | Command |
|------|---------|
| Restart services | `./scripts/dev/restart-ai-chat-all.sh` |
| Run E2E tests | `RUN_DEMOUSER_TESTS=1 npx playwright test deerflow-*.spec.ts` |
| Update visual baseline | `npx playwright test --update-snapshots` |
| View parity matrix | `docs/deerflow-parity-matrix.md` |
| View state machine | `docs/deerflow-state-machine.md` |

---

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `RUN_DEMOUSER_TESTS` | Enable demouser tests | For E2E |
| `RUN_AI_TESTS` | Enable AI provider tests | For streaming tests |
| `RUN_VISUAL_TESTS` | Enable visual regression | For screenshots |
| `AGENT_INTERNAL_TOKEN` | Agent auth token | For agent startup |
| `AI_ENCRYPTION_KEY` | Fernet key for AI config | For agent startup |