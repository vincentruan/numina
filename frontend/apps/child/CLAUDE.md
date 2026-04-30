# frontend/apps/child/CLAUDE.md

Module-specific guidance for the child-facing Vue 3 + TypeScript app.
See root [`CLAUDE.md`](../../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

```bash
npm run lint          # ESLint — check for errors and warnings
npm run lint:fix      # ESLint — auto-fix where possible
npm run typecheck     # vue-tsc --noEmit — type check without building
npm run build         # full production build
```

## Tooling

- **ESLint:** flat config at `eslint.config.js`. Vue 3 + typescript-eslint + prettier compat.
- **vue-tsc:** canonical type gate. Run `npm run typecheck` before pushing. Strict mode on.
- **Vant components** are auto-imported via `unplugin-vue-components`. Do not manually import them.

## Directory Structure

```
src/
├── api/           # HTTP request modules
├── components/    # Reusable Vue components
├── i18n/          # Localization (zh-CN.ts)
│   └── locales/
│       └── zh-CN.ts   # All user-facing strings — add here, never inline
├── pages/         # Route-level views
├── router/        # Vue Router config
├── stores/        # Pinia state stores
├── types/         # TypeScript type definitions
└── utils/         # Helper functions
```

## Key Invariants

- **`<script setup lang="ts">` only** — no Options API, no `defineComponent`.
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
- **Vant components are auto-imported** — do not manually import them.

## i18n Rules

**All user-facing strings must go through `t('key')`** — no exceptions.

```ts
// ✅ Correct
showToast(t('toast.drawFailed'))          // defined in zh-CN.ts
{{ t('chore.statusApproved') }}           // template label via i18n

// ❌ Wrong — hard-coded string
showToast('❌ 抽奖失败，请稍后再试')
{{ c.status === 'approved' ? '已完成' : '待审批' }}
```

This applies to:
- `showToast()` calls
- Template ternaries for status labels
- Milestone/achievement label maps
- Any string a child user will see

### Adding New Messages

1. Add the emoji-prefixed string to `src/i18n/locales/zh-CN.ts` under the appropriate section (`toast`, `errors`, `chore`, `blindBox`, etc.)
2. Use `t('section.key')` in the Vue file
3. Run `npm run typecheck` to verify

### Emoji Convention

| Type | Emoji | Examples |
|------|-------|---------|
| Success | ✅ | `✅ 登录成功`, `✅ 已赠出` |
| Failure/Error | ❌ | `❌ 抽奖失败`, `❌ 登录失败` |
| Warning | ⚠️ | `⚠️ 余额不足`, `⚠️ 暂无机会` |
| Lock | 🔒 | `🔒 账号已锁定` |

### i18n Key Sections in `zh-CN.ts`

| Section | Purpose |
|---------|---------|
| `common` | Shared labels (confirm, cancel, loading…) |
| `nav` | Bottom nav labels |
| `auth` | Login/PIN screen text |
| `errors` | Error code → message mapping |
| `toast` | All `showToast()` messages |
| `chore` | Chore status labels (`approved`, `pending_approval`…) |
| `blindBox` | Blind box draw messages |
| `milestone` | Achievement/milestone label map |

## Path Alias

`@/` maps to `src/` — configured in both `vite.config.ts` and `tsconfig.app.json`.

## Links

- Root [`CLAUDE.md`](../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Main app [`CLAUDE.md`](../main/CLAUDE.md) — same i18n rules, emoji convention reference
