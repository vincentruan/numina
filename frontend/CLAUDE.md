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

- **Vant components are auto-imported** via `unplugin-vue-components` (build tooling). Do not manually import them.
- **Path alias `@/`** maps to `src/`. Configured in both `vite.config.ts` and `tsconfig.app.json`.
- **`<script setup lang="ts">`** only — no Options API, no `defineComponent`.
- **No `as any`, `@ts-ignore`, or `@ts-expect-error`** — fix types properly.
- **Incremental formatting:** format only files you touch. Do not run `npm run format` on the entire repo in a single commit.

## Emoji Convention for User-Facing Messages

**All user-facing toast messages, confirmation dialogs, and error messages must include an emoji prefix.**

This ensures a unified visual style across the app. Emojis provide quick visual cues for message types:

| Type | Emoji | Examples |
|------|-------|----------|
| Success | ✅ | `✅ 添加成功`, `✅ 已保存` |
| Failure/Error | ❌ | `❌ 操作失败`, `❌ 登录失败` |
| Warning | ⚠️ | `⚠️ 请先选择资产`, `⚠️ 邀请码无效` |
| Delete | 🗑️ | `🗑️ 已删除` |
| Info/Status | 📡, 🤖, 🔑 | `📡 网络错误`, `🤖 AI 功能未启用` |
| Special actions | 💰, 🎨, 🔥, 🎉 | `💰 还款成功`, `🎨 主题已更改`, `🔥 连续打卡`, `🎉 注册成功` |

### Implementation Rules

1. **Use i18n keys for all messages** — define emoji-prefixed strings in `src/i18n/locales/*.ts`
2. **No hard-coded emoji strings in Vue files** — all messages should go through `t('toast.xxx')` or `t('errors.xxx')`
3. **Confirmation dialogs use emoji too** — e.g., `t('toast.confirmDelete', { name })` returns `⚠️ 确定要删除「{name}」吗？`
4. **Dynamic messages use interpolation** — `t('toast.assetDeletedCount', { count: 3 })` returns `🗑️ 已删除 3 项资产`

### Example Code

```ts
// ✅ Correct - use i18n with emoji
showToast(t('toast.addSuccess'))        // Shows: ✅ 添加成功
showToast(t('toast.deleteFailed'))      // Shows: ❌ 删除失败

// ❌ Wrong - hard-coded string without emoji
showToast('添加成功')
showToast('删除失败，请重试')

// ✅ Correct - confirmation dialog with emoji
showConfirmDialog({ 
  title: t('common.confirm'), 
  message: t('toast.confirmDelete', { name: asset.name }) 
})

// ❌ Wrong - confirmation without emoji
showConfirmDialog({ 
  title: '确认删除', 
  message: `确定要删除「${asset.name}」吗？` 
})
```

### When Adding New Messages

When adding a new user-facing message, follow this workflow:

1. Add the emoji-prefixed string to `zh-CN.ts` and `en-US.ts` under `toast` or `errors`
2. Use `t('key')` or `t('key', { param })` in the Vue file
3. Run `npm run typecheck` to verify