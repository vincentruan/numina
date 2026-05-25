# Empty State Audit — `/ai/chat`

> Phase 3 Bundle B item B3. Source spec: `docs/superpowers/specs/2026-05-25-ai-conversation-phase-3-design.md` §4.B3.

## Inspected code

- `frontend/apps/main/src/pages/AIChatPage.vue:155-200` — empty state template (hero + title + subtitle + suggestion grid)
- `frontend/apps/main/src/pages/AIChatPage.vue:817-820` — `onChipClick` handler
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` and `en-US.ts` — greeting i18n keys

## Findings

| Spec criterion | Status | Evidence |
|----------------|--------|----------|
| Empty state visible when messages.length === 0 | **Pass** | `<div v-if="!messages.length" class="chat-empty">` at line 156 |
| Hero/illustration | **Pass** | Custom SVG at line 158-164 |
| Greeting title | **Pass** | `t('aiChat.greetingTitle')` at line 165 |
| Greeting subtitle | **Pass** | `t('aiChat.greetingSubtitle')` at line 166 |
| Sample question chips (optional, "丰富版" per spec) | **Pass** | `.suggestion-grid` with chip buttons starting line 168 |
| Chip click → fill input, don't auto-send | **Fix applied** | `onChipClick(text)` at line 817-819 originally set `inputText.value = text` then immediately called `onSend()`, which contradicted spec §4.B3. Patched in this audit pass: the `onSend()` call is removed so chip click only populates the input. |
| i18n coverage (no hardcoded strings) | **Pass** | All visible strings go through `t(...)` |

## Decision

The empty-state visual, hero, greeting, suggestion grid, and i18n coverage already meet spec §4.B3. The only deviation was chip click auto-sending. That has been fixed in this audit pass (one-line patch: remove `onSend()` from `onChipClick`). No other code change required.

## Verification

After this audit lands: open `/ai/chat` with no prior session → confirm hero, title, subtitle, and chips visible; click a chip → input fills, NO message is auto-sent until user explicitly clicks send.
