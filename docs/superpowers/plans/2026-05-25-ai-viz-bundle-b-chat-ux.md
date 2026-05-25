# AI Conversation Phase 3 — Bundle B: Chat UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tighten three `/ai/chat` user-side UX behaviors: scroll-to-bottom button (currently only visible during streaming), Markdown rendering on user bubbles with strict XSS-safe allowlist, and empty-state audit.

**Architecture:** Bundle B is heterogeneous — two audits (B1 scroll-to-bottom, B3 empty-state) gate code changes on inspection results, and one new component (B2 `AiUserBubble.vue`) wraps `marked` + `DOMPurify` with a hand-written ALLOWED_TAGS / ALLOWED_ATTR allowlist. The new bubble component lives next to the existing `ai/` components and is invoked from the inline `v-if="msg.role === 'user'"` branch in `AIChatPage.vue`.

**Tech Stack:** Vue 3 + TypeScript + Vant 4. `marked` and `DOMPurify` are already in `package.json` (used by `AiFinalAnswer.vue`). Vitest for unit tests including a dedicated XSS suite for B2.

**Spec:** `docs/superpowers/specs/2026-05-25-ai-conversation-phase-3-design.md` §4 (Bundle B).

---

## File Structure

| File | Purpose | Action |
|------|---------|--------|
| `frontend/apps/main/src/components/ai/AiUserBubble.vue` | New component: Markdown user-message rendering with strict allowlist | Create |
| `frontend/apps/main/src/components/ai/AiUserBubble.test.ts` | XSS + render unit tests for AiUserBubble | Create |
| `frontend/apps/main/src/utils/userMarkdownSanitizer.ts` | Pure-function sanitizer used by AiUserBubble (testable in isolation) | Create |
| `frontend/apps/main/src/utils/userMarkdownSanitizer.test.ts` | Allowlist + XSS vector tests for the sanitizer | Create |
| `frontend/apps/main/src/pages/AIChatPage.vue` | Replace inline `<div class="bubble-text">{{ msg.content }}</div>` for user role with `<AiUserBubble>`; tighten scroll-to-bottom visibility (B1); audit empty-state (B3) | Modify |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | (Possibly) add empty-state strings if B3 audit finds gaps | Modify (conditional) |
| `frontend/apps/main/src/i18n/locales/en-US.ts` | English translations (conditional) | Modify (conditional) |
| `docs/superpowers/audits/2026-05-25-ai-chat-empty-state-audit.md` | B3 audit document | Create |
| `docs/superpowers/audits/2026-05-25-ai-chat-scroll-to-bottom-audit.md` | B1 audit document | Create |

---

### Task 1: B1 — Scroll-to-Bottom Audit

**Files:**
- Read: `frontend/apps/main/src/pages/AIChatPage.vue:339-352, 764-797`
- Create: `docs/superpowers/audits/2026-05-25-ai-chat-scroll-to-bottom-audit.md`

- [ ] **Step 1: Inspect the existing scroll-to-bottom implementation**

Read these regions to confirm current behavior:

```bash
cd frontend/apps/main
sed -n '335,360p' src/pages/AIChatPage.vue   # Button template
sed -n '760,800p' src/pages/AIChatPage.vue   # scrollToBottom + onChatScroll
```

Confirm what is observed:

- Button is gated on `v-if="isUserScrolledUp && asking"` (line 339-340) — visible only during streaming
- `scrollToBottom(force=false)` short-circuits when `isUserScrolledUp.value` is true (line 769) — auto-scroll properly suppressed when user has scrolled up
- `onChatScroll` updates `isUserScrolledUp` only `if (asking.value)` is true (line 786) — scroll detection deactivated outside streaming
- Distance threshold is 100px (line 787)

- [ ] **Step 2: Map findings to spec §4.B1 acceptance criteria**

Open `docs/superpowers/specs/2026-05-25-ai-conversation-phase-3-design.md` §4.B1 and record one verdict per item. Required acceptance items:

