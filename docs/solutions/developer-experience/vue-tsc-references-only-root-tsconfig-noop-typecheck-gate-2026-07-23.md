---
title: "vue-tsc references-only root tsconfig makes bare `vue-tsc --noEmit` a silent-pass typecheck gate"
date: 2026-07-23
category: developer-experience
module: frontend
problem_type: developer_experience
component: tooling
severity: high
applies_when:
  - A Vue 3 + TS app uses a solution-style root tsconfig.json with project references
  - The root tsconfig.json has "files": [] and only "references" to tsconfig.app.json / tsconfig.node.json / tsconfig.vitest.json
  - package.json runs bare "vue-tsc --noEmit" (no -p flag) as the typecheck script or CI gate
  - CI typecheck passes green while type errors accumulate unchecked
tags: [vue-tsc, typescript, tsconfig, project-references, typecheck, ci, silent-failure, monorepo, tooling]
---

# vue-tsc `files: []` no-op typecheck gate (silent-pass CI)

## Problem / Context

A CI gate that is supposed to catch type errors was **passing green while checking zero files**. 123 type errors had accumulated in `frontend/apps/main` undetected.

Root cause: the app's root `tsconfig.json` is a **solution-style references-only file**:

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" },
    { "path": "./tsconfig.vitest.json" }
  ]
}
```

The typecheck script was the bare form:

```json
"typecheck": "vue-tsc --noEmit"
```

`vue-tsc --noEmit` with **no `-p` flag** reads the root `tsconfig.json`. Because that file has `"files": []` and only `references`, vue-tsc type-checks **zero files** and exits `0`. Project `references` are a *build orchestration* feature (`tsc -b`); a plain `--noEmit` invocation does **not** follow them. The result is a gate that is green by construction — it can never fail.

This is the same silent-pass failure mode as a test runner configured to match zero test files: the gate exists, runs on every PR, and provides **false confidence**.

## Solution

Point the script at the real config(s) explicitly with `-p`. The config that actually includes `src/**` is `tsconfig.app.json`; the one that includes `tests/**` + `src/**/*.spec.ts` is `tsconfig.vitest.json`:

```json
"typecheck":      "vue-tsc --noEmit -p tsconfig.app.json",
"typecheck:test": "vue-tsc --noEmit -p tsconfig.vitest.json"
```

Two follow-throughs are required for the gate to be real:

1. **Fix the errors the now-real gate surfaces.** Turning the gate on immediately fails the build — in this case 123 pre-existing errors that had been silently passing. Budget for that remediation in the same change.
2. **Wire every config into CI.** Adding `typecheck:test` is not enough if CI only runs `typecheck`. The `frontend-typecheck` job must run both, or test-file type errors still slip through:

   ```yaml
   - name: Type check
     run: pnpm run typecheck && pnpm run typecheck:test
   ```

   Check the config `include`/`exclude` boundaries: `tsconfig.app.json` typically has `"include": ["src/**"]` and `"exclude": ["src/**/*.spec.ts", "src/**/*.test.ts"]`, so it covers **zero** test files. Only `tsconfig.vitest.json` covers tests. Root-level build files (`vite.config.ts`, `vitest.config.ts`, `components.d.ts`) may be covered by *neither* — acceptable if a real breakage fails the build anyway, but know the gap exists.

## Prevention

- **Never run bare `vue-tsc --noEmit` (or `tsc --noEmit`) against a references-only root tsconfig.** If `tsconfig.json` has `"files": []`, the bare command is a no-op. Always pass `-p <config>` targeting a config with a non-empty `include`.
- **Audit the gate, don't assume it.** A green typecheck is not evidence the gate works. Verify by introducing a deliberate type error and confirming the command exits non-zero — or check that the config it reads actually `include`s your sources.
- **One CI step per tsconfig you care about.** If tests matter, the CI job must invoke the test-covering config explicitly; defining the script in package.json without calling it from CI leaves the hole open.
- **Replication risk:** any sibling app scaffolded the same way (e.g. `frontend/apps/child`) has the same trap. Apply the `-p tsconfig.app.json` fix to each, and add a CI job per app — a wired-but-never-run script is the same silent pass.
- **Meta-guard (optional):** add a CI check that fails if vue-tsc reports 0 files checked, so a future regression to a no-op gate is caught.

## Related

- Fix commit: `0dbc1c49` (repair no-op typecheck gate + fix 123 surfaced type errors), CI wiring `fe0dcd72`.
- Supersedes the stale `"typecheck": "vue-tsc --noEmit"` recommendation in `monorepo-module-level-lint-format-typecheck-2026-04-12.md`.
- Money-as-str convention referenced by the surfaced errors: `../best-practices/money-decimal-compute-str-wire-serialization.md`.
