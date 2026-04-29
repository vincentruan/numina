<template>
  <div class="child-blind-box-page">
    <van-nav-bar :title="t('blindBox.navTitle')" />

    <van-tabs v-model:active="activeTab" sticky>
      <van-tab :title="t('blindBox.tabDraw')" name="draw" />
      <van-tab :title="t('blindBox.tabHistory')" name="history" />
    </van-tabs>

    <!-- Draw Tab -->
    <div v-if="activeTab === 'draw'" class="draw-tab">
      <DrawAnimation
        :animating="animating"
        :revealed="revealed"
        :gift="lastDraw"
        @draw="onDraw"
      />

      <div v-if="bonusDraws.length > 0" class="bonus-section">
        <van-divider>{{ t('blindBox.bonusDivider', { count: bonusDraws.length }) }}</van-divider>
        <div class="bonus-list" role="list" :aria-label="t('blindBox.bonusListLabel')">
          <div
            v-for="bonus in bonusDraws"
            :key="bonus.id"
            class="bonus-item"
            role="listitem"
          >
            <span>{{ t('blindBox.bonusItem', { expiry: formatExpiry(bonus.expires_at) }) }}</span>
            <van-button
              size="small"
              type="primary"
              :loading="loading"
              :disabled="loading"
              :aria-label="t('blindBox.bonusItemAriaLabel', { expiry: formatExpiry(bonus.expires_at) })"
              @click="onUseBonusDraw(bonus.id)"
            >
              {{ t('blindBox.useBtn') }}
            </van-button>
          </div>
        </div>
      </div>

      <div v-if="revealed && lastDraw" class="draw-actions">
        <van-button block type="primary" @click="resetDraw">{{ t('blindBox.drawAgain') }}</van-button>
      </div>
    </div>

    <!-- History Tab -->
    <div v-if="activeTab === 'history'">
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
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

const { t } = useI18n()
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

async function onUseBonusDraw(bonusId: number) {
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
  return new Date(dateStr).toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.child-blind-box-page {
  min-height: 100vh;
  background: var(--van-background);
}
.draw-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.bonus-section {
  width: 100%;
  padding: 0 16px;
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
  background: var(--van-background-2);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 13px;
}
.draw-actions {
  width: 100%;
  padding: 16px;
}
</style>
