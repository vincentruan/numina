# AI Conversation Phase 3 — Bundle C: Agent-Page Coupling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the deferred report-mode + streaming-skeleton in `AiFinalAnswer.vue` and add an Artifact link area beside the final answer, so that agent feature pages (AIReportPage / AIAlertsPage / etc.) can adopt these components in their later Task 10 integration.

**Architecture:** Two surface changes co-located in `AiFinalAnswer.vue`. (1) Re-introduce the previously-stripped `isReport` / `reportTitle` / `reportMeta` props plus a streaming skeleton that renders when `streaming && !content`. (2) Add an `artifacts` prop with a small `<AiArtifactLink>` child component that renders 0..N artifact cards beneath the markdown body and above the actions row. Type contract for the artifact event must be restored on `NormalizedAiEvent` and `NormalizationState` first — round-2 spec claimed these were already in place but they were not actually merged.

**Tech Stack:** Vue 3 + TypeScript + Vant 4 (`van-skeleton` auto-imported). No new deps. The artifact rendering is fixture-driven — the live backend `/ai/chat` does not currently emit artifact events; end-to-end verification waits for backend support and the parallel Task 10 plan that wires `AiFinalAnswer` into the agent feature pages.

**Spec:** `docs/superpowers/specs/2026-05-25-ai-conversation-phase-3-design.md` §5 (Bundle C).

**Dependency:** Bundle C produces a working component contract and fixture-tested behavior. End-to-end visual verification depends on the separate Task 10 plan (agent-page integration) and on backend artifact-event emission — both out of scope here.

---

## File Structure

| File | Purpose | Action |
|------|---------|--------|
| `frontend/apps/main/src/types/agent-stream.ts` | Restore `subagent_update`/`artifact`/`state_snapshot` on `NormalizedAiEvent`; add `Artifact` interface; extend `NormalizationState` with `artifacts` | Modify |
| `frontend/apps/main/src/utils/aiEventNormalizer.ts` | Initialize `state.artifacts = []` in `createNormalizationState`; add no-op routes for `artifact` / `subagent.update` events so unsupported backend events do not silently drop | Modify |
| `frontend/apps/main/src/components/ai/AiArtifactLink.vue` | New small component: single artifact card with icon + title + url-or-path | Create |
| `frontend/apps/main/src/components/ai/AiFinalAnswer.vue` | Restore `isReport`/`reportTitle`/`reportMeta` props; add `artifacts` prop; add streaming skeleton; render `<AiArtifactLink>` row | Modify |
| `frontend/apps/main/src/components/ai/AiArtifactLink.test.ts` | Unit test for artifact card render | Create |
| `frontend/apps/main/src/components/ai/AiFinalAnswer.test.ts` | Unit tests for skeleton, report header, and artifact row visibility | Create |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | Add `aiProcess.artifactsTitle`, `aiProcess.openArtifact`, `aiProcess.copyPath` | Modify |
| `frontend/apps/main/src/i18n/locales/en-US.ts` | English translations | Modify |

---

### Task 1: Restore the Artifact / Subagent / State-Snapshot Contract on `NormalizedAiEvent`

> **Status: COMPLETED in commit `c4a5b3e`.** Verified live: `src/types/agent-stream.ts` and `src/utils/aiEventNormalizer.ts` now expose all 14 spec-declared event variants and the new `Artifact`/`Subagent` interfaces; 10 normalizer unit tests pass at `tests/unit/utils/aiEventNormalizer.test.ts`. Skip Tasks 1 and 2 — proceed directly to Task 3.

**Files:**
- Modify: `frontend/apps/main/src/types/agent-stream.ts:50-91`

The round-2 spec amendment said these event variants were restored, but a fresh read of `frontend/apps/main/src/types/agent-stream.ts:50-60` shows they are NOT in the live `NormalizedAiEvent` union. This task corrects that drift before any UI work.

- [ ] **Step 1: Add `Artifact` interface and `Subagent` interface**

Edit `frontend/apps/main/src/types/agent-stream.ts`. Locate the existing `NormalizedAiEvent` union (lines 50-60). Directly **before** the union, insert:

```typescript
export interface Artifact {
  id: string
  title: string
  url?: string
  path?: string
  kind?: 'report' | 'file' | 'image' | 'link' | 'other'
}

export interface Subagent {
  taskId: string
  status: 'running' | 'done' | 'failed'
  title?: string
  description?: string
  result?: string
  error?: string
}
```

