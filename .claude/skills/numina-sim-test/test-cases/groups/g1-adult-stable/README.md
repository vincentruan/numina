# G1 — Adult stable (parallel-safe with G3)

> **Shared conventions:** [`../../_common.md`](../../_common.md)

## Scope

G1 runs the **adult-side feature cases that do NOT mutate global settings**.
All three files reuse one adult session (`$SID` from G0).

| File | Area | Cases |
|------|------|-------|
| [`area2-finance.md`](./area2-finance.md) | 2 — Financial management | C2.1–C2.20 |
| [`area3-ai.md`](./area3-ai.md) | 3 — AI (PDF/report/数鸣/chat) | C3.1–C3.20 |
| [`area6-ai-chat-parity.md`](./area6-ai-chat-parity.md) | 6 — AI chat DeerFlow parity | C6.1–C6.27 (D1–D7) |
| [`area7-regression.md`](./area7-regression.md) | 7 — Regression sweep (历史缺陷回归) | R1–R9 |
| [`area8-expanded-features.md`](./area8-expanded-features.md) | 8 — Expanded coverage (Manifesto/盲盒/Baby/Settings) | F.1–F.7 |

## State domain

- **Origin:** adult (`$BASE`, :5173 dev / :80 docker)
- **Auth:** adult `demouser` session from G0 (reused — do NOT re-login)
- **Reads:** assets/liabilities/wishes/AI config
- **Writes:** wish savings records, finance-coach cache, AI chat threads,
  asset-report cache, PDF import (creates assets). These are **per-entity
  writes**, NOT global setting changes — safe to interleave within G1.

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

One agent drives all of G1 sequentially (area2 → area8 → area3 → area6 → area7),
sharing `$SID`. Spawning a second agent to split G1 internally is NOT recommended:
area2/3/6/7/8 share the adult session and interleave writes to the same AI config /
chat threads — a second adult agent would race on those.

> **Recommended run order within G1:** area2 (finance) → area8 (expanded features) →
> area3 (AI) → area6 (AI chat parity) → area7 (regression sweep). Area 7 runs last
> because R6 (auth expiry) destroys the session — run it at the very end.

## Run command sketch

```bash
# Assumes G0 produced $SID (adult session) and AI is enabled.
SID="$SID_G0"   # reuse, do NOT session start a new one
# area2 — financial management
bsk navigate ${BASE} --session "$SID" --wait-until networkidle   # dashboard (C2.1)
# ... C2.1–C2.20 ...
# area8 — expanded features (Manifesto/Blind Box/Baby/Settings)
# ... F.1–F.7 ...
# area3 — AI capabilities (AI must be enabled)
# ... C3.1–C3.20 ...
# area6 — DeerFlow parity
# ... C6.1–C6.27 ...
# area7 — regression sweep (last! R6 destroys session)
# ... R1–R8 ... (R6 last, then re-login if needed)
```
