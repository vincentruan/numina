# Test-case groups — parallel run structure

The test cases are organized into **4 groups by state-isolation boundary**, so
that 2-3 agents can run them in parallel without racing on shared browser
state.

> **Shared conventions:** [`../_common.md`](../_common.md) (applies to every
> group).

## Why groups (not flat files)

`bsk` supports **concurrent sessions** (verified: 2 sessions active
simultaneously in `bsk session list`). BUT all sessions share **one browser
profile** — they share `cookie` and `localStorage` **per origin** (verified: a
value written by session A on `about:blank` is readable by session B). So two
agents operating the **same origin's global state** (e.g. `default_currency`)
race; two agents on **different origins** (adult :5173 vs child :5174 in dev)
are isolated.

The groups are cut along those boundaries — not along file count — so parallel
runs are safe by construction, not by luck.

## The 4 groups

| Group | Dir | Files | Session | State domain | Parallel with |
|-------|-----|-------|---------|--------------|---------------|
| **G0** preconditions | [`g0-preconditions/`](./g0-preconditions/) | (Phase 0/1/1.5/2 index) | serial | establishes login | none — runs first |
| **G1** adult-stable | [`g1-adult-stable/`](./g1-adult-stable/) | area2, area3, area6 | `$SID` (adult) | reads global; per-entity writes only | **G3** |
| **G2** adult-currency | [`g2-adult-currency/`](./g2-adult-currency/) | area4 | adult (own) | **mutates `default_currency`** | **G3** |
| **G3** child | [`g3-child/`](./g3-child/) | area1, area5 | `$SID_CHILD` | child origin (isolated in dev) | **G1 or G2** |

## Parallel schedule

```
        ┌── G1 (adult-stable: area2→area3→area6) ──┐
G0 ─────┤                                           ├── G2 (adult-currency: area4)
        └── G3 (child: area1→area5) ────────────────┘
```

- **G0 serial first** — `bsk doctor`, service health, gate, login. Produces
  `$SID` (adult) + `$SID_CHILD` (child, dev) + `SIM_CHILD_NAMES`.
- **G1 ‖ G3 parallel** — the real speedup. Two agents, two sessions, two
  origins (dev). G1 reads adult global state without mutating it; G3 is on the
  isolated child origin.
- **G2 after G1** — G2 flips `default_currency`; must not overlap G1 (both
  adult origin). G2 CAN overlap G3 (child origin isolated).

Net: 3 agents (G1, G3, then G2) cover all 111 cases. Wall-clock ≈ G0 + max(G1,
G3) + G2, instead of G0 + G1 + G2 + G3 sequential.

## Docker vs dev mode

- **dev mode:** adult (:5173) and child (:5174) are **different origins** →
  G1/G2 ‖ G3 parallel is safe. This is the mode the parallel design targets.
- **docker mode:** nginx serves both apps under **one origin** (:80) → adult
  and child share storage → G3 is NOT parallel-safe with G1/G2. In docker, run
  G3 serially with the adult groups (no parallel benefit, but the group
  structure still organizes the run).

## Spawning agents (recommended)

Use the host harness's `Agent` tool (or equivalent) to spawn one agent per
parallel group. Each agent:

1. Receives its group dir + the G0 session ids (`$SID` / `$SID_CHILD`).
2. Reads its group `README.md` for scope + state-domain + run sketch.
3. Drives its cases via `bsk ... --session <id>` (the session from G0).
4. **Does NOT call `bsk session stop` on a shared session** — only the G0 owner
   (or a final cleanup step) stops sessions. An agent that stops a shared
   session breaks the other agents reusing it.
5. Writes its failures to the shared report (`tests/audit-reports/`) with a
   group prefix (e.g. `G1-C2.3`, `G3-C1.10`).

## What NOT to parallelize

- **Two agents on the same group** (e.g. splitting G1 into area2-agent +
  area3-agent). They share one adult session and interleave writes to the same
  AI config / chat threads → race.
- **G1 and G2 concurrently.** Both adult origin; G2 mutates currency.
- **Any adult group alongside G0's login phase.** Login writes
  `localStorage.numina_user`; concurrent adult reads see a half-written state.