- [ ] **Step 2: Extend `NormalizedAiEvent` union with the three missing variants**

In the same file, replace the existing union (lines 50-60) with:

```typescript
export type NormalizedAiEvent =
  | { type: 'phase_change'; phase: 'connecting' | 'thinking' | 'answering' | 'done' }
  | { type: 'reasoning_delta'; content: string }
  | { type: 'reasoning_done'; elapsedMs: number }
  | { type: 'tool_call'; toolCallId: string; name: string; displayName: string; icon: string; args: Record<string, unknown> }
  | { type: 'tool_running'; toolCallId: string }
  | { type: 'tool_result'; toolCallId: string; success: boolean; summary?: string; error?: string; elapsedMs?: number }
  | { type: 'answer_delta'; content: string }
  | { type: 'answer_done' }
  | { type: 'subagent_update'; subagent: Subagent }
  | { type: 'artifact'; artifact: Artifact }
  | { type: 'state_snapshot'; messages?: unknown[]; artifacts?: Artifact[]; title?: string }
  | { type: 'error'; message: string; code?: string }
  | { type: 'session_end' }
```

- [ ] **Step 3: Extend `NormalizationState` to track artifacts and subagents**

In the same file, replace the existing `NormalizationState` interface (lines 86-91):

```typescript
export interface NormalizationState {
  phase: 'connecting' | 'thinking' | 'answering' | 'done'
  reasoningStartTime: number | null
  answerContent: string
  steps: ProcessStep[]
}
```

With:

```typescript
export interface NormalizationState {
  phase: 'connecting' | 'thinking' | 'answering' | 'done'
  reasoningStartTime: number | null
  answerContent: string
  steps: ProcessStep[]
  artifacts: Artifact[]
  subagents: Map<string, Subagent>
}
```

- [ ] **Step 4: Run typecheck — expect failures we'll fix in Task 2**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: FAIL — `aiEventNormalizer.ts` no longer constructs `artifacts` / `subagents` in `createNormalizationState`. This is intentional; Task 2 fixes it.

- [ ] **Step 5: Do NOT commit yet — chained with Task 2**

The type and state initializer must move together to keep the repo compilable. Hold the staged edit.

---

### Task 2: Update `aiEventNormalizer.ts` to Initialize and Propagate Artifact / Subagent State

> **Status: COMPLETED in commit `c4a5b3e`** (chained with Task 1). The live normalizer initializes `artifacts: []` and `subagents: new Map()` in `createNormalizationState`, handles `subagent.update` with partial-merge semantics, handles `artifact.created` with id-based dedup, and handles `state.snapshot` for history rehydration. Skip — proceed to Task 3.

**Files:**
- Modify: `frontend/apps/main/src/utils/aiEventNormalizer.ts`

- [ ] **Step 1: Update `createNormalizationState`**

Edit `frontend/apps/main/src/utils/aiEventNormalizer.ts`. Locate the `createNormalizationState` function. Replace its returned object with:

```typescript
export function createNormalizationState(): NormalizationState {
  return {
    phase: 'connecting',
    reasoningStartTime: null,
    answerContent: '',
    steps: [],
    artifacts: [],
    subagents: new Map(),
  }
}
```

- [ ] **Step 2: Add no-op routes for backend `artifact` and `subagent.update` events**

In the same file's `normalizeAgentEvent` switch statement, add (or extend, if existing) the following cases. The MVP backend does not emit these events on `/ai/chat`, but routing them through the normalizer means future backend support does not require an adapter change.

Locate the switch in `normalizeAgentEvent`. Append the following cases just before the `default:` (or before the function returns, if there is no `default:`):

```typescript
    case 'artifact':
    case 'artifact.created': {
      const artifactPayload = (event as unknown as { artifact?: Artifact }).artifact
      if (artifactPayload?.id) {
        state.artifacts.push(artifactPayload)
        events.push({ type: 'artifact', artifact: artifactPayload })
      }
      break
    }

    case 'subagent.update':
    case 'subagent_update': {
      const sub = (event as unknown as { subagent?: Subagent }).subagent
      if (sub?.taskId) {
        state.subagents.set(sub.taskId, sub)
        events.push({ type: 'subagent_update', subagent: sub })
      }
      break
    }
```

These cast through `unknown` because the canonical `AgentEvent` interface (line 12-47 of `agent-stream.ts`) does not yet declare `artifact` / `subagent` payloads — backend extensions land later. The `unknown` cast is intentional and bounded; **do not** add `as any`.

