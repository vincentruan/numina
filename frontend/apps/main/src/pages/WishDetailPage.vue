<template>
  <div class="wish-detail-page">
    <PageHeader :title="t('wish.detail')" />

    <template v-if="wish">
      <!-- Hero Card: Pastel Cloud Gradient -->
      <div class="hero-card" :class="wish.status">
        <!-- Decorative blob (handled via ::before in CSS) -->

        <div class="hero-top">
          <!-- Status icon -->
          <div class="hero-status-icon">
            <van-icon v-if="wish.status === 'realized'" name="success" size="28" />
            <van-icon v-else-if="wish.status === 'cancelled'" name="cross" size="28" />
            <van-icon v-else name="star" size="28" />
          </div>
          <div class="hero-info">
            <div class="hero-name">{{ wish.name }}</div>
            <div class="hero-category">
              <template v-if="wish.category">
                <template v-if="wish.category.icon && wish.category.icon.startsWith('icon-')">
                  <SvgIcon :name="getIconId(wish.category.icon)" style="width:1em;height:1em;vertical-align:-0.15em" />
                </template>
                <span v-else-if="wish.category.icon">{{ wish.category.icon }}</span>
                {{ wish.category.name }}
              </template>
              <template v-else>{{ t('wish.uncategorized') }}</template>
            </div>
          </div>
          <!-- Status badge -->
          <van-tag :type="statusType" size="medium" class="hero-status-tag">{{ statusText }}</van-tag>
        </div>

        <!-- Stats row -->
        <div class="hero-values">
          <div class="hero-value-item">
            <div class="hero-value-label">{{ t('wish.expectedPrice') }}</div>
            <div class="hero-value-num">
              <span v-if="wish.expected_price">{{ currency.formatConverted(wish.expected_price, wish.currency) }}</span>
              <span v-else class="hero-value-unset">{{ t('wish.unset') }}</span>
            </div>
          </div>
          <div class="hero-value-item">
            <div class="hero-value-label">{{ t('wish.priority') }}</div>
            <div class="hero-value-num">{{ priorityText }}</div>
          </div>
          <div class="hero-value-item">
            <div class="hero-value-label">{{ t('wish.status') }}</div>
            <div class="hero-value-num">{{ statusText }}</div>
          </div>
        </div>

        <div v-if="wish.realized_asset_id" class="hero-realized-info">
          <p v-if="wish.fulfilled_at" class="fulfilled-date">
            {{ t('wish.fulfilledAt', { date: parseApiDate(wish.fulfilled_at).toLocaleDateString(locale, { year: 'numeric', month: '2-digit', day: '2-digit' }) }) }}
          </p>
          <router-link :to="`/assets/${wish.realized_asset_id}`">
            {{ t('wish.realizedAsset') }} →
          </router-link>
        </div>

        <div v-if="wish.description" class="hero-description">{{ wish.description }}</div>
      </div>

      <!-- Savings progress + record/log dialogs. -->
      <WishSavingsProgress
        v-if="wish.status === 'pending'"
        :wish="wish"
        :net-worth="dashboardStore.overview?.net_worth ?? 0"
        @record="recordShow = true"
        @show-log="logShow = true"
      />
      <WishSavingsRecordDialog v-model:show="recordShow" :wish-id="wish.id" @saved="onSavingsChanged" />
      <WishSavingsLogDialog v-model:show="logShow" :wish-id="wish.id" @changed="onSavingsChanged" />

      <!-- Detail Info -->
      <van-cell-group inset :title="t('wish.detailInfo')">
        <van-cell :title="t('wish.status')" :value="statusText">
          <template #value>
            <van-tag :type="statusType">{{ statusText }}</van-tag>
          </template>
        </van-cell>
        <van-cell :title="t('wish.expectedPrice')">
          <template #value>
            <span v-if="wish.expected_price">{{ currency.formatIn(wish.expected_price, wish.currency) }}</span>
            <span v-else class="unset">{{ t('wish.unset') }}</span>
          </template>
        </van-cell>
        <van-cell :title="t('wish.priority')" :value="priorityText" />
        <van-cell :title="t('asset.category')" :value="wish.category?.name || t('wish.uncategorized')" />
        <van-cell :title="t('wish.createdAt')" :value="formatDate(wish.created_at)" />
        <van-cell :title="t('wish.updatedAt')" :value="formatDate(wish.updated_at)" />
      </van-cell-group>

      <!-- Notes -->
      <van-cell-group v-if="wish.description" inset :title="t('wish.notes')">
        <van-cell :title="wish.description" />
      </van-cell-group>

      <!-- Actions -->
      <div class="actions">
        <template v-if="wish.status === 'pending'">
          <van-button v-if="wish.converts_to_asset" block type="primary" @click="showRealizeDialog = true">
            {{ t('wish.convertToAsset') }}
          </van-button>
          <!-- Passive '问 AI 规划储蓄' button → /ai/chat?source=wish_detail&id= -->
          <van-button block type="default" plain @click="router.push({ name: 'AIChat', query: { source: 'wish_detail', id: wish.id } })">
            {{ t('wish.advice.askPlanSavings') }}
          </van-button>
          <van-button block type="default" plain @click="$router.push(`/wishes/${wish.id}/edit`)">
            {{ t('common.edit') }}
          </van-button>
          <van-button block type="warning" plain @click="onCancel">
            {{ t('wish.cancelWish') }}
          </van-button>
        </template>
        <template v-else-if="wish.status === 'cancelled'">
          <van-button block type="success" plain @click="onReactivate">
            {{ t('wish.reactivate') }}
          </van-button>
          <van-button block type="primary" plain @click="$router.push(`/wishes/${wish.id}/edit`)">
            {{ t('common.edit') }}
          </van-button>
        </template>
        <template v-else>
          <van-button block type="primary" plain @click="$router.push(`/wishes/${wish.id}/edit`)">
            {{ t('common.edit') }}
          </van-button>
        </template>
        <van-button block type="danger" plain :loading="deleting" class="delete-btn" @click="onDelete">
          {{ t('common.delete') }}
        </van-button>
      </div>

      <!-- High-interest-debt hint + 忽略 button (only when the
           current wish has monthly_saving>0 + high-interest debt + not ignored). -->
      <div v-if="showDebtWarning" class="debt-warning-bar">
        <van-icon name="warning-o" />
        <span>{{ t('wish.debtWarning.detailHint') }}</span>
        <van-button size="mini" plain @click="ignoreDebtWarning">
          {{ t('wish.debtWarning.ignore') }}
        </van-button>
      </div>

      <!-- Realize Dialog -->
      <van-popup v-model:show="showRealizeDialog" round position="bottom" :style="{ height: '60%' }">
        <div class="realize-dialog">
          <div class="dialog-title">{{ t('wish.dialogTitle') }}</div>
          <van-form @submit="onRealize">
            <van-cell-group inset>
              <van-field
                v-model="realizeForm.purchase_price"
                name="purchase_price"
                :label="t('asset.purchasePrice')"
                type="number"
                inputmode="decimal"
                :placeholder="t('wish.purchasePricePlaceholder')"
                :rules="[{ required: true, message: t('wish.purchasePriceRequired') }]"
              />
              <van-field
                v-model="realizeForm.purchase_date"
                name="purchase_date"
                :label="t('asset.purchaseDate')"
                :placeholder="t('wish.selectDate')"
                readonly
                :rules="[{ required: true, message: t('wish.selectDateRequired') }]"
                @click="showDatePicker = true"
              />
              <van-field
                v-model="selectedCategoryName"
                name="category"
                :label="t('asset.category')"
                :placeholder="t('wish.selectCategory')"
                readonly
                @click="showCategoryPicker = true"
              />
            </van-cell-group>
            <div style="margin: 16px">
              <van-button round block type="primary" native-type="submit" :loading="realizing">
                {{ t('wish.confirmConvert') }}
              </van-button>
            </div>
          </van-form>
        </div>
      </van-popup>

      <!-- Date Picker -->
      <van-calendar v-model:show="showDatePicker" @confirm="onDateConfirm" />

      <!-- Category Picker -->
      <van-popup v-model:show="showCategoryPicker" round position="bottom">
        <div class="category-picker-popup">
          <div class="category-type-tabs">
            <div
              class="type-tab"
              :class="{ active: selectedAssetType === 'physical' }"
              @click="selectedAssetType = 'physical'"
            >{{ t('categoryGrid.physical') }}</div>
            <div
              class="type-tab"
              :class="{ active: selectedAssetType === 'financial' }"
              @click="selectedAssetType = 'financial'"
            >{{ t('categoryGrid.financial') }}</div>
          </div>
          <div class="category-grid">
            <div
              v-for="cat in filteredCategories"
              :key="cat.id"
              class="category-item"
              :class="{ selected: realizeForm.category_id === cat.id }"
              @click="selectCategory(cat.id)"
            >
              <SvgIcon :name="getIconId(cat.icon)" class="cat-icon" />
              <span class="cat-name">{{ cat.name }}</span>
            </div>
          </div>
        </div>
      </van-popup>
    </template>

    </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, toRef } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useWishStore } from '@/stores/wish'
