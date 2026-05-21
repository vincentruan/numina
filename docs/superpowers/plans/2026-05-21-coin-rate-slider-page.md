# 星币汇率设置页面 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign star coin exchange rate configuration from inline expansion to a dedicated page with slider+input combo, using silver/gold coin styles for slider thumbs.

**Architecture:** Create a new CoinRatesPage at `/settings/family/coin-rates` with two horizontal slider+input rows. Custom CoinSlider component uses coin SVGs as draggable thumbs. Bidirectional sync between slider and input.

**Tech Stack:** Vue 3 + TypeScript + Vant 4 Slider + custom SVG thumb overlay

---

## File Structure

| File | Responsibility |
|------|----------------|
| `CoinRatesPage.vue` (create) | Page container, loads/saves rates, layout |
| `CoinSlider.vue` (create) | Custom slider with coin-style thumb, 1-10 range |
| `SettingsPage.vue` (modify) | Remove inline expansion, add navigation link |
| `router/index.ts` (modify) | Add route for `/settings/family/coin-rates` |
| `zh-CN.ts` (modify) | Add i18n keys for new page |
| `en-US.ts` (modify) | Add English translations |

---

### Task 1: Add i18n keys

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts:833` (after settings block)
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts` (settings section)

- [ ] **Step 1: Add Chinese i18n keys**

Add to `zh-CN.ts` in the `settings` block (after line 832):

```typescript
coinRatesPageTitle: '星币汇率设置',
copperToSilverRate: '铜币兑换银币',
silverToGoldRate: '银币兑换金币',
```

- [ ] **Step 2: Add English i18n keys**

Add to `en-US.ts` in the `settings` block:

```typescript
coinRatesPageTitle: 'Coin Exchange Rates',
copperToSilverRate: 'Copper to Silver Rate',
silverToGoldRate: 'Silver to Gold Rate',
```

- [ ] **Step 3: Verify i18n compiles**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: No type errors

- [ ] **Step 4: Commit i18n changes**

```bash
git add frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(i18n): add coin rates page translations"
```

---

### Task 2: Create CoinSlider component

**Files:**
- Create: `frontend/apps/main/src/components/coins/CoinSlider.vue`

- [ ] **Step 1: Create CoinSlider.vue with coin thumb overlay**

```vue
<template>
  <div class="coin-slider">
    <van-slider
      v-model="internalValue"
      :min="1"
      :max="10"
      :step="1"
      bar-height="6px"
      active-color="#bdbbff"
      inactive-color="#e5e5e5"
      @update:model-value="onSliderChange"
    />
    <!-- Coin thumb overlay -->
    <div class="coin-thumb" :style="{ left: thumbPosition }">
      <component :is="coinComponent" :size="28" />
    </div>
    <!-- Scale marks -->
    <div class="scale-marks">
      <span>1</span>
      <span>5</span>
      <span>10</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import SilverCoin from './SilverCoin.vue'
import GoldenCoin from './GoldenCoin.vue'

const props = withDefaults(
  defineProps<{
    modelValue: number
    coinType: 'silver' | 'gold'
  }>(),
  {
    modelValue: 10,
    coinType: 'silver',
  },
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: number): void
}>()

const internalValue = ref(props.modelValue)

watch(() => props.modelValue, (val) => {
  internalValue.value = val
})

const coinComponent = computed(() => {
  return props.coinType === 'silver' ? SilverCoin : GoldenCoin
})

// Calculate thumb position as percentage (1-10 range)
const thumbPosition = computed(() => {
  const percent = ((internalValue.value - 1) / 9) * 100
  return `calc(${percent}% - 14px)` // Offset for coin size (28px / 2)
})

function onSliderChange(val: number) {
  emit('update:modelValue', val)
}
</script>

<style scoped>
.coin-slider {
  position: relative;
  padding: 8px 14px 0; /* Account for coin thumb size */
}

.coin-slider :deep(.van-slider__button) {
  visibility: hidden; /* Hide default button */
}

.coin-thumb {
  position: absolute;
  top: 0;
  transition: left 0.1s ease-out;
  pointer-events: none; /* Let slider handle drag */
  z-index: 10;
}

.scale-marks {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
```

