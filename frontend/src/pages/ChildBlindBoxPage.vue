<template>
  <div class="child-blind-box-page">
    <van-nav-bar title="🎁 盲盒抽奖" />

    <van-tabs v-model:active="activeTab" sticky>
      <van-tab title="抽奖" name="draw" />
      <van-tab title="历史" name="history" />
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
        <van-divider>免费抽奖机会 ({{ bonusDraws.length }})</van-divider>
        <div class="bonus-list" role="list" aria-label="免费抽奖机会列表">
          <div
            v-for="bonus in bonusDraws"
            :key="bonus.id"
            class="bonus-item"
            role="listitem"
          >
            <span>🎀 免费抽奖（{{ formatExpiry(bonus.expires_at) }}到期）</span>
            <van-button
              size="small"
              type="primary"
              :loading="loading"
              :aria-label="`使用免费抽奖机会，${formatExpiry(bonus.expires_at)}到期`"
              @click="onUseBonusDraw(bonus.id)"
            >
              使用
            </van-button>
          </div>
        </div>
      </div>

      <div v-if="revealed && lastDraw" class="draw-actions">
        <van-button block type="primary" @click="resetDraw">再抽一次</van-button>
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
import { storeToRefs } from 'pinia'
import { useBlindBoxStore } from '@/stores/blindBox'
import DrawAnimation from '@/components/blindBox/DrawAnimation.vue'
import DrawHistoryList from '@/components/blindBox/DrawHistoryList.vue'

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

  // Tap-to-draw only works when there are bonus draws available.
  // Chore-based draws are triggered from the task completion flow (not here).
  if (bonusDraws.value.length === 0) {
    showToast('⚠️ 暂无免费抽奖机会，完成任务后可获得')
    return
  }

  animating.value = true
  revealed.value = false
  store.clearLastDraw()

  try {
    await store.useBonusDraw(bonusDraws.value[0].id)
    revealed.value = true
  } catch {
    showToast('❌ 抽奖失败，请稍后再试')
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
    showToast('❌ 使用失败，请稍后再试')
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
