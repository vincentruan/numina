# G3 — Child app (parallel-safe with G1 / G2)

> **Shared conventions:** [`../../_common.md`](../../_common.md)

## Scope

G3 runs the **child-app cases**. Two files, one child session (`$SID_CHILD`
from G0).

| File | Area | Cases |
|------|------|-------|
| [`area1-child.md`](./area1-child.md) | 1 — Child app (儿童页面优化) | C1.1–C1.17 |
| [`area5-child-navigation.md`](./area5-child-navigation.md) | 5 — Child nav coverage | C5.1–C5.10 |

## State domain

- **Origin:** child (`$CHILD_BASE`, :5174/child/ dev / :80/child/ docker)
- **Auth:** child role (two-step emoji-PIN; see `_common.md` "Child session
  injection (dev mode)")
- **No currency layer** — child app is coin-based (integer ⭐). The Area 4
  currency-switch bug class does NOT apply (verified: no `useCurrency` /
  `MoneyDisplay` imports in child app).

## Parallelism

✅ **Parallel-safe with G1 (adult-stable) AND G2 (adult-currency).**

This is the key enabler of the 4-group design. In **dev mode**, the child app
(:5174) is a **different origin** from the adult app (:5173). Verified: bsk
sessions share `localStorage` **per browser profile / origin**, so a child
session on :5174 does NOT see adult writes on :5173, and vice versa. G3 can run
concurrently with either adult group.

⚠️ **Docker mode caveat:** nginx serves both apps under one origin (:80), so
adult and child share storage. In docker mode, treat G3 as **same-origin as
G1/G2** — do NOT parallelize; run G3 serially alongside the adult groups. The
parallel benefit is dev-mode-only.

## Agent assignment

One agent drives G3 (area1 → area5), sharing `$SID_CHILD`. area1 and area5 both
operate the child origin and interleave child chore/wish state — a second child
agent would race on the same child's coin balance / wish list.

## Run command sketch

```bash
# Assumes G0 produced $SID_CHILD (child session, dev mode) + SIM_CHILD_NAMES.
SID_CHILD="$SID_CHILD_G0"
# area1
bsk navigate "$CHILD_BASE" --session "$SID_CHILD" --wait-until networkidle   # C1.1 home
# ... C1.1–C1.17 ...
# area5 (nav coverage)
# ... C5.1–C5.10 ...
```
