# frontend/apps/child/CLAUDE.md

Module-specific guidance for the child-facing Vue 3 + TypeScript app.
See root [`CLAUDE.md`](../../CLAUDE.md) for behavioral guidelines and cross-cutting conventions.

## Quality Commands

Run all commands from `frontend/apps/child/`:

```bash
npm run lint          # ESLint — check for errors and warnings
npm run lint:fix      # ESLint — auto-fix where possible
npm run typecheck     # vue-tsc --noEmit — type check without building
npm run build         # full production build
npm run test:run      # vitest run — run tests once (no watch)
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
├── i18n/          # Localization (zh-CN.ts, en-US.ts)
│   └── locales/
│       ├── zh-CN.ts   # All user-facing strings — add here, never inline
│       └── en-US.ts   # English translations — keep in sync with zh-CN.ts
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

## Design System (DESIGN.md — mandatory)

This app uses the **Clay** design system defined in [`DESIGN.md`](./DESIGN.md). All UI work **must** follow it. Do not invent colors, spacing, typography, or component styles — reference DESIGN.md exclusively.

### Non-negotiable rules

- **Colors** — use only tokens from `DESIGN.md colors`. Never hardcode hex values. Map to CSS variables or Tailwind tokens derived from that palette.
- **Typography** — use only the type scale defined in `DESIGN.md typography` (display-xl → caption-uppercase). Match `fontFamily`, `fontSize`, `fontWeight`, `lineHeight`, `letterSpacing` exactly.
- **Spacing** — use only the spacing scale (`xxs: 4px` → `section: 96px`). No arbitrary pixel values.
- **Border radius** — use only `rounded` tokens (`xs: 6px` → `pill: 9999px`).
- **Components** — buttons, cards, inputs, nav must match the component specs in `DESIGN.md components`. Use the correct variant (e.g. `button-primary` vs `button-secondary` vs `button-on-color`).
- **Feature cards** — use the named color variants (`feature-card-pink`, `feature-card-teal`, `feature-card-lavender`, `feature-card-peach`, `feature-card-ochre`, `feature-card-cream`). Do not create ad-hoc card colors.
- **Canvas background** — default page background is `canvas: #fffaf0`, not white (`#ffffff`).
- **Dark surfaces** — use `surface-dark` / `surface-dark-elevated` for dark-mode or inverted sections; never plain black.

### Before writing any UI component

1. Open `DESIGN.md` and locate the relevant component spec.
2. Apply the exact `backgroundColor`, `textColor`, `rounded`, `padding`, and `typography` values.
3. If a component variant doesn't exist in DESIGN.md, use the closest existing variant and note the gap — do not freestyle.

### Anti-patterns (never do these)

- Hardcoded hex colors not in the DESIGN.md palette
- Font sizes or weights outside the type scale
- Arbitrary border-radius values
- Inventing new component variants without a DESIGN.md entry
- Using `#ffffff` as canvas (correct value is `#fffaf0`)
- Using raw black (`#000000`) — use `ink: #0a0a0a` instead

## Links

- Root [`CLAUDE.md`](../../CLAUDE.md) — behavioral guidelines, cross-cutting conventions
- Main app [`CLAUDE.md`](../main/CLAUDE.md) — same i18n rules, emoji convention reference
- [`DESIGN.md`](./DESIGN.md) — Clay design system (colors, typography, components, spacing)