If the file does not currently import `Artifact` and `Subagent`, add them:

```typescript
import type {
  AgentEvent,
  NormalizedAiEvent,
  NormalizationState,
  Artifact,
  Subagent,
} from '@/types/agent-stream'
```

- [ ] **Step 3: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS — type errors from Task 1 should now resolve

- [ ] **Step 4: Run tests**

Run: `cd frontend/apps/main && npm run test:run`
Expected: PASS — no regressions in existing aiEventNormalizer tests

- [ ] **Step 5: Commit Tasks 1 + 2 together**

```bash
git add frontend/apps/main/src/types/agent-stream.ts frontend/apps/main/src/utils/aiEventNormalizer.ts
git commit -m "feat(ai): restore artifact/subagent/state_snapshot on NormalizedAiEvent

Phase 3 Bundle C prerequisite. Round-2 spec amendment claimed these were
restored but the live frontend/apps/main/src/types/agent-stream.ts only
had 11 of the 14 spec-required event variants. This patch:

- Adds Artifact and Subagent interfaces
- Extends NormalizedAiEvent union with subagent_update / artifact /
  state_snapshot variants
- Extends NormalizationState with artifacts: Artifact[] and
  subagents: Map<string, Subagent>
- Initializes both fields in createNormalizationState
- Adds no-op routing in normalizeAgentEvent for 'artifact' /
  'artifact.created' / 'subagent.update' / 'subagent_update' so
  future backend events do not silently drop

Live /ai/chat backend does not emit these events today; the type
contract is restored ahead of UI work in subsequent tasks."
```

---

### Task 3: Add i18n Keys for Artifacts

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts:182-198`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts:137-153`

- [ ] **Step 1: Add keys to `zh-CN.ts`**

Edit `frontend/apps/main/src/i18n/locales/zh-CN.ts`. Locate the `aiProcess: {` block at line 182. Append three new keys before the closing brace:

```typescript
    artifactsTitle: '关联资源',
    openArtifact: '打开',
    copyPath: '复制路径',
    pathCopied: '✅ 已复制路径',
```

- [ ] **Step 2: Add keys to `en-US.ts`**

Edit `frontend/apps/main/src/i18n/locales/en-US.ts`. Locate the `aiProcess: {` block at line 137. Append matching keys:

```typescript
    artifactsTitle: 'Related artifacts',
    openArtifact: 'Open',
    copyPath: 'Copy path',
    pathCopied: '✅ Path copied',
```

- [ ] **Step 3: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(ai/i18n): add artifact link keys

Phase 3 Bundle C item C2. Adds:
- artifactsTitle — section header above the artifact link row
- openArtifact — button label for url-bearing artifacts
- copyPath — button label for path-only artifacts
- pathCopied — success toast (emoji-prefixed per project convention)"
```

---

### Task 4: Create `AiArtifactLink.vue` Component

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiArtifactLink.vue`

- [ ] **Step 1: Create the component**

Write `frontend/apps/main/src/components/ai/AiArtifactLink.vue`:

```vue
<template>
  <div class="ai-artifact-link" :class="`kind-${artifact.kind ?? 'other'}`">
    <span class="artifact-icon" aria-hidden="true">{{ kindIcon }}</span>
    <span class="artifact-title">{{ artifact.title }}</span>
    <a
      v-if="artifact.url"
      class="artifact-action"
      :href="artifact.url"
      target="_blank"
      rel="noopener noreferrer"
    >{{ t('aiProcess.openArtifact') }}</a>
    <button
      v-else-if="artifact.path"
      class="artifact-action"
      type="button"
      @click="copyPath"
    >{{ t('aiProcess.copyPath') }}</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import type { Artifact } from '@/types/agent-stream'

const props = defineProps<{
  artifact: Artifact
}>()

const { t } = useI18n()

const kindIcon = computed(() => {
  switch (props.artifact.kind) {
    case 'report':
      return '📊'
    case 'file':
      return '📄'
    case 'image':
      return '🖼️'
    case 'link':
      return '🔗'
    default:
      return '📎'
  }
})

async function copyPath() {
  if (!props.artifact.path) return
  try {
    await navigator.clipboard.writeText(props.artifact.path)
    showToast(t('aiProcess.pathCopied'))
  } catch {
    showToast(t('aiProcess.copyFailed'))
  }
}
</script>

<style scoped>
.ai-artifact-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 4px;
  background: var(--bg-secondary);
  border: 1px solid var(--color-card-border);
  font-size: 13px;
  color: var(--text-primary);
}

.artifact-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.artifact-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-action {
  flex-shrink: 0;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--color-action-blue);
  background: var(--card-bg);
  border: 1px solid var(--color-card-border);
  border-radius: 4px;
  text-decoration: none;
  cursor: pointer;
}

.artifact-action:hover {
  opacity: 0.85;
}

@media (max-width: 768px) {
  .ai-artifact-link {
    padding: 6px 8px;
    font-size: 12px;
  }

  .artifact-action {
    padding: 4px 8px;
    font-size: 11px;
  }
}
</style>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiArtifactLink.vue
git commit -m "feat(ai): add AiArtifactLink card component

Phase 3 Bundle C item C2. Single-row artifact card showing kind icon +
title + action button. Action is 'Open' (target=_blank rel=noopener
noreferrer) when artifact.url is present, else 'Copy path' when
artifact.path is present, else no action button.

Five kind icons (report/file/image/link/other). Mobile-responsive sizing
at 768px breakpoint. Uses DESIGN.md tokens for all colors and 4px
border-radius."
```