- [ ] **Step 2: Verify component compiles**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: No type errors

- [ ] **Step 3: Commit CoinSlider component**

```bash
git add frontend/apps/main/src/components/coins/CoinSlider.vue
git commit -m "feat(components): add CoinSlider with coin-style thumb"
```

---

### Task 3: Create CoinRatesPage

**Files:**
- Create: `frontend/apps/main/src/pages/CoinRatesPage.vue`

- [ ] **Step 1: Create CoinRatesPage.vue**

```vue
<template>
  <div class="coin-rates-page">
    <PageHeader :title="t('settings.coinRatesPageTitle')" />
    <div class="rates-content">
      <!-- Copper to Silver -->
      <div class="rate-row">
        <div class="rate-label">{{ t('settings.copperToSilverRate') }}</div>
        <div class="rate-controls">
          <CoinSlider
            v-model="copperToSilver"
            coin-type="silver"
            class="slider"
          />
          <van-field
            v-model="copperToSilverStr"
            type="digit"
            class="rate-input"
            :error="copperToSilverError"
            @update:model-value="onCopperInput"
          />
        </div>
      </div>

      <!-- Silver to Gold -->
      <div class="rate-row">
        <div class="rate-label">{{ t('settings.silverToGoldRate') }}</div>
        <div class="rate-controls">
          <CoinSlider
            v-model="silverToGold"
            coin-type="gold"
            class="slider"
          />
          <van-field
            v-model="silverToGoldStr"
            type="digit"
            class="rate-input"
            :error="silverToGoldError"
            @update:model-value="onSilverInput"
          />
        </div>
      </div>
    </div>

    <div class="save-action">
      <van-button
        block
        type="primary"
        :loading="saving"
        :disabled="copperToSilverError || silverToGoldError"
        @click="saveRates"
      >
        {{ t('common.save') }}
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { useFamilyStore } from '@/stores/family'
import { getFamilySettings, updateFamilySettings } from '@/api/family'
import PageHeader from '@/components/common/PageHeader.vue'
import CoinSlider from '@/components/coins/CoinSlider.vue'

const { t } = useI18n()
const router = useRouter()
const familyStore = useFamilyStore()

const copperToSilver = ref(10)
const silverToGold = ref(10)
const copperToSilverStr = ref('10')
const silverToGoldStr = ref('10')
const copperToSilverError = ref(false)
const silverToGoldError = ref(false)
const saving = ref(false)

onMounted(async () => {
  try {
    const res = await getFamilySettings()
    copperToSilver.value = res.data.coin_copper_to_silver
    silverToGold.value = res.data.coin_silver_to_gold
    copperToSilverStr.value = String(copperToSilver.value)
    silverToGoldStr.value = String(silverToGold.value)
  } catch {
    showToast(t('toast.loadFailed'))
  }
})

function onCopperInput(val: string) {
  const num = parseInt(val)
  if (isNaN(num) || num < 1 || num > 10) {
    copperToSilverError.value = true
  } else {
    copperToSilverError.value = false
    copperToSilver.value = num
  }
}

function onSilverInput(val: string) {
  const num = parseInt(val)
  if (isNaN(num) || num < 1 || num > 10) {
    silverToGoldError.value = true
  } else {
    silverToGoldError.value = false
    silverToGold.value = num
  }
}

async function saveRates() {
  if (copperToSilverError.value || silverToGoldError.value) {
    showToast(t('toast.coinRateInvalid'))
    return
  }
  saving.value = true
  try {
    await updateFamilySettings({
      coinCopperToSilver: copperToSilver.value,
      coinSilverToGold: silverToGold.value,
    })
    familyStore.coinCopperToSilver = copperToSilver.value
    familyStore.coinSilverToGold = silverToGold.value
    showToast(t('toast.saveSuccess'))
    router.back()
  } catch {
    showToast(t('toast.saveFailed'))
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.coin-rates-page {
  min-height: 100vh;
  background: var(--bg-secondary);
}

.rates-content {
  padding: 16px;
}

.rate-row {
  background: var(--bg-card);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
}

.rate-label {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 12px;
  color: var(--text-primary);
}

.rate-controls {
  display: flex;
  align-items: center;
  gap: 12px;
}

.slider {
  flex: 1;
}

.rate-input {
  width: 60px;
  flex-shrink: 0;
}

.rate-input :deep(.van-field__control) {
  text-align: center;
}

.save-action {
  padding: 16px;
}
</style>
```