import { useDashboardStore } from '@/stores/dashboard'
import { parseApiDate } from '@/utils/format'
import { useLiabilityStore } from '@/stores/liability'
import { useDebtWarning } from '@/composables/useDebtWarning'
import { getCategories } from '@/api/categories'
import type { Category, Wish } from '@/types'
import { realizeWish, setIgnoreDebtWarning as setIgnoreDebtWarningApi } from '@/api/wishes'
import PageHeader from '@/components/common/PageHeader.vue'
import WishSavingsProgress from '@/components/wishes/WishSavingsProgress.vue'
import WishSavingsRecordDialog from '@/components/wishes/WishSavingsRecordDialog.vue'
import WishSavingsLogDialog from '@/components/wishes/WishSavingsLogDialog.vue'
import { getIconId } from '@/utils/icon'
import { usePageLoading } from '@/composables/usePageLoading'
import { useCurrency } from '@/composables/useCurrency'
import { useExchangeRate } from '@/composables/useExchangeRate'

const { t, locale } = useI18n()

const route = useRoute()
const router = useRouter()
const wishStore = useWishStore()
const dashboardStore = useDashboardStore()
const liabilityStore = useLiabilityStore()
const deleting = ref(false)
const acting = ref(false)
const { increment, decrement } = usePageLoading()
const currency = useCurrency()
const { ensureRate } = useExchangeRate()