---

### Task 5: Test `AiArtifactLink`

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiArtifactLink.test.ts`

- [ ] **Step 1: Write the test**

Create `frontend/apps/main/src/components/ai/AiArtifactLink.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AiArtifactLink from './AiArtifactLink.vue'
import type { Artifact } from '@/types/agent-stream'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      aiProcess: {
        openArtifact: '打开',
        copyPath: '复制路径',
        pathCopied: '✅ 已复制路径',
        copyFailed: '❌ 复制失败',
      },
    },
  },
})

function mountWith(artifact: Artifact) {
  return mount(AiArtifactLink, {
    props: { artifact },
    global: { plugins: [i18n] },
  })
}

describe('AiArtifactLink', () => {
  it('renders title', () => {
    const w = mountWith({ id: 'a1', title: 'Q3 资产报告' })
    expect(w.text()).toContain('Q3 资产报告')
  })

  it('renders Open button as <a> with secure attributes when url is present', () => {
    const w = mountWith({ id: 'a1', title: 'External', url: 'https://example.com' })
    const a = w.find('a')
    expect(a.exists()).toBe(true)
    expect(a.attributes('target')).toBe('_blank')
    expect(a.attributes('rel')).toBe('noopener noreferrer')
    expect(a.text()).toBe('打开')
  })

  it('renders Copy-path button when only path is present', () => {
    const w = mountWith({ id: 'a1', title: 'Local file', path: '/data/report.pdf' })
    const btn = w.find('button')
    expect(btn.exists()).toBe(true)
    expect(btn.text()).toBe('复制路径')
    expect(w.find('a').exists()).toBe(false)
  })

  it('renders no action when neither url nor path is present', () => {
    const w = mountWith({ id: 'a1', title: 'Bare artifact' })
    expect(w.find('a').exists()).toBe(false)
    expect(w.find('button').exists()).toBe(false)
  })

  it('applies kind-* class for known kinds', () => {
    expect(mountWith({ id: '1', title: 'r', kind: 'report' }).classes()).toContain('kind-report')
    expect(mountWith({ id: '1', title: 'f', kind: 'file' }).classes()).toContain('kind-file')
    expect(mountWith({ id: '1', title: 'i', kind: 'image' }).classes()).toContain('kind-image')
    expect(mountWith({ id: '1', title: 'l', kind: 'link' }).classes()).toContain('kind-link')
  })

  it('falls back to kind-other when kind is missing', () => {
    expect(mountWith({ id: '1', title: 'x' }).classes()).toContain('kind-other')
  })
})
```

- [ ] **Step 2: Run the test**

Run: `cd frontend/apps/main && npm run test:run -- AiArtifactLink`
Expected: 6 tests PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiArtifactLink.test.ts
git commit -m "test(ai): cover AiArtifactLink render variants

Phase 3 Bundle C — verifies title rendering, url/path/neither action
variants, secure-anchor attributes, and kind-* class application
for the 5 supported kinds plus the unknown-kind fallback."
```

---

### Task 6: Restore Report Mode + Streaming Skeleton + Artifact Row in `AiFinalAnswer.vue`

**Files:**
- Modify: `frontend/apps/main/src/components/ai/AiFinalAnswer.vue`

