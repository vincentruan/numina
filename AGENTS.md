# AGENTS.md

Codex execution entry for this repository.

## Source of Truth

- Primary rules: [`CLAUDE.md`](./CLAUDE.md)
- Module rules:
  - [`backend/CLAUDE.md`](./backend/CLAUDE.md)
  - [`frontend/packages/CLAUDE.md`](./frontend/packages/CLAUDE.md)
  - [`frontend/apps/main/CLAUDE.md`](./frontend/apps/main/CLAUDE.md)
  - [`frontend/apps/child/CLAUDE.md`](./frontend/apps/child/CLAUDE.md)
  - [`agent/CLAUDE.md`](./agent/CLAUDE.md)
  - [`site/CLAUDE.md`](./site/CLAUDE.md)

If any instruction conflicts, follow the closest module `CLAUDE.md`, then root `CLAUDE.md`.

## Codex Workflow Contract (No Duplication)

1. Read this file, then load the relevant `CLAUDE.md` files before editing.
2. Keep changes minimal and scoped; do not refactor unrelated code.
3. Verify only with commands defined in the relevant `CLAUDE.md` (module scope first).
4. In reports, state: changed files, verification commands run, and unresolved risks.

Do not copy conventions into this file; update `CLAUDE.md` instead.