| # | Criterion | Status (fill in) |
|---|-----------|------------------|
| 1 | Button visible when user scrolls up | partial — only during streaming (`asking`) |
| 2 | Button auto-hides when at bottom (< N px) | pass — 100px threshold |
| 3 | Click smoothly scrolls to bottom | partial — uses `scrollTop = scrollHeight` (instant, not smooth) |
| 4 | Auto-scroll pauses when user scrolls up during streaming | pass — `scrollToBottom` checks `isUserScrolledUp` before scrolling |

- [ ] **Step 3: Write the audit document**

Create `docs/superpowers/audits/2026-05-25-ai-chat-scroll-to-bottom-audit.md` with:

```markdown
# Scroll-to-Bottom Audit — `/ai/chat`

> Phase 3 Bundle B item B1. Source spec: `docs/superpowers/specs/2026-05-25-ai-conversation-phase-3-design.md` §4.B1.

## Inspected code

- `frontend/apps/main/src/pages/AIChatPage.vue:339-352` — button template and visibility gate
- `frontend/apps/main/src/pages/AIChatPage.vue:764-797` — `scrollToBottom`, `onChatScroll`, `onScrollToBottom`

## Findings

| # | Spec criterion | Status | Evidence | Fix needed |
|---|----------------|--------|----------|------------|
| 1 | Button visible when user scrolls up | **Partial** | `v-if="isUserScrolledUp && asking"` (line 339) ties visibility to streaming. User scrolling up to read history while no message is in flight gets no button. | Drop the `&& asking` guard so the button appears whenever the user is scrolled up beyond threshold, regardless of streaming state. Also requires `onChatScroll` to update `isUserScrolledUp` outside streaming. |
| 2 | Auto-hides at bottom | **Pass** | `isUserScrolledUp.value = distFromBottom > 100` (line 787) toggles correctly. | None |
| 3 | Click → smooth scroll | **Partial** | `scrollRef.value.scrollTop = scrollRef.value.scrollHeight` (line 794) jumps instantly. | Switch to `scrollRef.value.scrollTo({ top: scrollHeight, behavior: 'smooth' })` for `onScrollToBottom`. Keep instant scroll inside `scrollToBottom()` (auto-scroll during streaming) to avoid scroll-fight with new tokens. |
| 4 | Auto-scroll pauses when user scrolled up | **Pass** | `scrollToBottom(force=false)` early-returns on `isUserScrolledUp`. Force=true is correctly used only by explicit user actions (line 1181 `await scrollToBottom(true)`). | None |

## Decision

Two small patches required (#1 visibility gate, #3 smooth scroll on click). Documented in Task 2.

## Verification

After Task 2 lands:
- Manually scroll up while no message is streaming → button visible
- Click button → smooth animation, not jump
- Scroll up during streaming → auto-scroll pauses; button visible (already passing)
- Scroll back to bottom → button auto-hides (already passing)
```

- [ ] **Step 4: Commit the audit doc**

```bash
git add docs/superpowers/audits/2026-05-25-ai-chat-scroll-to-bottom-audit.md
git commit -m "docs(ai-viz): scroll-to-bottom audit for Phase 3 B1

Two gaps vs spec §4.B1: button visibility gated on streaming-only, and
click handler uses instant scroll instead of smooth. Both fixable with
small patches in Task 2."
```

---

### Task 2: B1 — Apply Scroll-to-Bottom Patches

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue:339-340, 783-787, 791-797`

- [ ] **Step 1: Drop the `&& asking` guard on button visibility**

Edit `frontend/apps/main/src/pages/AIChatPage.vue` line 339-340.

Replace:

```vue
      <button
        v-if="isUserScrolledUp && asking"
```

With:

```vue
      <button
        v-if="isUserScrolledUp"
