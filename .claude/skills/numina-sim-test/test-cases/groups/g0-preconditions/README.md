# G0 — Preconditions (serial, runs FIRST)

> **Shared conventions:** [`../../_common.md`](../../_common.md)

## Scope

G0 is the **mandatory serial prefix** every run must complete before any group
(G1/G2/G3) launches. It establishes the authenticated sessions the other groups
consume. It does NOT run any UI test cases — it only verifies the environment
and logs in.

Maps to SKILL.md phases:
- **Phase 0** — `bsk doctor` (verify CLI + extension connected)
- **Phase 1** — service health (adult / child / api UP)
- **Phase 1.5** — precondition gate (demouser family + ≥1 child + assets > 0;
  discovers `SIM_CHILD_NAMES`)
- **Phase 2** — login + session setup (adult cookie+localStorage injection
  fallback; child two-step emoji-PIN for dev mode)

## Session outputs

G0 produces the sessions the parallel groups reuse:

| Output | Used by | How |
|--------|---------|-----|
| `$SID` (adult session) | G1, G2 | reused (same session) |
| `$SID_CHILD` (child session) | G3 | dev mode: separate session on :5174; docker: same as `$SID` |
| `SIM_CHILD_NAMES` | G3 | exported from Phase 1.5 gate |

## Why serial, not parallel

- `bsk doctor` / service health / gate are curl-only — no session needed, fast.
- Login (Phase 2) mutates `localStorage.numina_user` and the httpOnly cookie on
  the adult origin. Running a second login concurrently on the same browser
  profile would race on that storage. Exactly one login per origin.
- The gate must pass before any UI case runs — otherwise assertions fail on
  absent data, not real bugs.

## Run order

```
G0 (serial) → then G1 ‖ G3 (parallel) → then G2 (serial, after G1)
```

See [`../README.md`](../README.md) for the full parallel schedule.