- [ ] **Step 2: Verify page compiles**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: No type errors

- [ ] **Step 3: Commit CoinRatesPage**

```bash
git add frontend/apps/main/src/pages/CoinRatesPage.vue
git commit -m "feat(pages): add CoinRatesPage with slider+input combo"
```

---

### Task 4: Add route and modify SettingsPage

**Files:**
- Modify: `frontend/apps/main/src/router/index.ts:228` (after settings/import-report)
- Modify: `frontend/apps/main/src/pages/SettingsPage.vue:39-67` (coin rate section)

- [ ] **Step 1: Add route to router/index.ts**

Add after line 232 (after `settings/import-report` route):

```typescript
{
  path: 'settings/family/coin-rates',
  name: 'CoinRates',
  component: () => import('@/pages/CoinRatesPage.vue'),
},
```

- [ ] **Step 2: Modify SettingsPage.vue coin rate cell**

Replace lines 39-67 with a simple navigation cell:

```vue
<van-cell
  v-if="authStore.user?.role === 'owner'"
  :title="t('settings.coinRate')"
  :value="t('settings.coinRateValue', { c2s: familyStore.coinCopperToSilver, s2g: familyStore.coinSilverToGold })"
  is-link
  to="/settings/family/coin-rates"
/>
```

Remove the related reactive refs and methods from `<script setup>`:
- Remove: `copperToSilverStr`, `silverToGoldStr`, `savingRates`, `coinRatesExpanded`
- Remove: `saveCoinRates()` function
- Remove: `onMounted` lines that initialize coin rate strings (lines 229-230)

- [ ] **Step 3: Verify changes compile**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: No type errors

- [ ] **Step 4: Commit route and SettingsPage changes**

```bash
git add frontend/apps/main/src/router/index.ts frontend/apps/main/src/pages/SettingsPage.vue
git commit -m "feat(settings): navigate to coin rates page instead of inline expansion"
```

---

### Task 5: Verify and final commit

- [ ] **Step 1: Run full typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS with no errors

- [ ] **Step 2: Run linter**

Run: `cd frontend/apps/main && npm run lint`
Expected: No errors (or auto-fix applied)

- [ ] **Step 3: Test in browser (manual)**

Start dev server: `cd frontend/apps/main && npm run dev`
1. Navigate to Settings → verify coin rate cell shows rates and has arrow
2. Click cell → navigates to `/settings/family/coin-rates`
3. Verify sliders show coin thumbs (silver/gold)
4. Drag slider → input updates
5. Type in input → slider moves
6. Type invalid value (0, 11) → error state shown
7. Click save → toast success → returns to Settings

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: resolve coin rates page issues"
```

---

## Self-Review

**Spec coverage:**
- ✓ Dedicated page at `/settings/family/coin-rates`
- ✓ Two rate rows (铜→银, 银→金)
- ✓ Horizontal layout: slider left, input right
- ✓ Slider range 1-10, integer only
- ✓ SilverCoin thumb for 铜→银, GoldenCoin for 银→金
- ✓ Scale marks (1, 5, 10)
- ✓ Bidirectional sync
- ✓ Save button
- ✓ API integration (existing endpoints)
- ✓ i18n keys added

**Placeholder scan:** No TBDs, TODOs, or vague descriptions.

**Type consistency:** All refs use `number` for internal value, `string` for input field. Component props properly typed.