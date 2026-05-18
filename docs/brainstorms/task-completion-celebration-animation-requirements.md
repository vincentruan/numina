# Task Completion Celebration Animation

## Summary

When a child opens the app and discovers newly-approved tasks (approval happened while they were away), trigger a celebration animation: custom SVG stars fly toward the balance display with a random encouraging phrase. This creates a tangible reward moment that connects "I did chores" → "I earned stars" → "I feel good."

## Problem

Currently, task completion has no emotional feedback. When a child marks a task complete, the only change is a status badge swap (`available` → `pending_approval`). When the parent later approves, the child sees nothing — the task silently appears as "approved" if they happen to check. This makes the reward feel disconnected and anticlimactic.

## User Story

**As a 4-12 year old child,** when I open the app and find that my parents approved my chores, I want to see a celebration that makes me feel proud and excited — not just silently updated status badges.

**As a parent,** I want my approval to create a moment of joy for my child, reinforcing that chores are rewarded and worth doing.

## Scope

### In Scope

- Celebration animation triggered on app open when newly-approved tasks exist
- Flying stars (custom SVG) from task positions toward balance display
- Random encouraging phrase displayed during animation
- Merged summary when multiple tasks approved at once
- Client-side tracking of "celebrated vs pending celebration" approvals

### Out of Scope (for this iteration)

- Swipe-to-complete gesture
- Sound/haptic feedback layer
- Mystery bonus rewards
- Celebration on immediate task submission (before approval)
- Real-time push notification triggering

## Trigger Conditions

| Condition | Behavior |
|-----------|----------|
| Child opens app + ≥1 newly-approved task not yet celebrated | Trigger celebration animation immediately |
| Child opens app + no new approvals | No celebration, normal app state |
| Multiple tasks approved in same batch | Single merged celebration showing total count and stars |
| All approved tasks already celebrated | No repeat celebration |

**"Newly-approved" definition:** Tasks whose status transitioned from `pending_approval` → `approved` since the last time the child saw the celebration for those tasks.

## Animation Choreography

### Sequence (2-3 seconds total)

1. **Fade overlay (0-0.2s)** — Semi-transparent canvas overlay appears, dimming the background
2. **Phrase appear (0.2-0.4s)** — Random encouraging phrase fades in at screen center, e.g., "太棒了！"
3. **Stars launch (0.3-1.5s)** — 3-6 stars (SVG with glow) animate from approximate task card positions, flying in curved paths toward the hero balance card
4. **Balance pulse (1.5-2s)** — Balance display briefly pulses/glows as stars "arrive"
5. **Summary card (1.8-2.5s)** — If multiple tasks: a summary card appears showing "X个任务通过！获得 Y ⭐"
6. **Fade out (2.5-3s)** — All animation elements fade out, overlay disappears, app returns to normal state

### Visual Elements

| Element | Specification |
|---------|--------------|
| **Stars** | Custom SVG, brand-ochre (#e8b94a) fill, soft glow filter, ~24-32px, slight rotation during flight |
| **Paths** | Bezier curves from bottom-left area (task list region) toward top center (hero balance), varied per star |
| **Overlay** | Semi-transparent canvas-bg with 0.3 opacity, rounded edges |
| **Phrase** | Inter 600, 18-24px, brand-ink color, centered, fade-in/out |
| **Summary card** | Cream surface-card background, rounded-lg, brief text showing count + stars earned |

### Random Encouraging Phrases

Pool of phrases, randomly selected each celebration:

```
太棒了！
厉害！
真行！
继续加油！
做得好！
你真棒！
加油加油！
```

### Merged Summary Format

When multiple tasks approved:

```
{count}个任务通过！获得 {stars} ⭐
```

Example: "3个任务通过！获得 15 ⭐"

When single task approved:

```
获得 {stars} ⭐！
```

Example: "获得 5 ⭐！"

## Client-Side State Tracking

**Problem:** Need to distinguish "approved but not celebrated" from "approved and already celebrated" to avoid repeating celebrations.

**Approach:** Store a "last celebrated approval timestamp" or a set of celebrated task IDs in localStorage.

| Option | Trade-off |
|--------|-----------|
| **Timestamp** (store `last_celebration_at`) | Simple, but may miss approvals if child celebrates partial batch then closes app |
| **Task ID set** (store `celebrated_task_ids: string[]`) | More precise, but requires syncing with API response, bounded growth (prune old IDs) |

Recommendation: Task ID set, pruned to last 50 IDs. On app open, compare current approved task IDs against celebrated set; animate for any newly-approved IDs not in set; add those IDs to set after celebration.

## Affected Components

| Component | Change |
|-----------|--------|
| `ChildHomePage.vue` | Entry point for celebration trigger on mount |
| `ChildTasksPage.vue` | Alternative entry point if child lands on tasks page |
| `ChildLayout.vue` | May host celebration overlay as Teleport target |
| New: `CelebrationAnimation.vue` | Dedicated animation component |
| New: SVG star asset | Custom star with glow filter |

## Edge Cases

| Case | Handling |
|------|----------|
| Child closes app mid-animation | Animation interrupted; task IDs marked as celebrated before animation starts to prevent repeat |
| Very large batch (10+ tasks approved) | Cap star count displayed at ~8-10 visually; summary text shows true count |
| Balance display not visible (scrolled down) | Stars fly toward top of screen regardless; overlay ensures visibility |
| Dark mode | Stars use same ochre fill (visible on dark); overlay uses dark-tinted background |
| Network error fetching approved tasks | Gracefully skip celebration; no blocking error |

## Success Criteria

- Child sees celebration ≥95% of times when approved tasks await
- Animation completes in ≤3 seconds
- No celebration repeats for same approval
- Animation works in both light and dark modes
- Does not block app navigation or interaction during animation

## Dependencies

- Backend already returns approved tasks in `getMyChores()` response
- No new API endpoints needed
- Client-side localStorage for celebration state

## Open Questions (resolved during planning)

- Exact SVG star design (deferred to planning with design review)
- Whether to use CSS animations or a lightweight animation library (Vue transitions suffice for 2-3s sequence)
- Whether balance pulse requires CoinDisplay component modification or can be overlay-based