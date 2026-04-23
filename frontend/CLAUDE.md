# frontend/CLAUDE.md

Module-specific guidance for the Vue 3 + TypeScript frontend.
See root [`CLAUDE.md`](../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

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

## Key Invariants

- **Emoji convention** — All user-facing toast messages, confirmation dialogs, and error messages MUST include an emoji prefix via i18n keys. Never hard-code strings directly in Vue files. See Patterns section.
- **Vant components are auto-imported** via `unplugin-vue-components`. Do not manually import them.
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
- **`<script setup lang="ts">` only** — no Options API, no `defineComponent`.
- **Incremental formatting** — run `npm run format` only on files you touch. Do not reformat the entire `src/` in one commit.

## Patterns

### Emoji Convention for User-Facing Messages

| Type | Emoji | Examples |
|------|-------|---------|
| Success | ✅ | `✅ 添加成功`, `✅ 已保存` |
| Failure/Error | ❌ | `❌ 操作失败`, `❌ 登录失败` |
| Warning | ⚠️ | `⚠️ 请先选择资产`, `⚠️ 邀请码无效` |
| Delete | 🗑️ | `🗑️ 已删除` |
| Info/Status | 📡, 🤖, 🔑 | `📡 网络错误`, `🤖 AI 功能未启用` |
| Special | 💰, 🎨, 🔥, 🎉 | `💰 还款成功`, `🎉 注册成功` |

**Implementation rules:**
1. Define emoji-prefixed strings in `src/i18n/locales/*.ts` under `toast` or `errors`
2. Use `t('toast.xxx')` or `t('errors.xxx')` in Vue files — never hard-coded strings
3. Confirmation dialogs use emoji too: `t('toast.confirmDelete', { name })` → `⚠️ 确定要删除「{name}」吗？`
4. Dynamic messages use interpolation: `t('toast.assetDeletedCount', { count: 3 })` → `🗑️ 已删除 3 项资产`

```ts
// ✅ Correct
showToast(t('toast.addSuccess'))        // Shows: ✅ 添加成功

// ❌ Wrong — hard-coded string without emoji
showToast('添加成功')
```

### Adding New Messages

1. Add emoji-prefixed string to `src/i18n/locales/zh-CN.ts` and `en-US.ts` under `toast` or `errors`
2. Use `t('key')` or `t('key', { param })` in the Vue file
3. Run `npm run typecheck` to verify

### Path Alias

`@/` maps to `src/` — configured in both `vite.config.ts` and `tsconfig.app.json`.

## Links

- Root [`CLAUDE.md`](../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Module [`README.md`](./README.md) — quick start, architecture, component structure