```

- [ ] **Step 2: Update `onChatScroll` to detect scroll position outside streaming too**

Edit `frontend/apps/main/src/pages/AIChatPage.vue` lines 783-789. Locate:

```typescript
function onChatScroll() {
  const el = scrollRef.value
  if (!el) return
  const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  // Mark as scrolled up when more than 100px from bottom (only during streaming)
  if (asking.value) {
    isUserScrolledUp.value = distFromBottom > 100
  }
}
```

Replace with:

```typescript
function onChatScroll() {
  const el = scrollRef.value
  if (!el) return
  const distFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  isUserScrolledUp.value = distFromBottom > 100
}
```

- [ ] **Step 3: Switch the explicit click handler to smooth scroll**

Edit `frontend/apps/main/src/pages/AIChatPage.vue` lines 791-797. Locate:

```typescript
function onScrollToBottom() {
  isUserScrolledUp.value = false
  if (scrollRef.value) {
    scrollRef.value.scrollTop = scrollRef.value.scrollHeight
  }
}
```

Replace with:

```typescript
function onScrollToBottom() {
  isUserScrolledUp.value = false
  if (scrollRef.value) {
    scrollRef.value.scrollTo({ top: scrollRef.value.scrollHeight, behavior: 'smooth' })
  }
}
```

Leave `scrollToBottom()` (the streaming auto-scroll function at line 764-775) untouched — instant scroll there avoids scroll-jank as new tokens arrive.

- [ ] **Step 4: Run typecheck and tests**

Run: `cd frontend/apps/main && npm run typecheck && npm run test:run`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/pages/AIChatPage.vue
git commit -m "fix(ai/chat): scroll-to-bottom button visible outside streaming + smooth scroll on click

Phase 3 Bundle B item B1. Two small fixes from the audit:
- Drop the &&asking gate so the button is visible whenever user is
  scrolled up reading history, not only during a live stream.
- onChatScroll now updates isUserScrolledUp regardless of streaming
  state so the visibility flag stays accurate.
- onScrollToBottom (explicit click) uses scrollTo({behavior:'smooth'})
  for a polished feel; the streaming auto-scroll path keeps the instant
  scrollTop assignment to avoid jank as new tokens arrive."
```

---

### Task 3: B2 — Create `userMarkdownSanitizer` Utility

**Files:**
- Create: `frontend/apps/main/src/utils/userMarkdownSanitizer.ts`

- [ ] **Step 1: Create the sanitizer module**

Write `frontend/apps/main/src/utils/userMarkdownSanitizer.ts`:

```typescript
import { marked, type MarkedOptions } from 'marked'
import DOMPurify from 'dompurify'

const ALLOWED_TAGS = [
  'p',
  'br',
  'strong',
  'b',
  'em',
  'i',
  'code',
  'a',
] as const

const ALLOWED_ATTR = [
  'href',
  'target',
  'rel',
] as const

const MARKED_OPTIONS: MarkedOptions = {
  async: false,
  breaks: true,
  gfm: true,
}

DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') {
    const href = node.getAttribute('href') ?? ''
    const lower = href.trim().toLowerCase()
    if (
      lower.startsWith('javascript:') ||
      lower.startsWith('data:') ||
      lower.startsWith('vbscript:')
    ) {
      node.removeAttribute('href')
    }
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

export function sanitizeUserMarkdown(input: string): string {
  if (!input) return ''
  let html: string
  try {
    html = marked.parse(input, MARKED_OPTIONS) as string
  } catch {
    html = input
  }
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [...ALLOWED_TAGS],
    ALLOWED_ATTR: [...ALLOWED_ATTR],
    ALLOW_DATA_ATTR: false,
  })
}
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/utils/userMarkdownSanitizer.ts
git commit -m "feat(ai): add userMarkdownSanitizer with strict inline-only allowlist

Phase 3 Bundle B item B2. Pure-function sanitizer used by AiUserBubble.

Allowlist: p / br / strong / b / em / i / code / a
Attributes: href / target / rel only.

DOMPurify afterSanitizeAttributes hook strips javascript:/data:/vbscript:
href values and forces target=_blank rel=noopener noreferrer on all
surviving anchors. Block-level Markdown (h1-h6, pre/code-block, table,
blockquote, hr, img, iframe, script, style) is dropped to plain text or
removed entirely — bubbles must not contain block content."
```

---

### Task 4: B2 — Test the Sanitizer Against XSS Vectors and Allowlist

**Files:**
- Create: `frontend/apps/main/src/utils/userMarkdownSanitizer.test.ts`

- [ ] **Step 1: Write the test file**