// Realize dialog
const showRealizeDialog = ref(false)
const realizing = ref(false)
const showDatePicker = ref(false)
const showCategoryPicker = ref(false)

// Savings record + log dialogs.
const recordShow = ref(false)
const logShow = ref(false)

async function onSavingsChanged() {
  // Refresh the wish so saved_amount + savings_count update after record/delete.
  if (wish.value) {
    await wishStore.fetchWish(wish.value.id)
  }
}
const realizeForm = ref({
  purchase_price: '',
  purchase_date: '',
  category_id: ''
})
const categories = ref<Category[]>([])

const wish = computed(() => wishStore.currentWish)

// High-interest-debt ↔ wish linkage hint + 忽略 button.
// Pass a single-element wishes ref so shouldWarnForWish + ignore_debt_warning
// work on the current wish; the composable only needs liabilities + hasHighInterestDebt.
const wishesRef = ref<Wish[]>([])
const debtWarning = useDebtWarning(toRef(liabilityStore, 'liabilities'), wishesRef)
const showDebtWarning = computed(
  () => wish.value ? debtWarning.shouldWarnForWish(wish.value) : false,
)

async function ignoreDebtWarning() {
  if (!wish.value) return
  try {
    await setIgnoreDebtWarningApi(wish.value.id, true)
    wishStore.currentWish = { ...wish.value, ignore_debt_warning: true }
    showSuccessToast(t('common.saved'))
  } catch {
    showFailToast(t('toast.operationFailed'))
  }
}

