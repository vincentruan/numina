<template>
  <div class="child-blind-box-page">
    <!-- Clay-styled header band — lavender feature card -->
    <div class="page-header">
      <p class="page-title">{{ t('blindBox.navTitle') }}</p>
    </div>

    <!-- Clay category tabs -->
    <div class="tab-row">
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'draw' }"
        @click="activeTab = 'draw'"
      >{{ t('blindBox.tabDraw') }}</button>
      <button
        class="tab-btn"
        :class="{ active: activeTab === 'history' }"
        @click="activeTab = 'history'"
      >{{ t('blindBox.tabHistory') }}</button>
    </div>

    <!-- Draw Tab -->
    <div v-if="activeTab === 'draw'" class="draw-tab">
      <DrawAnimation
        :animating="animating"
        :revealed="revealed"
        :gift="lastDraw"
        @draw="onDraw"
      />

      <div v-if="bonusDraws.length > 0" class="bonus-section">
        <p class="bonus-divider-label">{{ t('blindBox.bonusDivider', { count: bonusDraws.length }) }}</p>
        <div class="bonus-list" role="list" :aria-label="t('blindBox.bonusListLabel')">
          <div
            v-for="bonus in bonusDraws"
            :key="bonus.id"
            class="bonus-item"
            role="listitem"
          >
            <span class="bonus-text">{{ t('blindBox.bonusItem', { expiry: formatExpiry(bonus.expires_at) }) }}</span>
            <button
              class="btn-use"
              :disabled="loading"
              :aria-label="t('blindBox.bonusItemAriaLabel', { expiry: formatExpiry(bonus.expires_at) })"
              @click="onUseBonusDraw(bonus.id)"
            >
              {{ t('blindBox.useBtn') }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="revealed && lastDraw" class="draw-actions">
        <button class="btn-draw-again" @click="resetDraw">
          {{ t('blindBox.drawAgain') }}
        </button>
      </div>
    </div>

    <!-- History Tab -->
    <div v-if="activeTab === 'history'">
      <van-pull-refresh
        v-model="refreshing"
        :pulling-text="t('common.pullRefresh.pulling')"
        :loosing-text="t('common.pullRefresh.loosing')"
        :loading-text="t('common.pullRefresh.loading')"
        :success-text="t('common.pullRefresh.success')"
        @refresh="onRefresh"
      >
        <DrawHistoryList :draws="draws" />
      </van-pull-refresh>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useBlindBoxStore } from '@/stores/blindBox'
import DrawAnimation from '@/components/blindBox/DrawAnimation.vue'
import DrawHistoryList from '@/components/blindBox/DrawHistoryList.vue'

const { t, locale } = useI18n()
const store = useBlindBoxStore()
const { draws, bonusDraws, loading, lastDraw } = storeToRefs(store)

const activeTab = ref<'draw' | 'history'>('draw')
const animating = ref(false)
const revealed = ref(false)
const refreshing = ref(false)

onMounted(async () => {
  await Promise.all([store.fetchChildDraws(), store.fetchBonusDraws()])
})

async function onDraw() {
  if (animating.value || revealed.value) return

  if (bonusDraws.value.length === 0) {
    showToast(t('toast.noBonusDraws'))
    return
  }

  animating.value = true
  revealed.value = false
  store.clearLastDraw()

  try {
    await store.useBonusDraw(bonusDraws.value[0].id)
    revealed.value = true
  } catch {
    showToast(t('toast.drawFailed'))
  } finally {
    animating.value = false
  }
}

async function onUseBonusDraw(bonusId: string) {
  animating.value = true
  revealed.value = false
  store.clearLastDraw()
  try {
    await store.useBonusDraw(bonusId)
    revealed.value = true
    activeTab.value = 'draw'
  } catch {
    showToast(t('toast.useBonusFailed'))
  } finally {
    animating.value = false
  }
}

function resetDraw() {
  revealed.value = false
  store.clearLastDraw()
}

async function onRefresh() {
  await store.fetchChildDraws()
  refreshing.value = false
}

function formatExpiry(dateStr: string) {
  return new Date(dateStr).toLocaleDateString(locale.value, { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
/* ── Canvas ── */
.child-blind-box-page {
  min-height: 100vh;
  background: var(--color-canvas);
}

/* ── Page header — lavender feature card ── */
.page-header {
  background: var(--color-brand-lavender);
  border-radius: 0 0 var(--radius-xl) var(--radius-xl);
  padding: 24px 20px 20px;
  text-align: center;
  margin-bottom: var(--space-md);
}
[data-theme="dark"] .page-header { color: var(--color-on-feature-lavender); }
.page-title {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
}

/* ── Clay category tabs ── */
.tab-row {
  display: flex;
  gap: 8px;
  padding: 0 var(--space-md);
  margin-bottom: var(--space-md);
}
.tab-btn {
  flex: 1;
  height: 44px;
  border: none;
  border-radius: var(--radius-pill);
  background: transparent;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-muted);
  cursor: pointer;
  transition: all 0.15s;
}
.tab-btn.active {
  background: var(--color-surface-card);
  color: var(--color-ink);
  font-weight: 600;
}

/* ── Draw tab ── */
.draw-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.bonus-section {
  width: 100%;
  padding: 0 var(--space-md);
}

.bonus-divider-label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1.5px;
  text-transform: uppercase;
  color: var(--color-muted);
  text-align: center;
  margin: 0 0 12px;
}

.bonus-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bonus-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--color-surface-soft);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  border: 1px solid var(--color-hairline);
  min-height: 52px;
}

.bonus-text {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
}

/* Use button — 44px touch target */
.btn-use {
  background: var(--color-primary);
  color: var(--color-on-primary);
  border: none;
  border-radius: var(--radius-sm);
  padding: 0 16px;
  height: 44px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
  white-space: nowrap;
}
.btn-use:disabled { opacity: 0.4; cursor: not-allowed; }
.btn-use:active:not(:disabled) { opacity: 0.8; }

/* Draw again button — lavender brand CTA */
.draw-actions {
  width: 100%;
  padding: var(--space-md);
}
.btn-draw-again {
  width: 100%;
  background: var(--color-brand-lavender);
  color: var(--color-ink);
  border: none;
  border-radius: var(--radius-md);
  height: 44px;
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s;
}
.btn-draw-again:active { opacity: 0.8; }
</style>
