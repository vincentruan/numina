# G2 — Adult currency-switch (serial, after G1)

> **Shared conventions:** [`../../_common.md`](../../_common.md)

## Scope

G2 runs the **navigation-coverage suite that mutates `default_currency`** —
the global setting that every money display reads. Single file, one adult
session.

| File | Area | Cases |
|------|------|-------|
| [`area4-navigation.md`](./area4-navigation.md) | 4 — Main app nav + currency-switch bug class | C4.0–C4.16 |

## State domain

- **Origin:** adult (`$BASE`)
- **Auth:** adult `demouser` session (can reuse G1's `$SID`, or start fresh)
- **⚠️ Mutates `default_currency`** via Settings → CurrencyPicker (C4.0, C4.11):
  - writes `localStorage.numina_user.default_currency`
  - calls `updateSetting('default_currency', X)` → backend `authStore.fetchMe()`
  - this is a **global, persistent** change visible to every adult page

## Why isolated from G1

This is the **only group that flips the global currency**. If it ran alongside
G1 (which asserts money magnitudes on dashboard/assets/liabilities/wishes), G1's
assertions would see post-switch amounts and fail spuriously. Verified root
cause: bsk sessions share one browser profile's `localStorage`
(`g1-adult-stable` and `g2-adult-currency` would read the same
`numina_user.default_currency`).

C4.0 itself is the **bug-class smoke test** — it deliberately switches currency
and compares magnitudes across pages. It must own the currency state
exclusively.

## Parallelism

✅ **Parallel-safe with G3 (child).** Child origin is isolated; child app has no
currency layer (coin-based). So G2 ‖ G3 is safe.

⚠️ **NOT parallel with G1.** Both read/write the adult origin's global state.
Run G2 **after** G1 completes (or before, then restore CNY before G1).

## Restore discipline

C4.0 / C4.11 end by switching back to CNY and confirming baseline returns. G2's
last step should leave `default_currency` at its pre-run value (CNY by default)
so subsequent runs are not polluted. If G2 is interrupted, the next run's G0
gate or a manual `updateSetting('default_currency','CNY')` must reset it.

## Agent assignment

One agent drives G2 end-to-end. No benefit to splitting — it is a single
601-line file with a single shared currency state.