const statusMap = computed<Record<string, { text: string; type: 'primary' | 'success' | 'warning' | 'danger' | 'default' }>>(() => ({
  pending: { text: t('wish.statusPending'), type: 'primary' },
  realized: { text: t('wish.statusRealized'), type: 'success' },
  cancelled: { text: t('wish.statusCancelled'), type: 'default' }
}))

const statusText = computed(() => statusMap.value[wish.value?.status || '']?.text || '')
const statusType = computed(() => statusMap.value[wish.value?.status || '']?.type || 'default')

const priorityMap = computed<Record<string, string>>(() => ({
  low: t('wish.priorityLow'),
  medium: t('wish.priorityMedium'),
  high: t('wish.priorityHigh'),
}))
const priorityText = computed(() => priorityMap.value[wish.value?.priority ?? ''] ?? t('wish.unset'))

const selectedAssetType = ref<'physical' | 'financial'>('physical')

const filteredCategories = computed(() =>
  categories.value.filter(c => c.asset_type === selectedAssetType.value)
)

const selectedCategoryName = computed(() => {
  if (!realizeForm.value.category_id) return ''
  const cat = categories.value.find(c => c.id === realizeForm.value.category_id)
  return cat?.name ?? ''
})

function formatDate(dateStr: string) {
  return parseApiDate(dateStr).toLocaleDateString(locale.value, { year: 'numeric', month: '2-digit', day: '2-digit' })
}

function onDateConfirm(date: Date) {
  realizeForm.value.purchase_date = date.toISOString().slice(0, 10)
  showDatePicker.value = false
}

function selectCategory(id: string) {
  realizeForm.value.category_id = id
  showCategoryPicker.value = false
}

async function onRealize() {
  if (!wish.value) return
  realizing.value = true
  try {
    const payload = {
      purchase_price: parseFloat(realizeForm.value.purchase_price),
      purchase_date: realizeForm.value.purchase_date,
      category_id: realizeForm.value.category_id || undefined
    }
    const res = await realizeWish(wish.value.id, payload)
    showSuccessToast(t('toast.assetConverted'))
    showRealizeDialog.value = false
    router.push(`/assets/${res.data.id}`)
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    realizing.value = false
  }
}

async function onCancel() {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmCancel') })
    acting.value = true
    await wishStore.updateWish(wish.value!.id, { status: 'cancelled' })
    showSuccessToast(t('toast.wishCancelled'))
  } catch {
    // cancelled
  } finally {
    acting.value = false
  }
}

async function onReactivate() {
  acting.value = true
  try {
    await wishStore.updateWish(wish.value!.id, { status: 'pending' })
    showSuccessToast(t('toast.wishReactivated'))
  } finally {
    acting.value = false
  }
}

async function onDelete() {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmDelete', { name: wish.value?.name }) })
    deleting.value = true
    await wishStore.deleteWish(wish.value!.id)
    showSuccessToast(t('toast.deleteSuccess'))
    router.back()
  } catch {
    // cancelled
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  increment()
  try {
    const id = route.params.id as string
    await wishStore.fetchWish(id)
    wishesRef.value = wishStore.currentWish ? [wishStore.currentWish] : []

    // Prefetch exchange rate for this wish's currency so converted amounts render
    // synchronously on first paint.
    if (wish.value?.currency && wish.value.currency !== 'CNY') {
      void ensureRate(wish.value.currency)
    }

    // load debt thresholds + liabilities so the high-interest hint can render.
    void debtWarning.loadThresholds()
    liabilityStore.fetchLiabilities().catch(() => {})

    // P1 fix: load dashboard overview so afford bar shows actual net worth.
    if (!dashboardStore.overview) {
      void dashboardStore.fetchOverview()
    }

    // Pre-fill form
    if (wish.value?.expected_price) {
      realizeForm.value.purchase_price = String(wish.value.expected_price)
    }
    if (wish.value?.category_id) {
      realizeForm.value.category_id = wish.value.category_id
    }

    // Load categories for picker
    const catRes = await getCategories()
    categories.value = catRes.data

    // Pre-set asset type tab based on wish's existing category
    if (wish.value?.category_id) {
      const cat = categories.value.find(c => c.id === wish.value!.category_id)
      if (cat) selectedAssetType.value = cat.asset_type as 'physical' | 'financial'
    }
  } finally {
    decrement()
  }
})
</script>

