# Area 1 — Child app (儿童页面优化)

Shared conventions in [`_common.md`](./_common.md).

Routes live under `${CHILD_BASE}` (child SPA; `/child/` base in both modes).
Auth: cookie is shared with the adult session in **docker** mode — establish
the adult session as `demouser` first (prefer the cookie+localStorage
injection fallback in SKILL.md "Phase 2 fallback" — the default `bsk fill`
form-login can trigger a password-manager extension that hijacks the tab),
**then** navigate to `${CHILD_BASE}`. In **dev** mode adult (:5173) and child
(:5174) are different origins; the cookie does NOT carry over — drive the
child two-step emoji-PIN login from the child origin's page context (see
`_common.md` "Child session injection (dev mode)"). The child PIN-pad UI flow
itself is exercised by C1.3 below.

## Existing cases — core child flows

### C1.1 Child home (ChildHomePage) — hero, balance, today's chores

```
bsk navigate ${CHILD_BASE} --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Wait-for text: 选择孩子 → click 小宝 card → PIN flow (C1.3) → lands on `/child/`.

Assertions after PIN login:
- [ ] Greeting shows child display_name (小宝), not empty
- [ ] BalanceHero renders coin amount; copper→silver→gold tiers collapse correctly
- [ ] ProgressRing shows completed/pending/total for today's chores (only when chores exist)
- [ ] "今日任务" section lists today's chores with emoji + reward (+N ⭐)
- [ ] Streak badge 🔥N shows for chores with streak_count > 1
- [ ] Top active wish preview card renders (if child has an active wish)
- [ ] `[console]` zero errors (401 on first auth refresh is expected, not an error)

### C1.2 Child ledger (ChildLedgerPage) — transaction list + sibling gift

```
bsk navigate ${CHILD_BASE}ledger --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] BalanceHero (variant=ledger) renders balance
- [ ] Gift button visible only when `hasSiblings` is true (demouser has 2 children → visible)
- [ ] Transaction list renders: emoji + narrative + relative_time + amount
- [ ] Amount color: positive (income) vs negative (spend) distinguished
- [ ] Empty state (EmptyState component) shows when no transactions
- [ ] Click 赠送 button → van-popup bottom sheet opens with sibling list
- [ ] Selecting a sibling + confirming does NOT error (gift flow)

### C1.3 Child PIN auth (ChildAuthPage) — correct + wrong PIN

After navigating to `/child/` and clicking a child card:
```
bsk snapshot --session <id>     # capture emoji buttons as @eN refs
```

Assertions (correct PIN for 小宝 = 🐰🥕🌈⭐):
- [ ] 4 empty PIN slot indicators visible
- [ ] 12 emoji buttons in 4×3 grid
- [ ] 删除 and 清除 buttons visible
- [ ] Click the 4 correct emojis in order → auto-submits → navigates to `/child/` (home)
- [ ] Wrong PIN (e.g. 🐱🐱🐱🐱) → shake animation + PIN cleared + error message

**Emoji click order note:** snapshot the grid, then click each emoji's `@eN` ref
in sequence. Do NOT assume a fixed layout — re-snapshot if a click causes any
DOM change before the next.

### C1.4 Child wishes (ChildWishesPage) — list + status variants

```
bsk navigate ${CHILD_BASE}wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Wish list renders with emoji, name, status badge
- [ ] Status variants present per prerequisite data:
      - 小宝: 积木玩具 (pending_review), 昂贵玩具 (rejected), 小背包 (realized)
      - 大宝: 新耳机 (active, cost=80), 漫画书 (redemption_requested, cost=30)
- [ ] Coin cost shown for approved/active wishes
- [ ] 申请兑换 button visible for active wishes with sufficient balance

### C1.5 Child wish create (ChildWishCreatePage) — form submission

```
bsk navigate ${CHILD_BASE}wishes/new --session <id> --wait-until networkidle
bsk snapshot --session <id>
# fill name field (find via ref), click submit
bsk fill @eN --value 测试心愿 --session <id>
bsk snapshot --session <id>   # re-snapshot to get submit button ref
bsk click @eM --session <id>
```

Assertions:
- [ ] Form renders name input + emoji picker + (optional) cost field
- [ ] Submit creates wish in pending_review status
- [ ] On success, navigates back to `/child/wishes` and new wish appears in list
- [ ] Empty name submission → validation error, no API call

### C1.6 Child tasks (ChildTasksPage) — chore list + completion

```
bsk navigate ${CHILD_BASE}tasks --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Today's chore list visible (整理房间 🧹 5⭐, 洗碗 🍽️ 8⭐, etc. from prerequisite data)
- [ ] Chore cards show emoji, name, coin reward
- [ ] Available chore → tap → marks complete → shows 待审批 state
- [ ] Completed-but-unapproved chores show pending_approval badge (clock icon)
- [ ] Approved chores show success icon; rejected show warning icon

