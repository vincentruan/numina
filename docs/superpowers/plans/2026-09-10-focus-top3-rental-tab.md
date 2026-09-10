# FocusTop3Card 租约 Tab 补全 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 4th "rentals" tab to the dashboard's FocusTop3Card so it mirrors the FinanceHubPage's 4-tab structure (assets / liabilities / wishes / rentals).

**Architecture:** Add a `rentals` tab to `FocusTop3Card.vue` that loads active rental contracts via `useRentalContractStore.fetchContracts({ active_only: true })`, sorts them by upcoming urgency (tenant `end_date` / landlord next collection date), and renders the top 3 with role icon, counterparty, monthly rent, and next-due badge. "View all" deep-links to `/finance?tab=rentals`.

**Tech Stack:** Vue 3 `<script setup lang="ts">`, Vant 4 `van-tab`, Pinia `useRentalContractStore`, `useCurrency` composable, `MoneyDisplay` component.

**Spec:** FocusTop3Card currently has 3 tabs (assets/liabilities/wishes) but FinanceHubPage has 4 (assets/liabilities/wishes/rentals). The rentals tab was never ported over when added.

## Global Constraints

- `<script setup lang="ts">` only — no Options API
- No `any` / `@ts-expect-error`
- i18n required — every user-facing string via `t('key')`, never hard-coded Chinese
- Snowflake ID fields are `string` type
- Format `MoneyDisplay` for monetary values; `useCurrency` for inline formatting
- CSS variables + scoped styles only
- Match existing FocusTop3Card patterns (independent loading/error per domain, retry button, `van-empty` fallback, "view all" link)

---

### Task 1: i18n keys for rental tab in FocusTop3Card

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

**Interfaces:**
- Consumes: existing `rental.tab` = '租约' (already present, use for tab title)
- Produces: new `nav.rentals`, `focusTop3.noRentals`, `focusTop3.rentalRenewal`, `focusTop3.rentCollection`, `focusTop3.rentalIndefinite`, `rental.month` keys

- [ ] **Step 1: Add nav.rentals key (zh-CN)**

In `frontend/apps/main/src/i18n/locales/zh-CN.ts`, inside the `nav` object (~line 93, after `settings`), add:

```ts
    rentals: '租约',
```

- [ ] **Step 2: Add focusTop3 keys (zh-CN)**

In the same file, inside the `focusTop3` object (after `liabilityHighRate` line ~152), add:

```ts
    noRentals: '暂无活跃租约',
    rentalRenewal: '续租',
    rentCollection: '收租',
    rentalIndefinite: '不定期',
```

- [ ] **Step 3: Add rental.month key (zh-CN)**

In the `rental` block (~line 1302, after `monthlyRent`), add:

```ts
    month: '月',
```

- [ ] **Step 4: Add matching en-US keys**

In `frontend/apps/main/src/i18n/locales/en-US.ts`:

In `nav` object:
```ts
    rentals: 'Rentals',
```

In `focusTop3` object:
```ts
    noRentals: 'No active rentals',
    rentalRenewal: 'Renewal',
    rentCollection: 'Collection',
    rentalIndefinite: 'Indefinite',
```

In `rental` block:
```ts
    month: '/mo',
```

- [ ] **Step 5: Verify typecheck passes**

Run: `cd frontend && pnpm -r typecheck`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(i18n): add FocusTop3Card rental tab keys"
```

---

### Task 2: Add rentals tab to FocusTop3Card template + script

**Files:**
- Modify: `frontend/apps/main/src/components/dashboard/FocusTop3Card.vue`

**Interfaces:**
- Consumes: `useRentalContractStore` from `@/stores/rentalContract`, `RentalContract` type from `@/types`, `parseLocalDate` from `@/utils/format`, `MoneyDisplay` (already imported), `useCurrency` (already imported)
- Produces: 4th `rentals` tab in the component, visible in the dashboard

- [ ] **Step 1: Write the failing test**

In `frontend/apps/main/src/components/dashboard/__tests__/FocusTop3Card.spec.ts` (or create if missing), add a test that verifies the rentals tab exists:

```ts
it('renders a rentals tab', () => {
  // ... setup with mocked stores returning empty data
  expect(wrapper.find('.top3-tabs').exists()).toBe(true)
  const tabs = wrapper.findAll('.van-tab')
  expect(tabs.length).toBe(4)
  expect(tabs[3].text()).toContain('rental') // or check i18n key resolves
})
```

If the test file doesn't exist yet, check for existing test files first:
```bash
find frontend/apps/main/src -path "*FocusTop3*" -name "*.spec.ts"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && pnpm -r test:run -- FocusTop3Card`
Expected: FAIL — only 3 tabs rendered

- [ ] **Step 3: Update the script section**

In `FocusTop3Card.vue` `<script setup>`, add the rental store import and data:

```ts
// Add import (after existing store imports ~line 159-161)
import { useRentalContractStore } from '@/stores/rentalContract'
import type { RentalContract } from '@/types'