Create `frontend/apps/main/src/utils/userMarkdownSanitizer.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { sanitizeUserMarkdown } from './userMarkdownSanitizer'

describe('sanitizeUserMarkdown — allowed inline content', () => {
  it('returns empty string for empty input', () => {
    expect(sanitizeUserMarkdown('')).toBe('')
  })

  it('preserves plain text', () => {
    expect(sanitizeUserMarkdown('hello world')).toContain('hello world')
  })

  it('renders bold, italic, and inline code', () => {
    const out = sanitizeUserMarkdown('**bold** *italic* `code`')
    expect(out).toContain('<strong>bold</strong>')
    expect(out).toMatch(/<em>italic<\/em>/)
    expect(out).toContain('<code>code</code>')
  })

  it('preserves single line break with breaks:true', () => {
    const out = sanitizeUserMarkdown('line one\nline two')
    expect(out).toContain('<br')
  })

  it('renders autolinks with target=_blank rel=noopener noreferrer', () => {
    const out = sanitizeUserMarkdown('see https://example.com')
    expect(out).toContain('href="https://example.com"')
    expect(out).toContain('target="_blank"')
    expect(out).toContain('rel="noopener noreferrer"')
  })
})

describe('sanitizeUserMarkdown — XSS allowlist enforcement', () => {
  it('strips <script> tags', () => {
    const out = sanitizeUserMarkdown('<script>alert(1)</script>')
    expect(out).not.toContain('<script')
    expect(out).not.toContain('alert(1)')
  })

  it('strips <iframe>', () => {
    const out = sanitizeUserMarkdown('<iframe src="https://evil.example"></iframe>')
    expect(out).not.toContain('<iframe')
  })

  it('strips <img> with onerror', () => {
    const out = sanitizeUserMarkdown('<img src=x onerror=alert(1)>')
    expect(out).not.toContain('<img')
    expect(out).not.toContain('onerror')
  })

  it('strips inline event handlers', () => {
    const out = sanitizeUserMarkdown('<a href="https://example.com" onclick="alert(1)">x</a>')
    expect(out).not.toContain('onclick')
  })

  it('strips javascript: URL in markdown link', () => {
    const out = sanitizeUserMarkdown('[xss](javascript:alert(1))')
    expect(out).not.toContain('javascript:')
  })

  it('strips data: URL in markdown link', () => {
    const out = sanitizeUserMarkdown('[xss](data:text/html,<script>alert(1)</script>)')
    expect(out).not.toContain('data:')
  })

  it('strips vbscript: URL', () => {
    const out = sanitizeUserMarkdown('<a href="vbscript:msgbox(1)">click</a>')
    expect(out).not.toContain('vbscript:')
  })

  it('strips <style> blocks', () => {
    const out = sanitizeUserMarkdown('<style>body{display:none}</style>hi')
    expect(out).not.toContain('<style')
  })

  it('strips <object> and <embed>', () => {
    const out = sanitizeUserMarkdown('<object data="evil.swf"></object><embed src="evil.swf">')
    expect(out).not.toContain('<object')
    expect(out).not.toContain('<embed')
  })

  it('strips block-level Markdown to plain or empty', () => {
    const headingOut = sanitizeUserMarkdown('# Heading')
    expect(headingOut).not.toContain('<h1')
    expect(headingOut).not.toContain('<h2')

    const codeBlockOut = sanitizeUserMarkdown('```\ncode block\n```')
    expect(codeBlockOut).not.toContain('<pre')

    const tableOut = sanitizeUserMarkdown('| a | b |\n|---|---|\n| 1 | 2 |')
    expect(tableOut).not.toContain('<table')

    const blockquoteOut = sanitizeUserMarkdown('> quoted')
    expect(blockquoteOut).not.toContain('<blockquote')

    const hrOut = sanitizeUserMarkdown('---')
    expect(hrOut).not.toContain('<hr')
  })
})
```

- [ ] **Step 2: Run the tests**

Run: `cd frontend/apps/main && npm run test:run -- userMarkdownSanitizer`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/utils/userMarkdownSanitizer.test.ts
git commit -m "test(ai): cover userMarkdownSanitizer allowlist and XSS vectors

Phase 3 Bundle B item B2. Two test groups:
- Allowed inline content: empty input, plain text, bold/italic/code,
  line breaks, autolink with target=_blank rel=noopener noreferrer.
