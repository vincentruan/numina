# G1 — Adult stable (parallel-safe with G3)

> **Shared conventions:** [`../../_common.md`](../../_common.md)

## Scope

G1 runs the **adult-side feature cases that do NOT mutate global settings**.
All three files reuse one adult session (`$SID` from G0).

| File | Area | Cases |
|------|------|-------|
| [`area2-finance.md`](./area2-finance.md) | 2 — Financial management | C2.1–C2.25 |
| [`area3-ai.md`](./area3-ai.md) | 3 — AI (PDF/report/数鸣/chat) | C3.1–C3.23 |
| [`area6-ai-chat-parity.md`](./area6-ai-chat-parity.md) | 6 — AI chat DeerFlow parity | C6.1–C6.27 (D1–D7) |
| [`area7-regression.md`](./area7-regression.md) | 7 — Regression sweep (历史缺陷回归) | R1–R9 |
| [`area8-expanded-features.md`](./area8-expanded-features.md) | 8 — Expanded coverage (Manifesto/盲盒/Baby/Settings) | F.1–F.12 |
| [`area9-security-notification.md`](./area9-security-notification.md) | 9 — Account security + notification | C9.1–C9.7 |
| [`area11-ai-security-adversarial.md`](./area11-ai-security-adversarial.md) | 11 — AI/agent adversarial security | C11.1–C11.20 |
| [`area12-ai-task-resilience.md`](./area12-ai-task-resilience.md) | 12 — AI task resilience (前端不稳定处理) | C12.1–C12.9 |
| [`area13-ai-asset-report-deep.md`](./area13-ai-asset-report-deep.md) | 13 — AI 资产报告深度验证 | C13.1–C13.5 |
| [`area14-travel.md`](./area14-travel.md) | 14 — Travel module (家庭旅行管理 + 行程规划) | C14.1–C14.40 |
| [`area15-ui-quality.md`](./area15-ui-quality.md) | 15 — UI quality & design system (H5/PWA/深色模式/无障碍) | UIQ.1–UIQ.10 |
| [`area18-learning-os.md`](./area18-learning-os.md) | 18 — Learning OS (家长端 + 端到端闭环) | C18.1–C18.24 |
| [`area20-mcp-external-token.md`](./area20-mcp-external-token.md) | 20 — MCP external API token & governance | M20.1–M20.15 |

## State domain

- **Origin:** adult (`$BASE`, :5173 dev / :80 docker)
- **Auth:** adult `demouser` session from G0 (reused — do NOT re-login)
- **Reads:** assets/liabilities/wishes/AI config
- **Writes:** wish savings records, finance-coach cache, AI chat threads,
  asset-report cache, PDF import (creates assets), trip/expense/split data.
  These are **per-entity writes**, NOT global setting changes — safe to
  interleave within G1.

## Parallelism

✅ **Parallel-safe with G3 (child).** G3 operates on the child origin (:5174
dev), which is a **different origin** → isolated cookie/localStorage
(verified: bsk sessions share storage **per browser profile**, and dev-mode
child is a separate origin). G1 and G3 can run as two concurrent agents.

⚠️ **NOT parallel with G2.** G2 (area4) mutates `default_currency` — a global
setting stored in `localStorage.numina_user` + backend. If G1 ran alongside G2,
G1's money-display assertions would be polluted by G2's currency switch. G2
runs **after** G1 (or before, but never concurrent).

## Agent assignment

One agent drives all of G1 sequentially, sharing `$SID`. Spawning a second agent to split G1 internally is NOT recommended:
all areas share the adult session and interleave writes to the same AI config /
chat threads — a second adult agent would race on those.

> **Recommended run order within G1:** area2 (finance) → area14 (travel) →
> area18 (learning OS) → area8 (expanded features) → area3 (AI) → area6 (AI chat parity) →
> area12 (task resilience) → area15 (UI quality) → area9 (security/notification) → area7 (regression sweep) → area11 (adversarial security) → area20 (MCP token).
> Area 7 runs last-but-three because R6 (auth expiry) destroys the session.
> Area 15 (UI quality) runs before regression since it needs a stable session for
> dark-mode toggling and viewport tests. Area 9 runs after area15 since WebAuthn/2FA
> flows need a stable session. Area 11 uses read-only probes. Area 20 runs last
> since it generates/consumes MCP tokens.

## Run command sketch

```bash
# Assumes G0 produced $SID (adult session) and AI is enabled.
SID="$SID_G0"   # reuse, do NOT session start a new one
# area2 — financial management
bsk navigate ${BASE} --session "$SID" --wait-until networkidle   # dashboard (C2.1)
# ... C2.1–C2.25 ...
# area14 — travel module (trip CRUD, expenses, split, graduation)
# ... C14.1–C14.40 ...
# area18 — learning OS (parent + E2E closed loop)
# ... C18.1–C18.24 ...
# area8 — expanded features (Manifesto/Blind Box/Baby/Settings)
# ... F.1–F.12 ...
# area3 — AI capabilities (AI must be enabled)
# ... C3.1–C3.23 ...
# area6 — DeerFlow parity
# ... C6.1–C6.27 ...
# area13 — AI report deep
# ... C13.1–C13.5 ...
# area12 — AI task resilience
# ... C12.1–C12.9 ...
# area15 — UI quality & design system
# ... UIQ.1–UIQ.10 ...
# area9 — security + notification
# ... C9.1–C9.7 ...
# area7 — regression sweep (R6 destroys session — near last)
# ... R1–R9 ... (R6 last, then re-login if needed)
# area11 — AI adversarial security (read-only probes)
# ... C11.1–C11.20 ...
# area20 — MCP external token & governance
# ... M20.1–M20.15 ...
```
