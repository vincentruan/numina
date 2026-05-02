# frontend/packages/CLAUDE.md

Shared packages under `frontend/packages/`. All conventions from [`frontend/apps/main/CLAUDE.md`](../apps/main/CLAUDE.md) apply here unless noted otherwise.

## Scope

Packages in this directory are consumed by `frontend/apps/main` and `frontend/apps/child`. Code changes here affect both apps.

## Key Invariants (inherited)

- **i18n required for all UI strings** — no hard-coded Chinese strings in `.vue` or `.ts` files. Define in the consuming app's `src/i18n/locales/*.ts` and pass via props or composable arguments.
- **Emoji convention** — user-facing messages must include emoji prefixes. See main app CLAUDE.md for the full table.
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
- **`<script setup lang="ts">` only** — no Options API, no `defineComponent`.
- **Vant components** — do not import Vant directly in packages; leave that to the consuming app's auto-import setup.

## Quality Commands

Run from `frontend/`:

```bash
npm run typecheck     # type-check all workspaces including packages
```

Or from the package directory directly:

```bash
cd packages/auth && npx tsc --noEmit
```

## Links

- [`frontend/apps/main/CLAUDE.md`](../apps/main/CLAUDE.md) — full conventions, patterns, design system
- Root [`CLAUDE.md`](../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