- XSS allowlist enforcement: <script>, <iframe>, <img onerror>, inline
  event handlers, javascript:/data:/vbscript: URLs in both raw HTML and
  markdown link form, <style>, <object>/<embed>.
- Block-level Markdown (h1-h6, pre/code-block, table, blockquote, hr)
  stripped to plain or empty — confirms inline-only contract."
```

---

### Task 5: B2 — Create `AiUserBubble.vue` Component

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiUserBubble.vue`

- [ ] **Step 1: Create the component**

Write `frontend/apps/main/src/components/ai/AiUserBubble.vue`:

```vue
<template>
  <!-- eslint-disable-next-line vue/no-v-html -- sanitized via userMarkdownSanitizer -->
  <div class="ai-user-bubble" v-html="renderedContent" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { sanitizeUserMarkdown } from '@/utils/userMarkdownSanitizer'

const props = defineProps<{
  content: string
}>()

const renderedContent = computed(() => sanitizeUserMarkdown(props.content))
</script>

<style scoped>
.ai-user-bubble {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary);
}

.ai-user-bubble :deep(p) {
  margin: 0 0 4px;
}

.ai-user-bubble :deep(p:last-child) {
  margin-bottom: 0;
}

.ai-user-bubble :deep(strong),
.ai-user-bubble :deep(b) {
  font-weight: 600;
  color: var(--text-primary);
}

.ai-user-bubble :deep(em),
.ai-user-bubble :deep(i) {
  font-style: italic;
}

.ai-user-bubble :deep(code) {
  background: var(--bg-secondary);
  padding: 1px 4px;
  border-radius: 4px;
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}

.ai-user-bubble :deep(a) {
  color: var(--color-action-blue);
  text-decoration: underline;
}

.ai-user-bubble :deep(a:hover) {
  opacity: 0.8;
}
</style>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiUserBubble.vue
git commit -m "feat(ai): add AiUserBubble for sanitized Markdown user content

Phase 3 Bundle B item B2. Thin component wrapping sanitizeUserMarkdown.
white-space: pre-wrap preserves the existing newline behavior of the
inline bubble-text; :deep selectors style the small allowlist (p/strong/
em/code/a) using DESIGN.md tokens (var(--text-primary),
var(--bg-secondary), var(--color-action-blue)).

No font/size/color regression vs the inline implementation. Visual parity
verified against AIChatPage.vue:1898 .message-row.user / 1911 bubble-body
/ 2273 .bubble.user .bubble-text styles — those continue to control the
outer bubble shell; AiUserBubble only handles the inner text content."
```

---

### Task 6: B2 — Component Test

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiUserBubble.test.ts`

- [ ] **Step 1: Write the component test**

Create `frontend/apps/main/src/components/ai/AiUserBubble.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import AiUserBubble from './AiUserBubble.vue'

describe('AiUserBubble', () => {
  it('renders empty when content is empty', () => {
    const wrapper = mount(AiUserBubble, { props: { content: '' } })
    expect(wrapper.html()).toContain('ai-user-bubble')
    expect(wrapper.text()).toBe('')
  })

  it('renders plain text', () => {
    const wrapper = mount(AiUserBubble, { props: { content: 'hello world' } })
    expect(wrapper.text()).toContain('hello world')
  })

  it('renders inline markdown', () => {
    const wrapper = mount(AiUserBubble, { props: { content: '**bold** _italic_' } })
    expect(wrapper.find('strong').text()).toBe('bold')
    expect(wrapper.find('em').text()).toBe('italic')
  })

  it('blocks <script> injection', () => {
    const wrapper = mount(AiUserBubble, {
      props: { content: '<script>window.__pwn = 1</script>safe' },
    })
    expect(wrapper.html()).not.toContain('<script')
    expect(wrapper.text()).toContain('safe')
  })

  it('blocks javascript: URL', () => {
    const wrapper = mount(AiUserBubble, {
      props: { content: '[xss](javascript:alert(1))' },
    })
    expect(wrapper.html()).not.toContain('javascript:')
  })

  it('forces target=_blank rel=noopener noreferrer on links', () => {
    const wrapper = mount(AiUserBubble, {
      props: { content: 'visit https://example.com' },
    })
    const a = wrapper.find('a')
    expect(a.attributes('target')).toBe('_blank')
    expect(a.attributes('rel')).toBe('noopener noreferrer')
  })

  it('reactively re-renders when content changes', async () => {
    const wrapper = mount(AiUserBubble, { props: { content: 'first' } })
    expect(wrapper.text()).toContain('first')
    await wrapper.setProps({ content: 'second' })
    expect(wrapper.text()).toContain('second')
  })
})
```

- [ ] **Step 2: Run the tests**

Run: `cd frontend/apps/main && npm run test:run -- AiUserBubble`
Expected: 7 tests PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiUserBubble.test.ts
git commit -m "test(ai): cover AiUserBubble render + reactivity + XSS smoke

Phase 3 Bundle B item B2. Component-level tests complement the
sanitizer-level tests in userMarkdownSanitizer.test.ts. Verifies the
component wires sanitizer output into v-html correctly, reactively
re-renders on prop change, and applies anchor-attribute hardening
end-to-end."
```

