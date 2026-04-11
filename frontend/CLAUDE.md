# frontend/CLAUDE.md

Module-specific guidance for the Vue 3 + TypeScript frontend.
See root `CLAUDE.md` for architecture, API patterns, component structure, and style conventions.

## Quality Commands

```bash
npm run lint          # ESLint — check for errors and warnings
npm run lint:fix      # ESLint — auto-fix where possible
npm run format        # Prettier — format all files in src/
npm run typecheck     # vue-tsc --noEmit — type check without building
npm run build         # vue-tsc -b && vite build — full production build
npm run test:run      # vitest run — run tests once (no watch)
```

## Tooling

- **ESLint:** flat config at `eslint.config.js`. Vue 3 + typescript-eslint + prettier compat.
- **Prettier:** config at `.prettierrc`. Single quotes, no semicolons, trailing commas, 100-char width.
- **vue-tsc:** canonical type gate. Run `npm run typecheck` before pushing. Strict mode is on (`tsconfig.app.json`).
- **vitest:** test runner. Tests live in `src/**/*.test.ts` or `src/**/*.spec.ts`.

## Key Conventions

- **Vant components are auto-imported** via `unplugin-vue-components`. Do not manually import them — ESLint is configured to allow this.
- **Path alias `@/`** maps to `src/`. Configured in both `vite.config.ts` and `tsconfig.app.json`.
- **`<script setup lang="ts">`** only — no Options API, no `defineComponent`.
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
- **Incremental formatting:** format only files you touch. Do not run `npm run format` on the entire repo in a single commit.
