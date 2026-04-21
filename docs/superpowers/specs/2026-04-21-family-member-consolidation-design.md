---
name: family-member-consolidation
description: Consolidate FamilyPage and MemberManagePage into a unified family management interface
type: refactor
date: 2026-04-21
---

# Family Member Management Consolidation

## Problem

Current family member management is split across three pages with overlapping functionality:

1. **FamilyPage** (`/family`) — displays family info, member list, child management dashboard (balance/chores/wishes stats + actions)
2. **MemberManagePage** (`/family/members`) — separate page for member operations (swipe to remove, set as owner, regenerate invite code)
3. **SettingsPage** — has a "家庭成员管理" link pointing to `/family`

**Overlaps:**
- Both FamilyPage and MemberManagePage display member lists (duplicate UI)
- Child management actions (switch view, grant coins) only in FamilyPage
- Adult member management (remove, set owner) only in MemberManagePage
- User must navigate between pages for different member operations

## Goal

Consolidate all family and member management into a single page at `/family`, eliminating redundancy and providing a unified management interface.

## Design

### Page Structure

**Route:** `/family` → `FamilyPage.vue`

**Layout (top to bottom):**

```
┌─────────────────────────────────────┐
│ Section 1: Family Info              │
│ ├─ Family Name (owner editable)     │
│ └─ Invite Code (copy button)        │
├─────────────────────────────────────┤
│ Section 2: Adult Members            │
│ ├─ Member rows (swipe actions)      │
│ │  ├─ Avatar + Name + Role tag      │
│ │  └─ Swipe: Set Owner / Remove     │
│ └─ Regenerate Invite Code button    │
├─────────────────────────────────────┤
│ Section 3: Child Members (owner)    │
│ ├─ Child rows (if any)              │
│ │  ├─ Avatar + Name                 │
│ │  ├─ Stats: Balance / Chores /     │
│ │  │         Wishes / Pending        │
│ │  └─ Actions: Approve Chores /     │
│ │             Approve Wishes /       │
│ │             Grant Coins /          │
│ │             Switch View /          │
│ │             Remove                 │
│ └─ (Hidden if no children)          │
└─────────────────────────────────────┘
```

### Approach

**Selected: Approach B — Refactor FamilyPage as base**

Rationale:
- FamilyPage already contains all child management logic (API calls, state, actions)
- Route `/family` remains unchanged
- Merge MemberManagePage's adult member operations into FamilyPage
- Delete MemberManagePage entirely

### Changes

#### 1. FamilyPage.vue

**Add from MemberManagePage:**
- Adult member swipe actions (set owner, remove)
- Regenerate invite code button
- Split member list into two sections: adults and children

**Remove:**
- Coin exchange rate settings (铜→银、银→金) — move to SettingsPage

**Refactor:**
- Child management cards → grouped list with inline stats and action buttons
- Each child row shows: avatar, name, 4 stats (balance, chores, wishes, pending), 5 action buttons

#### 2. SettingsPage.vue

**Add:**
- New section "星星币设置" (owner only)
- Fields: 铜→银 (copper_to_silver), 银→金 (silver_to_gold)
- Save button calling `updateFamilySettings`

**Location:** Insert after "家庭管理" section, before "账户信息"

#### 3. Router

**Remove:**
- Route `/family/members` and its MemberManagePage import

**Keep:**
- Route `/family` → FamilyPage.vue (unchanged)

#### 4. Delete Files

- `frontend/src/pages/MemberManagePage.vue`

### Component Boundaries

**No new components.** All logic stays in FamilyPage.vue for simplicity:
- Adult member operations (remove, set owner, regenerate code) — inline in template
- Child member operations (grant coins, switch view, approve) — existing logic
- Family info display — existing logic

### Data Flow

**Existing APIs (no backend changes):**
- `GET /api/v1/family/info` — family info
- `GET /api/v1/family/members` — all members
- `PUT /api/v1/family/members/{id}/role` — set owner
- `DELETE /api/v1/family/members/{id}` — remove member
- `POST /api/v1/family/regenerate-invite-code` — regenerate code
- `GET /api/v1/family/children/balances` — child balances
- `GET /api/v1/family/children/chore-stats` — child chore stats
- `GET /api/v1/family/child-wishes` — child wishes
- `POST /api/v1/coins/grant` — grant coins
- `POST /api/v1/auth/admin/switch-child` — switch to child view
- `PUT /api/v1/family/settings` — update coin rates (moved to SettingsPage)

**State management:**
- `useFamilyStore` — family info, members, coin rates
- `useAuthStore` — current user role

### UI Patterns

**Adult members:**
- `van-swipe-cell` with right actions (existing pattern from MemberManagePage)
- Cannot remove self
- Cannot remove other owners (only one owner allowed)

**Child members:**
- Grouped under "👧 孩子管理" heading
- Each row: `van-cell` with custom content (avatar, name, stats grid, action buttons)
- Stats displayed as 4-column grid (balance, chores, wishes, pending)
- Action buttons: 4 mini buttons (approve chores, approve wishes, grant coins, switch view) + swipe-to-remove

**Coin grant sheet:**
- Existing bottom sheet popup (no changes)

### Permission Rules

**Owner only:**
- Edit family name
- Regenerate invite code
- Set other members as owner
- Remove members
- View and manage child section
- Grant coins
- Switch to child view

**Member:**
- View family info (read-only)
- View adult member list (no actions)
- No child section visible

### Error Handling

**Existing patterns:**
- API errors → `showToast` with error message
- Confirmation dialogs for destructive actions (remove, regenerate code)
- Loading states on async operations

### Testing Strategy

**Manual testing:**
1. Owner login → verify all sections visible and functional
2. Member login → verify read-only view, no child section
3. Remove member → confirm dialog, member removed from list
4. Set owner → confirm dialog, role tag updates
5. Regenerate code → confirm dialog, new code displayed
6. Child operations → grant coins, switch view, approve actions work
7. Coin rate settings → moved to SettingsPage, save works

**No new unit tests needed** — existing component tests cover the merged functionality.

## Implementation Plan

1. **Backup current state** — commit any uncommitted changes
2. **Modify FamilyPage.vue:**
   - Add adult member swipe actions
   - Add regenerate invite code button
   - Refactor child cards into grouped list
   - Remove coin rate settings
3. **Modify SettingsPage.vue:**
   - Add coin rate settings section
4. **Modify router/index.ts:**
   - Remove `/family/members` route
5. **Delete MemberManagePage.vue**
6. **Test all scenarios** (owner/member views, all actions)
7. **Commit changes**

## Non-Goals

- Backend API changes (all existing endpoints work as-is)
- New components or abstractions
- Child detail page (all operations inline)
- Pagination (member lists are small in typical families)

## Success Criteria

- Single page at `/family` handles all family and member management
- Owner can perform all operations without navigating away
- Member sees appropriate read-only view
- No duplicate UI or navigation confusion
- All existing functionality preserved
- MemberManagePage deleted, no dead routes