// Add store instance (after wishStore ~line 172)
const rentalStore = useRentalContractStore()

// Widen activeTab type (line 186)
const activeTab = ref<'assets' | 'liabilities' | 'wishes' | 'rentals'>('assets')

// Add rental loading/error state (after wishError ~line 196)
const rentalLoading = ref(false)
const rentalError = ref(false)

// Add top 3 rental computed (after topWishes computed ~line 225)
// Sort by upcoming urgency: tenant by end_date, landlord by next collection date
function nextRentalDueDate(c: RentalContract): Date | null {
  if (c.role === 'tenant' && c.end_date) {
    return parseLocalDate(c.end_date)
  }
  if (c.role === 'landlord' && c.start_date) {
    // Next collection = same day-of-month as start_date, in current or next month
    const today = new Date()
    const day = new Date(c.start_date).getDate()
    const thisMonth = new Date(today.getFullYear(), today.getMonth(), day)
    if (thisMonth >= today) return thisMonth
    return new Date(today.getFullYear(), today.getMonth() + 1, day)
  }
  return null
}

const topRentals = computed(() =>
  [...(rentalStore.contracts || []).filter(c => c.is_active)]
    .sort((a, b) => {
      const da = nextRentalDueDate(a)
      const db = nextRentalDueDate(b)
      if (!da && !db) return 0
      if (!da) return 1  // no date → sort last
      if (!db) return -1
      return da.getTime() - db.getTime()
    })
    .slice(0, 3),
)

// Add rental load function (after loadWishes)
async function loadRentals() {
  rentalLoading.value = true
  rentalError.value = false
  try {
    await rentalStore.fetchContracts({ active_only: true })
  } catch {
    rentalError.value = true
  } finally {
    rentalLoading.value = false
  }
}

function retryRentals() {
  loadRentals()
}

// Update onMounted (line ~346-351) to also load rentals:
onMounted(() => {
  loadLiabilities()
  loadWishes()
  loadRentals()
})

// Update onActivated (line ~356-360) to also load rentals:
onActivated(() => {
  if (!hasActivated) { hasActivated = true; return }
  loadLiabilities()
  loadWishes()
  loadRentals()
})
```

- [ ] **Step 4: Add the rentals tab template**

After the wishes `</van-tab>` closing tag (line 148), before `</van-tabs>` (line 149), insert:

```vue
      <!-- 租约 tab: active contracts sorted by upcoming due date -->
      <van-tab :title="t('nav.rentals')" name="rentals">
        <div class="top3-body">
          <van-skeleton v-if="rentalLoading" :row="3" animate data-test="rentals-skeleton" />
          <button v-else-if="rentalError" class="top3-retry" data-test="rentals-retry" @click="retryRentals">
            {{ t('financeHub.retry') }}
          </button>
          <van-empty v-else-if="topRentals.length === 0" :description="t('focusTop3.noRentals')" image-size="60" />
          <template v-else>
            <div
              v-for="c in topRentals"
              :key="c.id"
              class="top3-rental"
              role="button"
              tabindex="0"
              :aria-label="rentalAria(c)"
              @click="$router.push({ path: '/finance', query: { tab: 'rentals' } })"
              @keydown.enter="$router.push({ path: '/finance', query: { tab: 'rentals' } })"
            >
              <div class="top3-rental-head">
                <van-icon :name="c.role === 'tenant' ? 'clock-o' : 'gold-coin-o'" class="top3-rental-icon" />
                <span class="top3-rental-name">{{ c.counterparty || t('rental.contract') }}</span>
                <span class="top3-rental-role" :class="`top3-rental-role--${c.role}`">
                  {{ c.role === 'tenant' ? t('focusTop3.rentalRenewal') : t('focusTop3.rentCollection') }}
                </span>
              </div>
              <div class="top3-rental-foot">
                <span class="top3-rental-rent">
                  <MoneyDisplay :amount="Number(c.monthly_rent)" /> / {{ t('rental.month') }}
                </span>
                <span class="top3-rental-date" :class="rentalUrgencyClass(c)">
                  {{ rentalDueLabel(c) }}
                </span>
              </div>
            </div>
          </template>
          <router-link :to="{ path: '/finance', query: { tab: 'rentals' } }" class="top3-view-all" data-test="view-all-rentals">
            {{ t('financeHub.viewAll') }} ›
          </router-link>
        </div>
      </van-tab>