<style scoped>
.wish-detail-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}

/* W5 (Plan B T8): debt-warning hint bar */
.debt-warning-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 8px 16px;
  padding: 8px 12px;
  background: rgba(255, 151, 106, 0.12);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-primary, #323233);
}
.debt-warning-bar span {
  flex: 1;
}

/* ── Hero Card: Pastel Cloud Gradient (light mode) ── */
.hero-card {
  background:
    linear-gradient(135deg,
      rgba(239, 44, 193, 0.10) 0%,
      rgba(189, 187, 255, 0.18) 45%,
      rgba(160, 195, 255, 0.14) 100%),
    #ffffff;
  padding: 20px 16px 16px;
  color: #000000;
  position: relative;
  overflow: hidden;
}

/* Decorative soft blob */
.hero-card::before {
  content: '';
  position: absolute;
  top: -40px;
  right: -30px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(189, 187, 255, 0.22) 0%, transparent 70%);
  pointer-events: none;
}

/* Dark mode */
[data-theme='dark'] .hero-card {
  background:
    linear-gradient(135deg,
      rgba(189, 187, 255, 0.08) 0%,
      rgba(189, 187, 255, 0.04) 50%,
      transparent 100%),
    #010120;
  color: var(--text-primary);
}
[data-theme='dark'] .hero-card::before {
  background: radial-gradient(circle, rgba(189, 187, 255, 0.10) 0%, transparent 70%);
}

/* Realized: soft green tint over gradient base */
.hero-card.realized {
  background:
    linear-gradient(135deg,
      rgba(5, 150, 105, 0.10) 0%,
      rgba(189, 187, 255, 0.12) 50%,
      rgba(160, 195, 255, 0.10) 100%),
    #ffffff;
}
[data-theme='dark'] .hero-card.realized {
  background:
    linear-gradient(135deg,
      rgba(5, 150, 105, 0.12) 0%,
      rgba(189, 187, 255, 0.06) 100%),
    #010120;
}

/* Cancelled: muted overlay */
.hero-card.cancelled {
  background:
    linear-gradient(135deg,
      rgba(0, 0, 0, 0.04) 0%,
      rgba(0, 0, 0, 0.02) 100%),
    #f5f5f5;
  color: rgba(0, 0, 0, 0.55);
}
[data-theme='dark'] .hero-card.cancelled {
  background:
    linear-gradient(135deg,
      rgba(255, 255, 255, 0.03) 0%,
      rgba(255, 255, 255, 0.01) 100%),
    #0d0d1a;
  color: rgba(255, 255, 255, 0.50);
}

.hero-top {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
  position: relative;
}

/* Status icon container: glass badge */
.hero-status-icon {
  width: 52px;
  height: 52px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(0, 0, 0, 0.08);
  color: rgba(0, 0, 0, 0.65);
}
[data-theme='dark'] .hero-status-icon {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.75);
}
.hero-card.realized .hero-status-icon {
  background: rgba(5, 150, 105, 0.10);
  border-color: rgba(5, 150, 105, 0.20);
  color: #059669;
}
[data-theme='dark'] .hero-card.realized .hero-status-icon {
  color: var(--color-trend-down);
}

.hero-info {
  flex: 1;
  min-width: 0;
}