- [ ] **Step 1: Restore the report header template**

Edit `frontend/apps/main/src/components/ai/AiFinalAnswer.vue`. Locate the existing template (lines 1-27). Replace the entire `<template>` block with:

```vue
<template>
  <div class="ai-final-answer" :class="{ 'is-streaming': streaming, 'is-report': isReport }">
    <!-- Report header (spec §6.2) — only when isReport -->
    <div v-if="isReport && reportTitle" class="answer-report-header">
      <span class="report-icon" aria-hidden="true">📊</span>
      <span class="report-title">{{ reportTitle }}</span>
      <span v-if="reportMeta?.generatedAt" class="report-meta">{{ reportMeta.generatedAt }}</span>
    </div>

    <!-- Streaming skeleton (spec §6.1): rendered when streaming and no content yet -->
    <div v-if="streaming && !content" class="answer-skeleton" aria-hidden="true">
      <van-skeleton :row="3" row-width="100%" animate />
      <van-skeleton :row="1" row-width="60%" animate />
    </div>

    <!-- Answer content -->
    <div v-else ref="contentRef" class="answer-content">
      <!-- eslint-disable-next-line vue/no-v-html -- sanitized via DOMPurify -->
      <div class="answer-markdown" v-html="renderedContent" />
      <span v-if="streaming" class="answer-cursor" aria-hidden="true">▋</span>
    </div>

    <!-- Artifact row (spec §3.0 / Bundle C C2) — only when artifacts exist -->
    <div v-if="!streaming && artifacts && artifacts.length > 0" class="answer-artifacts">
      <p class="artifacts-title">{{ t('aiProcess.artifactsTitle') }}</p>
      <div class="artifacts-list">
        <AiArtifactLink
          v-for="artifact in artifacts"
          :key="artifact.id"
          :artifact="artifact"
        />
      </div>
    </div>

    <!-- Actions -->
    <div v-if="!streaming && showActions" class="answer-actions">
      <button class="action-btn" @click="copyContent">
        <van-icon name="description" />
        <span>{{ t('aiProcess.copy') }}</span>
      </button>
      <button v-if="showRegenerate" class="action-btn" @click="emit('regenerate')">
        <van-icon name="refresh" />
        <span>{{ t('aiProcess.regenerate') }}</span>
      </button>
    </div>
  </div>
</template>
```

- [ ] **Step 2: Restore the report-mode props and add `artifacts` prop in `<script setup>`**

In the same file, locate the existing `defineProps` (around line 39-44):

```typescript
const props = defineProps<{
  content: string
  streaming?: boolean
  showActions?: boolean
  showRegenerate?: boolean
}>()
```

Replace with:

```typescript
const props = defineProps<{
  content: string
  streaming?: boolean
  showActions?: boolean
  showRegenerate?: boolean
  isReport?: boolean
  reportTitle?: string
  reportMeta?: { generatedAt?: string; itemCount?: number }
  artifacts?: Artifact[]
}>()
```

Add the import for `Artifact` and `AiArtifactLink` near the existing imports (near line 30-34):

```typescript
import AiArtifactLink from './AiArtifactLink.vue'
import type { Artifact } from '@/types/agent-stream'
```

- [ ] **Step 3: Remove the now-stale TODO(phase-3) markers**

Delete the comment block at lines 3-6 inside the template:

```vue
    <!-- TODO(phase-3): restore report header when agent feature pages are integrated.
         Spec §6.2 / §6.3 use isReport + reportTitle + reportMeta to surface a
         report-styled header above the markdown body on AIReportPage et al.
         Stripped for the chat-only MVP because no caller currently passes them. -->
```

Delete the comment block at lines 36-38 inside `<script setup>`:

```typescript
// TODO(phase-3): add isReport / reportTitle / reportMeta props back here when
// agent feature pages (AIReportPage etc.) integrate AiFinalAnswer. See
// spec §6.2 / §6.3 for the report-mode contract.
```

Delete the comment block at lines 95-98 inside `<style scoped>`:

```css
/* TODO(phase-3): restore .is-report, .answer-report-header, .report-icon,
   .report-title, .report-meta styles when AiFinalAnswer is used in agent
   feature pages (spec §6.2 / §6.3). Stripped because the report-mode
   template was stripped from AiFinalAnswer for the chat-only MVP. */
```

- [ ] **Step 4: Add styles for report header, skeleton, and artifact row**