### C1.7 Child treasures/blind-box (ChildTreasuresPage)

```
bsk navigate ${CHILD_BASE}treasures --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Treasure/blind-box UI renders
- [ ] Available bonus draws shown (小宝 has 2 bonus draws per prerequisite data)
- [ ] Gift pool preview visible
- [ ] Draw history visible if any past draws
- [ ] `/child/blind-box` redirects to `/child/treasures` (route alias)

### C1.8 Child asset detail (ChildAssetDetailPage)

```
# From child home, click a wish preview or asset link → /child/assets/:id
bsk snapshot --session <id>
```

Assertions:
- [ ] Asset detail renders (name, emoji, value as seen by child role)
- [ ] No adult-only fields leak (e.g. purchase_price edit, sell button)
- [ ] Back navigation returns to previous page

### C1.9 Child settings (ChildSettingsPage)

```
bsk navigate ${CHILD_BASE}settings --session <id> --wait-until networkidle
bsk snapshot --session <id>
```

Assertions:
- [ ] Settings page renders for child role
- [ ] Logout option present and functional
- [ ] No adult-only settings (AI config, family management) visible

---

## New cases — child celebration gamefeel (gamification)

Covers `feat-child-celebration-gamefeel-v2` + `feat-child-chore-gamification`
(both landed in `frontend/apps/child/src/`). Components: `FlyToTarget`,
`CandleFlame`, `useHaptic`, `useReducedMotion`, `motionTokens`.

### C1.10 Chore completion celebration — FlyToTarget particle + coin bump

```
# On ChildTasksPage, snapshot an available chore, then complete it
bsk navigate ${CHILD_BASE}tasks --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>   # tap an available chore → mark complete
bsk wait-ms 800                # let the celebration animation play
bsk screenshot --session <id> --out dogfood-output/c1.10-celebration.png
```

Assertions:
- [ ] On completion, `FlyToTarget` particle animates from the chore card toward the balance/coin target
- [ ] BalanceHero coin amount increments (the reward lands)
- [ ] A wish-bump toast appears if this chore's reward contributed to an active wish's progress (gamification U3)
- [ ] Chore card transitions to 待审批 / pending_approval state
- [ ] `[console]` zero errors (animation libs must not throw on missing target ref)

### C1.11 Streak flame on chore cards

```
bsk snapshot --session <id>     # on ChildTasksPage, capture a chore with streak_count > 1
```

Assertions:
- [ ] Chores with `streak_count > 1` render a streak flame animation (CandleFlame / streak flame) on the card
- [ ] Chores with no streak (streak_count ≤ 1) do NOT render the flame
- [ ] Flame does not overlap the chore name or reward text (no layout regression)

### C1.12 Reduced-motion fallback

```
# Emulate prefers-reduced-motion via evaluate, then complete a chore
bsk evaluate --session <id> --expr "const m = window.matchMedia('(prefers-reduced-motion: reduce)'); Object.defineProperty(m, 'matches', {get:()=>true}); window.__origMatchMedia = window.matchMedia; window.matchMedia = () => m; 'reduced-motion-forced'"
bsk navigate ${CHILD_BASE}tasks --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk click @eN --session <id>     # complete a chore
bsk wait-ms 600
```

Assertions:
- [ ] No particle/FlyToTarget animation plays (reduced-motion path is static, not disabled — see plan KTD "Static overlay")
- [ ] Coin still increments, chore still marked complete (feature works, just no motion)
- [ ] If a long-press peek or toast is involved, it shows as a static instant-on overlay, not an animation
- [ ] `[console]` zero errors (useReducedMotion must register/cleanup its matchMedia listener cleanly)

### C1.13 Haptic pulse on completion (device-aware)

```
bsk evaluate --session <id> --expr "'vibrate' in navigator ? navigator.vibrate.toString() : 'no-vibrate'"
# then complete a chore as in C1.10
```

Assertions:
- [ ] On a device/emulator with `navigator.vibrate`, completing a chore triggers the reward pulse pattern (`[50, 30, 50]` per gamification U1)
- [ ] On a device WITHOUT vibrate (desktop Chromium), completion still succeeds — `useHaptic` feature-detects and no-ops gracefully
- [ ] `[console]` zero errors (no "navigator.vibrate is not a function")

---

## New cases — cross-wish bundle (constellation + what-if peek)

Covers `feat-child-cross-wish-bundle`. Components: `WishConstellationGrid`,
`WishConstellationCard`, `@numina/math` (`reachabilityTint`, `previewSpend`,
`daysEstimate`). No backend changes — backed by `priority_simulation[]`.

### C1.14 Wish constellation grid — traffic-light tints + days estimate

```
bsk navigate ${CHILD_BASE}wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c1.14-constellation.png
```

Assertions:
- [ ] `WishConstellationGrid` renders as a grid of `WishConstellationCard`s (not a flat list) for active wishes
- [ ] Each card tinted by reachability: green (covered/soon reachable), yellow (mid), red (far/unreachable) — `reachabilityTint()` from `@numina/math`
- [ ] Each card shows the `≈ N 天` secondary read (`daysEstimate()`) when a days estimate exists; placeholder text when null (`timeUnitPlaceholder`)
- [ ] Tint + days estimate are consistent (a green card should have a low/zero days estimate; a red card a high one) — verify the arithmetic, not just presence
- [ ] `[console]` zero errors

### C1.15 Long-press what-if peek — spend delta preview

```
bsk snapshot --session <id>     # on the wishes constellation grid
# Long-press a wish card (hold the @eN ref)
bsk evaluate --session <id> --expr "<dispatch pointerdown on the wish card element, hold 1.5s>"
bsk wait-ms 1600
bsk screenshot --session <id> --out dogfood-output/c1.15-whatif-peek.png
bsk snapshot --session <id>     # capture the peek overlay state
```

Assertions:
- [ ] Long-pressing a wish card triggers a what-if peek overlay (`peekActiveWishId` set, `peekDeltas` populated via `previewSpend()`)
- [ ] Overlay shows how spending on this wish would shift OTHER wishes' progress/days (`days_added` deltas visible)
- [ ] Wishes already covered by the spend get `days_added: 0`; uncovered wishes get positive `days_added`
- [ ] Releasing the long-press (pointerup) dismisses the peek overlay
- [ ] Peek is non-committing — no API call fired (verify via `[console]`: no POST/PUT network for wish mutation)
- [ ] `[console]` zero errors

### C1.16 Long-press peek — reduced-motion static overlay

```
# Force reduced-motion (as in C1.12), then long-press a wish card
bsk evaluate --session <id> --expr "<force prefers-reduced-motion reduce>"
bsk evaluate --session <id> --expr "<pointerdown on wish card>"
bsk wait-ms 500
bsk snapshot --session <id>
```

Assertions:
- [ ] Under reduced-motion, the peek shows the after-state immediately as a STATIC overlay (no 1.5s ghost animation)
- [ ] Overlay auto-dismisses after a 3-second timeout OR on pointerup (whichever first)
- [ ] Educational content (deltas) is still shown — feature not disabled, just de-animated

---

## New cases — parent-side cost-edit dialog (cross-app trust contract)

Covers the parent main-app side of the cross-wish bundle: `WishCostEditDialog`
in `frontend/apps/main/src/components/wishes/`. Surfaces the child's
days-estimate delta before commit.

### C1.17 Parent cost-edit dialog with days-estimate delta warning

```
# Adult session (Phase 2 login). Navigate to a wish's cost-edit affordance.
bsk navigate ${BASE}wishes --session <id> --wait-until networkidle
bsk snapshot --session <id>
# Open the cost-edit dialog on a wish (the StarCoinSuggestion / cost-edit entry)
bsk click @eN --session <id>
bsk snapshot --session <id>
bsk screenshot --session <id> --out dogfood-output/c1.17-cost-edit.png
```

Assertions:
- [ ] `WishCostEditDialog` opens with the current cost editable
- [ ] A trust-contract warning sheet/notice is shown explaining that changing the cost affects the child's days-estimate (the cross-app delta the child sees)
- [ ] Editing the cost updates the displayed `≈ N 天` projection live (parent sees the same days-estimate math the child sees, via shared `@numina/math`)
- [ ] Cancel discards without API call; Confirm POSTs the cost change and the dialog closes
- [ ] `[console]` zero errors