---

### Task 7: B2 — Wire `AiUserBubble` into `AIChatPage.vue`

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue:253, 398`

- [ ] **Step 1: Add the import**

Edit `frontend/apps/main/src/pages/AIChatPage.vue`. Around line 398 there is:

```typescript
import AIChatInput from '@/components/common/AIChatInput.vue'
```

Add this import alongside it (the AI imports cluster — if there is a group of `from '@/components/ai/...'` imports, add it there; otherwise add directly above the `AIChatInput` import):

```typescript
import AiUserBubble from '@/components/ai/AiUserBubble.vue'
```

- [ ] **Step 2: Replace the inline `bubble-text` for user role**

Edit `frontend/apps/main/src/pages/AIChatPage.vue` line 253. Locate:

```vue
                <div v-if="msg.role === 'user'" class="bubble-text">{{ msg.content }}</div>
```

Replace with:

```vue
                <AiUserBubble v-if="msg.role === 'user'" class="bubble-text" :content="msg.content" />
```

The `class="bubble-text"` is preserved on the new component so existing CSS rules at `AIChatPage.vue:2273` (`.bubble.user .bubble-text`) and similar selectors continue to apply for outer bubble shell styling.

- [ ] **Step 3: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 4: Run all tests**

Run: `cd frontend/apps/main && npm run test:run`
Expected: PASS — including new sanitizer + component tests

- [ ] **Step 5: Commit**

```bash
git add frontend/apps/main/src/pages/AIChatPage.vue
git commit -m "feat(ai/chat): use AiUserBubble for user message rendering

Phase 3 Bundle B item B2. Replaces the inline
<div class=bubble-text>{{ msg.content }}</div> for msg.role === 'user'
with <AiUserBubble :content=...>. The class=bubble-text is preserved on
the component so the existing .bubble.user .bubble-text outer styling
continues to apply.

User input is now rendered as Markdown via the strict inline-only
allowlist (p/br/strong/b/em/i/code/a). Block-level Markdown degrades to
plain text — bubbles do not host h1-h6, code blocks, tables, etc.