In the same file's `<style scoped>` block, locate the `.ai-final-answer { ... }` rule (line 88-93). After the existing rule and `.answer-content { ... }` rule (around line 100-104), add:

```css
.is-report {
  padding: 16px;
  box-shadow: 0 2px 8px rgba(1, 1, 32, 0.1);
}

.answer-report-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--separator);
  margin-bottom: 12px;
}

.report-icon {
  font-size: 18px;
  background: var(--color-success);
  color: #ffffff;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.report-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.report-meta {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.answer-skeleton {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 0;
}

.answer-artifacts {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--separator);
}

.artifacts-title {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--text-secondary);
}

.artifacts-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

@media (max-width: 768px) {
  .is-report {
    padding: 12px;
  }

  .report-title {
    font-size: 14px;
  }

  .report-icon {
    width: 28px;
    height: 28px;
    font-size: 16px;
  }

  .answer-artifacts {
    margin-top: 10px;
    padding-top: 10px;
  }
}
```

- [ ] **Step 5: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 6: Run lint**

Run: `cd frontend/apps/main && npm run lint`
Expected: PASS — no new warnings

- [ ] **Step 7: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiFinalAnswer.vue
git commit -m "feat(ai): restore report-mode props + streaming skeleton + artifact row in AiFinalAnswer

Phase 3 Bundle C items C1 and C2.

Restored (previously stripped in commit 73a347c with TODO(phase-3) markers):
- isReport / reportTitle / reportMeta props
- .answer-report-header template
- .is-report / .answer-report-header / .report-icon / .report-title /
  .report-meta CSS, using DESIGN.md tokens (var(--color-success),
  var(--separator), var(--text-primary), 8px radius for the icon)

New for streaming skeleton (C1):
- v-if='streaming && !content' branch renders <van-skeleton> rows so
  agent feature pages with multi-second LLM warmup show motion before
  first token arrives. The instant first token arrives, the skeleton
  unmounts and the markdown div with cursor takes over (no double-render).

New for artifact row (C2):
- artifacts?: Artifact[] prop
- Renders an .answer-artifacts section between markdown body and actions
  iff !streaming && artifacts.length > 0
- Each artifact renders via <AiArtifactLink> child component
- 0 artifacts → section completely unmounts (no empty container)

All TODO(phase-3) markers removed."
```

---

### Task 7: Component Tests for `AiFinalAnswer`

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiFinalAnswer.test.ts`

- [ ] **Step 1: Write the test**

Create `frontend/apps/main/src/components/ai/AiFinalAnswer.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AiFinalAnswer from './AiFinalAnswer.vue'
import type { Artifact } from '@/types/agent-stream'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      aiProcess: {
        copy: '复制',
        regenerate: '重新生成',
        copySuccess: '✅ 已复制',
        copyFailed: '❌ 复制失败',
        artifactsTitle: '关联资源',
        openArtifact: '打开',
        copyPath: '复制路径',
        pathCopied: '✅ 已复制路径',
      },
    },
  },
})

function mountWith(props: Record<string, unknown>) {
  return mount(AiFinalAnswer, {
    props,
    global: { plugins: [i18n] },
  })
}

describe('AiFinalAnswer — streaming skeleton', () => {
  it('renders skeleton when streaming and no content', () => {
    const w = mountWith({ content: '', streaming: true })
    expect(w.find('.answer-skeleton').exists()).toBe(true)
    expect(w.find('.answer-content').exists()).toBe(false)
  })

  it('switches to markdown content the moment first token arrives', () => {
    const w = mountWith({ content: 'first', streaming: true })
    expect(w.find('.answer-skeleton').exists()).toBe(false)
    expect(w.find('.answer-content').exists()).toBe(true)
    expect(w.find('.answer-cursor').exists()).toBe(true)
  })

  it('shows neither skeleton nor cursor when not streaming', () => {
    const w = mountWith({ content: 'final answer', streaming: false })
    expect(w.find('.answer-skeleton').exists()).toBe(false)
    expect(w.find('.answer-cursor').exists()).toBe(false)
    expect(w.find('.answer-content').exists()).toBe(true)
  })
})

describe('AiFinalAnswer — report header', () => {
  it('does not render header by default', () => {
    const w = mountWith({ content: 'x' })
    expect(w.find('.answer-report-header').exists()).toBe(false)
  })

  it('renders header when isReport=true and reportTitle is set', () => {
    const w = mountWith({ content: 'x', isReport: true, reportTitle: 'Q3 报告' })
    expect(w.find('.answer-report-header').exists()).toBe(true)
    expect(w.find('.report-title').text()).toBe('Q3 报告')
  })

  it('omits the title element if reportTitle is missing', () => {
    const w = mountWith({ content: 'x', isReport: true })
    expect(w.find('.answer-report-header').exists()).toBe(false)
  })

  it('shows generatedAt meta when provided', () => {
    const w = mountWith({
      content: 'x',
      isReport: true,
      reportTitle: 'r',
      reportMeta: { generatedAt: '2026-05-25 10:00' },
    })
    expect(w.find('.report-meta').text()).toBe('2026-05-25 10:00')
  })
})

describe('AiFinalAnswer — artifact row', () => {
  const fixtures: Artifact[] = [
    { id: '1', title: 'Report PDF', kind: 'report', url: 'https://example.com/r.pdf' },
    { id: '2', title: 'Local data', kind: 'file', path: '/data/x.json' },
    { id: '3', title: 'Bare', kind: 'other' },
  ]

  it('does not render artifact section when artifacts is undefined', () => {
    const w = mountWith({ content: 'x', streaming: false })
    expect(w.find('.answer-artifacts').exists()).toBe(false)
  })

  it('does not render artifact section when artifacts is empty', () => {
    const w = mountWith({ content: 'x', streaming: false, artifacts: [] })
    expect(w.find('.answer-artifacts').exists()).toBe(false)
  })

  it('renders one AiArtifactLink per artifact when artifacts is non-empty', () => {
    const w = mountWith({ content: 'x', streaming: false, artifacts: fixtures })
    const items = w.findAll('.ai-artifact-link')
    expect(items).toHaveLength(3)
    expect(items[0].text()).toContain('Report PDF')
    expect(items[2].text()).toContain('Bare')
  })

  it('does not render artifact section while streaming', () => {
    const w = mountWith({ content: 'x', streaming: true, artifacts: fixtures })
    expect(w.find('.answer-artifacts').exists()).toBe(false)
  })
})
```