/* Wish name: display-level, tight negative tracking */
.hero-name {
  font-size: clamp(18px, 5vw, 22px);
  font-weight: 500;
  letter-spacing: -0.22px;
  line-height: 1.15;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #000000;
}
[data-theme='dark'] .hero-name {
  color: var(--text-primary);
}
.hero-card.cancelled .hero-name {
  color: rgba(0, 0, 0, 0.50);
}
[data-theme='dark'] .hero-card.cancelled .hero-name {
  color: var(--text-tertiary);
}

/* Mono label for category */
.hero-category {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.45);
  font-family: 'Georgia', monospace;
}
[data-theme='dark'] .hero-category {
  color: var(--text-tertiary);
}

.hero-status-tag {
  flex-shrink: 0;
}

/* Stats row: glass container, 8px radius, dark-blue-tinted shadow */
.hero-values {
  display: flex;
  align-items: flex-start;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  padding: 12px 0;
  margin-bottom: 8px;
  box-shadow: rgba(1, 1, 32, 0.08) 0px 2px 8px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
[data-theme='dark'] .hero-values {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: rgba(1, 1, 32, 0.40) 0px 2px 8px;
}

.hero-value-item {
  flex: 1;
  text-align: center;
  border-right: 1px solid rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .hero-value-item {
  border-right-color: rgba(255, 255, 255, 0.12);
}
.hero-value-item:last-child {
  border-right: none;
}

/* Mono label for value headers */
.hero-value-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.40);
  font-family: 'Georgia', monospace;
  margin-bottom: 4px;
}
[data-theme='dark'] .hero-value-label {
  color: var(--text-tertiary);
}

.hero-value-num {
  font-size: 16px;
  font-weight: 500;
  letter-spacing: -0.16px;
  color: #000000;
}
[data-theme='dark'] .hero-value-num {
  color: var(--text-primary);
}

.hero-value-unset {
  font-size: 13px;
  color: var(--text-secondary);
}

.hero-realized-info {
  font-size: 12px;
  font-weight: 500;
  color: #059669;
  text-align: center;
  margin-bottom: 4px;
}
[data-theme='dark'] .hero-realized-info {
  color: var(--color-trend-down);
}

.hero-description {
  font-size: 14px;
  color: rgba(0, 0, 0, 0.55);
  line-height: 1.5;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  margin-top: 4px;
}
[data-theme='dark'] .hero-description {
  color: rgba(255, 255, 255, 0.50);
  border-top-color: rgba(255, 255, 255, 0.10);
}

.actions {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.delete-btn {
  margin-top: 4px;
}

.realize-dialog {
  padding: 16px;
}

.dialog-title {
  font-size: 16px;
  font-weight: 500;
  letter-spacing: -0.16px;
  text-align: center;
  margin-bottom: 16px;
  color: var(--text-primary);
}

/* Category picker popup */
.category-picker-popup {
  padding: 16px;
  max-height: 60vh;
  overflow-y: auto;
}
.category-type-tabs {
  display: flex;
  background: var(--van-background-2);
  border-radius: 10px;
  padding: 3px;
  margin-bottom: 12px;
}
.type-tab {
  flex: 1;
  text-align: center;
  padding: 8px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--van-text-color-2);
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
}
.type-tab.active {
  background: var(--van-primary-color);
  color: #fff;
  font-weight: 600;
}
[data-theme='dark'] .type-tab.active {
  background: var(--color-lavender, #bdbbff);
  color: #010120;
}
.category-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}
.category-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 4px;
  border-radius: 10px;
  background: var(--van-background-2);
  border: 1.5px solid transparent;
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, transform 0.15s;
}
.category-item:active {
  transform: scale(0.95);
}
.category-item.selected {
  border-color: var(--van-primary-color);
  background: color-mix(in srgb, var(--van-primary-color) 12%, transparent);
}
.cat-icon {
  width: 22px;
  height: 22px;
  fill: currentColor;
}
.cat-name {
  font-size: 10px;
  color: var(--van-text-color-2);
  margin-top: 4px;
  text-align: center;
  line-height: 1.2;
}
.category-item.selected .cat-name {
  color: var(--van-primary-color);
}
</style>