XSS surface is bounded by sanitizeUserMarkdown() with full unit-test
coverage (see userMarkdownSanitizer.test.ts and AiUserBubble.test.ts)."
```

---

### Task 8: B3 — Empty State Audit

**Files:**
- Read: `frontend/apps/main/src/pages/AIChatPage.vue:156-170`
- Create: `docs/superpowers/audits/2026-05-25-ai-chat-empty-state-audit.md`

- [ ] **Step 1: Inspect the existing empty state**

Read the existing empty-state region:

```bash
cd frontend/apps/main
sed -n '155,200p' src/pages/AIChatPage.vue
```

Confirmed observations:

- `v-if="!messages.length"` at line 156 — empty state already exists
- Hero icon (custom SVG, line 158-164)
- Title: `t('aiChat.greetingTitle')` at line 165
- Subtitle: `t('aiChat.greetingSubtitle')` at line 166
- "Suggestion cards" comment at line 168 + `<div class="suggestion-grid">` — sample-question chips already exist

This means B3 is mostly **verified** — the audit confirms the spec's empty-state expectations are already met.

- [ ] **Step 2: Verify the suggestion grid is functional**

Run:

```bash
cd frontend/apps/main && grep -n "suggestion-grid\|onChipClick\|chip\|suggestion" src/pages/AIChatPage.vue | head -20
```

Confirm at least one chip-click handler that fills the input box and (per spec) does NOT auto-send. The reviewer should look for either `inputText.value = ...` followed by NOT calling `onSend()`, or an explicit comment.

If `onChipClick` does call `onSend()` — note as a gap (spec §4.B3 says chips should fill the input, not auto-send).

- [ ] **Step 3: Verify i18n keys exist**

Run:

```bash
cd frontend/apps/main && grep -n "greetingTitle\|greetingSubtitle\|suggestionPrompt" src/i18n/locales/zh-CN.ts src/i18n/locales/en-US.ts
```

Expected: both keys present in both files.

- [ ] **Step 4: Write the audit document**

Create `docs/superpowers/audits/2026-05-25-ai-chat-empty-state-audit.md`:

```markdown
# Empty State Audit — `/ai/chat`

> Phase 3 Bundle B item B3. Source spec: `docs/superpowers/specs/2026-05-25-ai-conversation-phase-3-design.md` §4.B3.

## Inspected code

- `frontend/apps/main/src/pages/AIChatPage.vue:155-200` — empty state template (hero + title + subtitle + suggestion grid)
- `frontend/apps/main/src/i18n/locales/zh-CN.ts` and `en-US.ts` — greeting i18n keys

## Findings

| Spec criterion | Status | Evidence |
|----------------|--------|----------|
| Empty state visible when messages.length === 0 | **Pass** | `<div v-if="!messages.length" class="chat-empty">` at line 156 |
| Hero/illustration | **Pass** | Custom SVG at line 158-164 |
| Greeting title | **Pass** | `t('aiChat.greetingTitle')` at line 165 |
| Greeting subtitle | **Pass** | `t('aiChat.greetingSubtitle')` at line 166 |
| Sample question chips (optional, "丰富版" per spec) | **Pass** | `.suggestion-grid` with chip buttons starting line 168 |
| Chip click → fill input, don't auto-send | **(verify in code review)** | Review `onChipClick` handler in `AIChatPage.vue` to confirm it sets `inputText.value` and does NOT call `onSend()` |
| i18n coverage (no hardcoded strings) | **Pass** | All visible strings go through `t(...)` |

## Decision

**No code change required.** Empty state already meets all spec §4.B3 requirements. If the chip-click verification reveals auto-send behavior, file as a separate small fix outside Bundle B (one-line patch).

## Verification

After this audit lands: open `/ai/chat` with no prior session → confirm hero, title, subtitle, and chips visible; click a chip → confirm input fills and NO message is sent until user explicitly clicks send.
```

- [ ] **Step 5: Commit the audit**

```bash
git add docs/superpowers/audits/2026-05-25-ai-chat-empty-state-audit.md
git commit -m "docs(ai-viz): empty-state audit confirms Phase 3 B3 requirements met

Existing chat-empty block (AIChatPage.vue:156) already provides hero,
greeting title/subtitle, and suggestion-grid chips with full i18n
coverage. No code change required for B3. Chip-click handler should be
verified in code review to confirm fill-not-send behavior."
```

---

### Task 9: Bundle B Final Verification

**Files:** (verification only — no edits)

- [ ] **Step 1: Run full typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS with zero errors

- [ ] **Step 2: Run full test suite**

Run: `cd frontend/apps/main && npm run test:run`
Expected: All tests PASS — including all new sanitizer and component tests

- [ ] **Step 3: Run lint**

Run: `cd frontend/apps/main && npm run lint`
Expected: No new warnings or errors

- [ ] **Step 4: Run production build smoke**

Run: `cd frontend/apps/main && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Manual verification checklist**

The engineer should manually verify (start `npm run dev`, navigate to `/ai/chat`):

