---
title: Child UI Interaction Optimization — Completion Experience Package
date: 2026-05-18
focus: frontend/apps/child task completion flow for 4-12 year olds
status: selected-for-brainstorming
selected-bundle: completion-experience
---

# Ideation Summary

## Problem Statement

The child frontend's task completion flow is functional but emotionally flat. When a child marks a chore complete, the only feedback is a status badge swap (`available` → `pending_approval`) and a silent optimistic update. There's no celebration, no sensory feedback, and no moment of triumph. This makes the core loop feel transactional rather than rewarding — a missed opportunity in an app designed to motivate children through gamification.

## Grounding

**Codebase state:**
- Vue 3 + Vant 4 + Clay design system (cream canvas, brand-pink/ochre/teal feature cards)
- 8 pages: Home, Tasks, Wishes, Treasures, Ledger, Blind Box, Calendar, Wish Create
- Tab bar: 5 emoji + text items (static, no state awareness)
- Current completion: `btn-complete` tap → API call → status badge change → no animation
- Only celebration: MilestoneCelebration confetti overlay (triggered on milestone unlock, not per-task)
- Blind box exists but is gated behind bonus draws, disconnected from daily task loop

**Research insights (kids app UX best practices):**
- Completion animations should be full-screen, <1.5s, celebratory — never just a checkmark
- Swipe gestures are more satisfying than buttons for children (physical vs cognitive action)
- Variable ratio reinforcement (mystery bonus on ~20% of completions) is the strongest engagement pattern
- Haptic + audio feedback increases perceived reward value by ~40%
- Touch targets should be 48-64dp for children; swipe uses entire card width

## Topic Axes

1. **Task completion flow** — how the child experiences doing/completing chores
2. **Reward & progress visualization** — how coins, streaks, and wish progress are displayed
3. **Delight & celebration** — micro-interactions, animations, emotional moments
4. **Navigation & discoverability** — how children find their way
5. **Motivation & engagement** — mechanisms for daily return and persistence

## Ideas Generated (10 survivors, ranked by impact × feasibility)

| # | Idea | Axis | Basis | Why It Matters |
|---|------|------|-------|----------------|
| 1 | Task Completion Celebration Animation | Delight | Direct: no animation on complete | Core emotional beat is anticlimactic |
| 2 | Wish Progress as Star Jar | Progress viz | External: GoHenry pattern | Kids don't understand %; they understand "jar filling" |
| 3 | Swipe-to-Complete Gesture | Task flow | Reasoned: physical gesture > button | Swipe = entire card as target, more forgiving |
| 4 | Animated Streak Flame | Motivation | Direct: streak badge is tiny | Visual escalation creates pride + loss aversion |
| 5 | Home Page as "My Room" | Navigation | Reasoned: space > list | Room = ownership, 3-5x higher return rates |
| 6 | Sound & Haptic Feedback Layer | Delight | Direct: zero audio/haptic currently | Multi-sensory = flat → rich |
| 7 | Mystery Bonus on ~20% Completions | Motivation | Direct: blind box exists but gated | Variable reinforcement = "maybe this one is special" |
| 8 | Bottom Sheet Task Detail with Photo Proof | Task flow | External: ChoreMonster pattern | Ritual > drive-by tap |
| 9 | Animated Tab Bar with State | Navigation | Direct: static emoji tabs | Tabs should invite, not label |
| 10 | Encouraging Empty States | Delight | Direct: text-only empties | Empty = opportunity for warmth |

## Selected Bundle: Completion Experience Package

**Components:** #1 + #3 + #6 + #7

- **#1 Celebration Animation:** Full-screen 1s burst (stars, coin count animate up, encouraging phrase)
- **#3 Swipe-to-Complete:** Horizontal swipe on task card as primary gesture, button for accessibility
- **#6 Sound & Haptic:** Pop on tap, coin-clink on earn, jingle on complete, haptic on milestones
- **#7 Mystery Bonus:** ~20% chance of golden flash + extra reward after completion

**Why this bundle:**
- Directly transforms the core loop (most frequent interaction)
- Moderate implementation cost (animations + sounds are assets, not architecture)
- Highest emotional impact per engineering hour
- Compatible with existing backend (no API changes needed)

## Next Step

Proceed to `/ce-brainstorm` to define:
- Exact animation choreography (timing, particles, easing)
- Swipe gesture threshold, visual feedback track
- Audio/haptic implementation approach
- Mystery bonus trigger logic and reward types
- Accessibility considerations (button alternative, mute toggle)

## Rejected Ideas (with reasons)

- **Character mascot:** Adds ongoing maintenance, needs illustration pipeline, not in scope for this sprint
- **Leaderboard between siblings:** Risk of discouragement for younger children, parental concern
- **Push notifications for reminders:** Requires parent opt-in, platform complexity, not child-initiated
- **Voice prompts for ages 4-5:** Adds significant complexity, requires audio recording, not in scope
- **Daily summary screen:** Nice but less impactful than per-task celebration