```

- [ ] **Step 5: Add rental helper functions in script**

Add these functions in the `<script setup>` block (after `liabilityAria` ~line 313):

```ts
// --- Rental compute ---

function rentalDueLabel(c: RentalContract): string {
  if (c.role === 'tenant' && c.end_date) {
    return c.end_date
  }
  if (c.role === 'landlord' && c.start_date) {
    const today = new Date()
    const day = new Date(c.start_date).getDate()
    const thisMonth = new Date(today.getFullYear(), today.getMonth(), day)
    const next = thisMonth >= today ? thisMonth : new Date(today.getFullYear(), today.getMonth() + 1, day)
    return `${t('rental.monthly')} ${next.getDate()}日`
  }
  return t('focusTop3.rentalIndefinite')
}

function rentalUrgencyClass(c: RentalContract): string {
  const due = nextRentalDueDate(c)
  if (!due) return ''
  const days = Math.round((due.getTime() - Date.now()) / 86_400_000)
  if (days <= 7) return 'urgent'
  if (days <= 30) return 'warning'
  return ''
}

function rentalAria(c: RentalContract): string {
  const parts = [c.counterparty || t('rental.contract')]
  parts.push(c.role === 'tenant' ? t('focusTop3.rentalRenewal') : t('focusTop3.rentCollection'))
  return listFormatter.format(parts)
}
```

- [ ] **Step 6: Add rental CSS styles**

Add to the `<style scoped>` block (after wish styles, ~line 610):

```css
/* Rental row */
.top3-rental {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 4px 10px 8px;
  border-bottom: 1px solid var(--separator);
  border-left: 3px solid transparent;
  cursor: pointer;
  transition: background 150ms ease-out;
}
.top3-rental:active { background: var(--bg-secondary); }
.top3-rental:last-of-type { border-bottom: none; }
.top3-rental-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.top3-rental-icon {
  font-size: 18px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}
.top3-rental-name {
  flex: 1;
  font-size: 14px;
  color: var(--text-primary);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.top3-rental-role {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
}
.top3-rental-role--tenant {
  background: rgba(25, 137, 250, 0.1);
  color: var(--color-primary);
}
.top3-rental-role--landlord {
  background: rgba(7, 193, 96, 0.1);
  color: var(--color-success, #07c160);
}
.top3-rental-foot {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.top3-rental-rent {
  font-size: 13px;
  color: var(--text-primary);
  font-weight: 600;
}
.top3-rental-date {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 6px;
}
.top3-rental-date.urgent {
  background: #fff1f0;
  color: #cf1322;
}
.top3-rental-date.warning {
  background: #fff7e6;
  color: #d48806;
}
[data-theme='dark'] .top3-rental-date.urgent {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
}
[data-theme='dark'] .top3-rental-date.warning {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd frontend && pnpm -r test:run -- FocusTop3Card`
Expected: PASS

- [ ] **Step 8: Verify typecheck**

Run: `cd frontend && pnpm -r typecheck`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add frontend/apps/main/src/components/dashboard/FocusTop3Card.vue
git commit -m "feat(dashboard): add rentals tab to FocusTop3Card"
```

## Self-Review Checklist

1. **Spec coverage:** The rentals tab mirrors the existing 3 tabs' patterns (loading/error/empty/list + view-all link). ✅
2. **Placeholder scan:** No TBD/TODO in any step. ✅
3. **Type consistency:** `useRentalContractStore` returns `contracts: RentalContract[]`; `nextRentalDueDate` / `rentalDueLabel` / `rentalUrgencyClass` / `rentalAria` all accept `RentalContract`. `topRentals` is `ComputedRef<RentalContract[]>`. ✅