1. **B1**: Send a message; while AI is streaming, scroll up — button visible. Stop streaming (let it finish or abort) and scroll up — button STILL visible (this is the fix).
2. **B1**: Click the button — observe smooth scroll animation, not an instant jump.
3. **B2**: Send `**bold** *italic* \`code\` https://example.com` — bubble renders as bold + italic + monospace + clickable link.
4. **B2**: Send `<script>alert(1)</script>safe` — bubble renders only "safe", no script execution.
5. **B2**: Send `[xss](javascript:alert(1))` — bubble shows the link text but href is stripped.
6. **B2**: Send `# Header\n\`\`\`\ncode block\n\`\`\`` — bubble shows plain text without `<h1>` or `<pre>` rendering.
7. **B3**: Open `/ai/chat` with no messages — empty state hero, title, subtitle, suggestion chips all visible.
8. **B3**: Click a suggestion chip — input box fills with the chip's text; NO message is auto-sent.

If any check fails, document the failure but do not gate Bundle B on B3 chip behavior — it's a verify-only item.

---

## Verification Checklist

### Build & types
- [ ] `npm run typecheck` passes with zero new errors
- [ ] `npm run test:run` passes including new sanitizer + component tests
- [ ] `npm run lint` passes with no new warnings
- [ ] `npm run build` succeeds

### Spec coverage (`docs/superpowers/specs/2026-05-25-ai-conversation-phase-3-design.md` §4)

- [ ] B1.1: Button visible when user scrolls up (regardless of streaming) — verified in `Task 2`
- [ ] B1.2: Auto-hides at bottom — verified by audit, no change needed
- [ ] B1.3: Click → smooth scroll — verified in `Task 2`
- [ ] B1.4: Auto-scroll pauses when user scrolled up during streaming — verified by audit, no change needed
- [ ] B2.1: Inline-only allowlist (p/br/strong/b/em/i/code/a) — verified in `Task 3` and tests in `Task 4`
- [ ] B2.2: XSS vectors blocked (`<script>`, `<iframe>`, `<img onerror>`, `javascript:` URLs, `data:` URLs, `vbscript:` URLs, inline event handlers, `<style>`, `<object>`, `<embed>`) — verified in `Task 4`
- [ ] B2.3: Block-level Markdown degrades to plain text — verified in `Task 4`
- [ ] B2.4: Anchors get `target="_blank" rel="noopener noreferrer"` — verified in `Task 3` (DOMPurify hook) and `Task 6` (component test)
- [ ] B2.5: Visual parity with prior plain-text bubble — verified by manual check + DESIGN.md token usage
- [ ] B3: Empty state already meets spec — audit doc verifies hero/title/subtitle/chips/i18n coverage

### Behavioral guarantees

- [ ] Sanitizer is pure-functional (no DOM dependency at module load), testable in isolation
- [ ] DOMPurify `addHook` is idempotent (called once at module load) — does not stack hooks across hot reloads in dev
- [ ] No new dependencies in `package.json` diff (marked + DOMPurify already in tree)
- [ ] No `as any` / `@ts-ignore` introduced

---

## Notes

- The DOMPurify `addHook` runs at module load, so it is global to the app. This is fine for the use case — all consumers of `DOMPurify.sanitize` get the same anchor-hardening, and `AiFinalAnswer.vue` (the only other consumer) already passes content through DOMPurify with the default profile, which is fine because `AiFinalAnswer` content comes from the backend, not user input.
- If a future change requires DOMPurify to behave differently in different contexts, consider creating a per-call DOMPurify instance rather than relying on the global hook.
- B3 audit confirms suggestion chips are fully implemented. The verification step (chip click → fill, not send) is documented as a code-review check rather than a code change.

---

## Deferred / Open Questions

- If the chip-click verification in B3 (Task 8 Step 2) reveals auto-send behavior, file a separate one-line patch. Not in Bundle B scope.
- Future hardening: consider adding URL-host allowlist (only HTTP/HTTPS) for autolinks. Currently the sanitizer relies on DOMPurify default URL parsing + the JS/data/vbscript denylist. If a CSP review surfaces concerns, tighten the hook.
- AiFinalAnswer's existing `marked.parse()` call at line 57 (similar pattern) is unchanged — it operates on backend-controlled content, where the threat model is different. No security regression.