- [ ] **Step 2: Run the test**

Run: `cd frontend/apps/main && npm run test:run -- AiFinalAnswer`
Expected: all tests PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiFinalAnswer.test.ts
git commit -m "test(ai): cover AiFinalAnswer skeleton + report header + artifact row

Phase 3 Bundle C — three test groups:
- Streaming skeleton: visible when streaming && !content; replaced by
  markdown the instant first token arrives; absent when not streaming.
- Report header: hidden by default; shown only when isReport && reportTitle;
  generatedAt meta renders from reportMeta.generatedAt.
- Artifact row: hidden when undefined/empty/streaming; shows one
  AiArtifactLink per artifact when populated and not streaming."
```

---

### Task 8: Bundle C Final Verification

**Files:** (verification only — no edits)

- [ ] **Step 1: Run full typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS with zero errors

- [ ] **Step 2: Run full test suite**

Run: `cd frontend/apps/main && npm run test:run`
Expected: All tests PASS — Bundle C added new tests across `AiArtifactLink.test.ts` and `AiFinalAnswer.test.ts`; no existing tests regress

- [ ] **Step 3: Run lint**

Run: `cd frontend/apps/main && npm run lint`
Expected: No new warnings or errors

- [ ] **Step 4: Run production build smoke**

Run: `cd frontend/apps/main && npm run build`
Expected: Build succeeds

- [ ] **Step 5: Manual verification (fixture-driven, no live backend)**

Bundle C does not change any live page. End-to-end verification waits for Task 10 (agent-page integration). To smoke-test the components manually before Task 10 lands, the engineer can temporarily add a fixture invocation inside `/ai/chat`:

1. In `AIChatPage.vue`, find the existing `<AiFinalAnswer>` invocation
2. Temporarily add hardcoded props: `:is-report="true"` `report-title="测试报告"` `:report-meta="{ generatedAt: '2026-05-25 10:00' }"` `:artifacts="[{ id: 'x', title: '测试 PDF', kind: 'report', url: 'https://example.com' }]"`
3. Reload, send a message, observe that report header + artifact row render after streaming completes
4. **Revert the temporary fixture before committing** — these props should not be live in `/ai/chat` until Task 10

If skeleton needs visual verification, simulate slow first-token by adding `await new Promise(r => setTimeout(r, 2000))` before pushing the first token in the stream handler. Revert after verification.

These manual checks are documented but not gated — Bundle C ships as a unit-tested component contract; the live integration is Task 10's responsibility.

---

## Verification Checklist

### Build & types
- [ ] `npm run typecheck` passes with zero new errors
- [ ] `npm run test:run` passes including all new tests
- [ ] `npm run lint` passes with no new warnings
- [ ] `npm run build` succeeds

### Spec coverage (`docs/superpowers/specs/2026-05-25-ai-conversation-phase-3-design.md` §5)

- [ ] C1.1: Skeleton visible when `streaming && !content` — verified in `AiFinalAnswer.test.ts`
- [ ] C1.2: Skeleton hidden when `streaming && content.length > 0` — verified in `AiFinalAnswer.test.ts`
- [ ] C1.3: Report header (icon + title + generatedAt) restored — verified in `AiFinalAnswer.test.ts`
- [ ] C1.4: `isReport` / `reportTitle` / `reportMeta` props restored, no longer TODO(phase-3) — verified by file diff
- [ ] C2.1: Artifact row renders 1..N artifacts when present — verified in `AiFinalAnswer.test.ts`
- [ ] C2.2: 0 artifacts → no empty container — verified in `AiFinalAnswer.test.ts`
- [ ] C2.3: URL-bearing artifact → `target="_blank" rel="noopener noreferrer"` — verified in `AiArtifactLink.test.ts`
- [ ] C2.4: Path-only artifact → "Copy path" button — verified in `AiArtifactLink.test.ts`
- [ ] C2.5: DESIGN.md token usage (CSS variables, 4px/8px radius, `rgba(1, 1, 32, 0.1)` shadow) — verified by code review
- [ ] Type contract: `NormalizedAiEvent` has `subagent_update` / `artifact` / `state_snapshot`; `NormalizationState` has `artifacts` and `subagents` — verified by file diff

### Behavioral guarantees

- [ ] `artifacts` prop is optional — `AiFinalAnswer` renders unchanged when caller does not pass it
- [ ] `isReport` prop is optional with default false — chat-only callers see no header
- [ ] Skeleton uses `van-skeleton` (auto-imported, no manual import needed)
- [ ] No live-page behavior change in `/ai/chat` (caller does not yet pass new props)
- [ ] No new dependencies in `package.json` diff
- [ ] No `as any` / `@ts-ignore` introduced (single intentional `as unknown as { artifact?: Artifact }` in normalizer is bounded to event-payload extraction)

---

## Notes

- Bundle C ships a working **component contract**. End-to-end visual proof requires both Task 10 (agent-page integration plan) AND backend artifact-event emission. Both are explicitly out of scope here per the spec §5 dependency note.
- The `unknown` cast in `aiEventNormalizer.ts` Task 2 is the one place where the adapter steps slightly beyond the canonical `AgentEvent` interface. It is bounded to extracting the typed payload from the still-typeless event field; once the backend's `AgentEvent` interface gains `artifact` / `subagent` fields, the cast can be removed in a follow-up patch.
- The streaming skeleton uses `van-skeleton` per the existing `DashboardSkeleton.vue` pattern (`frontend/apps/main/src/components/dashboard/DashboardSkeleton.vue`). The 3-row + 1-row split is a heuristic for "report-like" content shape; agent pages may pass their own skeleton in a future iteration if a more specific shape is needed.

---

## Deferred / Open Questions

- **Task 10 — agent-page integration.** Out of scope for Bundle C. Five pages (`AIReportPage`, `AIAlertsPage`, `AIDisposalPage`, `AILiabilityAdvisorPage`, `AIAllocationPage`) need their own plan to swap `TaskConsole` for `<AiProcessBlock>` and `<AiFinalAnswer>` invocations. That plan should reference Bundle C completion as a prerequisite.
- **Backend artifact event support.** The `/ai/chat` backend does not currently emit artifact events. UI is fixture-tested but cannot be end-to-end verified until backend emission lands.
- **`AiFinalAnswer` `scrollIntoView` cleanup.** Round-3 review left this on the deferred list. The watch-and-scroll behavior at lines 65-75 of the current file is preserved unchanged in this bundle. If it produces fixed-header jumps on agent pages during Task 10 integration, that fix lands there.
- **Subagent step rendering inside `AiProcessBlock`.** `ProcessStep` union still only has `reasoning` and `tool_call` variants (matching MVP scope). Adding a `subagent` variant requires UI work in `AiProcessBlock.vue` and is left to Task 10 if backend subagent events become a real consumer.
