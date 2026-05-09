# AI Chat Page "Thinking" State Enhancement Plan

## Context

The user wants to enhance the `/ai/chat` page's AI response interaction to match a DeepSeek-inspired style, with a focus on:

1. **Flowing gradient halo effect** for the "thinking" state (instead of current simple pulse)
2. **Error state with retry button** in the bubble
3. **Smooth transition** from thinking to answer content

The current implementation (AIChatPage.vue, 1465 lines) already handles most requirements:
- User/assistant bubbles with correct alignment
- Phase indicators (connecting/thinking/answering)
- Deep think blocks with shimmer text
- Message actions (copy, regenerate, feedback thumbs)
- Streaming SSE handling
- Light/dark theme via CSS variables
- Abort functionality

**What needs enhancement:**
- The thinking state uses a simple `phase-pulse` animation (8px dot with box-shadow pulse) - needs a flowing gradient halo around the entire bubble
- Error messages show toast but lack an in-bubble retry button
- Transition could be smoother (fade-in for answer content)

## Design Constraints (from DESIGN.md)

- **No brand magenta/orange (#ef2cc1/#fc4c02) as UI colors** - they're illustration only
- Use **lavender (#bdbbff)** as soft accent for thinking effect
- Use **dark-blue-tinted shadows**: rgba(1, 1, 32, 0.1)
- **Sharp radius**: 4px for buttons, 8px for cards
- **Dark surface**: #010120 for dark mode
- Shadows always dark-blue-tinted, never warm-toned
- Mobile-first: touch targets ≥44px

## Implementation Plan

### 1. Add Flowing Gradient Halo for Thinking State

**File**: `frontend/apps/main/src/pages/AIChatPage.vue`

Add CSS for flowing gradient halo animation on assistant bubbles during thinking phase:

```css
/* Thinking halo effect - gradient flows around border */
.bubble.assistant--thinking {
  position: relative;
  overflow: visible;
}

.bubble.assistant--thinking::before {
  content: '';
  position: absolute;
  inset: -2px;
  border-radius: 18px;
  background: conic-gradient(
    from 0deg,
    rgba(189, 187, 255, 0.1),
    rgba(129, 140, 248, 0.3),
    rgba(189, 187, 255, 0.1),
    rgba(129, 140, 248, 0.3),
    rgba(189, 187, 255, 0.1)
  );
  animation: halo-flow 1.5s linear infinite;
  z-index: -1;
  filter: blur(1px);
}

@keyframes halo-flow {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Inner pulse glow */
.bubble.assistant--thinking::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 16px;
  background: radial-gradient(
    circle at center,
    rgba(129, 140, 248, 0.08) 0%,
    transparent 70%
  );
  animation: pulse-glow-inner 1.8s ease-in-out infinite;
  z-index: 0;
}

@keyframes pulse-glow-inner {
  0%, 100% { opacity: 0.2; }
  50% { opacity: 0.6; }
}
```

Apply class `assistant--thinking` when `msg.phase === 'thinking' || msg.phase === 'answering'` (before done).

**Light mode variant**: Use lighter lavender tones, ensure visibility on white.

### 2. Add Error State Retry Button

**Template changes**: Add a retry button inside assistant bubble when `phase === 'error'`:

```vue
<div v-if="msg.role === 'assistant' && msg.phase === 'error'" class="error-retry">
  <button class="retry-btn" @click="onRetryError(idx)">
    <svg><!-- refresh icon --></svg>
    <span>重试</span>
  </button>
</div>
```

**Script changes**: Add `onRetryError(idx)` function:
- Find the preceding user message
- Remove the error assistant message
- Re-send the user's question via `onSend()`

### 3. Smooth Transition from Thinking to Answer

Add CSS transition for content appearance:

```css
.bubble-text--appearing {
  animation: content-fade-in 0.2s ease-out;
}

@keyframes content-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}
```

Apply this class briefly when transitioning from thinking to answering (first token received).

### 4. i18n Keys

Add to `zh-CN.ts`:
```ts
aiChat: {
  retry: '重试',
  retrying: '重新生成中',
  errorRetry: '请求失败，点击重试',
}
```

### 5. Accessibility

- Ensure `prefers-reduced-motion` disables halo animation
- Add `aria-live="polite"` to thinking indicator
- Retry button has clear aria-label

## Critical Files to Modify

1. `frontend/apps/main/src/pages/AIChatPage.vue` (template + script + CSS)
2. `frontend/apps/main/src/i18n/locales/zh-CN.ts` (new keys)
3. `frontend/apps/main/src/i18n/locales/en-US.ts` (new keys)

## Verification

1. Run `npm run typecheck` - ensure no type errors
2. Manual test in browser:
   - Send a message, observe flowing halo during thinking
   - Simulate error (network failure), verify retry button appears
   - Click retry, verify re-generation works
   - Test in both light and dark themes
   - Test on mobile viewport (375px)
   - Test with `prefers-reduced-motion` enabled

## Implementation Order

1. CSS: Add halo animation keyframes and classes
2. Template: Apply thinking class conditionally, add error retry button
3. Script: Add `onRetryError()` function, track appearing state
4. i18n: Add new keys
5. Test and refine