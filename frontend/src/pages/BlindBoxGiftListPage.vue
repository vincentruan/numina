<template>
  <div class="blind-box-gift-list-page">
    <van-nav-bar
      title="礼物池"
      left-arrow
      @click-left="$router.back()"
      @click-right="$router.push('/blind-box/gifts/new')"
    >
      <template #right>
        <van-icon name="plus" size="18" />
      </template>
    </van-nav-bar>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <van-empty v-if="!loading && gifts.length === 0" description="礼物池为空，点击右上角添加礼物" />

      <div v-else class="gift-list" role="list" aria-label="礼物池列表">
        <div
          v-for="gift in gifts"
          :key="gift.id"
          class="gift-item"
          role="listitem"
          :aria-label="`${gift.emoji ?? ''} ${gift.name}，价值分 ${gift.value_score}`"
        >
          <div class="gift-info">
            <span class="gift-emoji" aria-hidden="true">{{ gift.emoji ?? '🎁' }}</span>
            <div class="gift-details">
              <span class="gift-name">{{ gift.name }}</span>
              <span class="gift-score">价值分: {{ gift.value_score }}/10</span>
            </div>
          </div>
          <div class="gift-actions">
            <van-button
              size="small"
              type="primary"
              plain
              :aria-label="`编辑 ${gift.name}`"
              @click="$router.push(`/blind-box/gifts/${gift.id}/edit`)"
            >
              编辑
            </van-button>
            <van-button
              size="small"
              type="danger"
              plain
              :aria-label="`删除 ${gift.name}`"
              @click="onDelete(gift)"
            >
              删除
            </van-button>
          </div>
        </div>
      </div>
    </van-pull-refresh>

    <div class="page-footer">
      <van-button
        block
        plain
        type="default"
        @click="$router.push('/blind-box/config')"
      >
        ⚙️ 盲盒配置
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useBlindBoxStore } from '@/stores/blindBox'
import { storeToRefs } from 'pinia'
import type { BlindBoxGift } from '@/types/blindBox'

const store = useBlindBoxStore()
const { gifts, loading } = storeToRefs(store)
const refreshing = ref(false)

onMounted(() => store.fetchGifts())

async function onRefresh() {
  await store.fetchGifts()
  refreshing.value = false
}

async function onDelete(gift: BlindBoxGift) {
  await showConfirmDialog({
    title: '删除礼物',
    message: `⚠️ 确定要删除「${gift.name}」吗？`,
  })
  await store.deleteGift(gift.id)
  showToast('🗑️ 已删除')
}
</script>

<style scoped>
.blind-box-gift-list-page {
  min-height: 100vh;
  background: var(--van-background);
}
.gift-list {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.gift-item {
  background: var(--van-background-2);
  border-radius: 10px;
  padding: 12px 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.gift-info {
  display: flex;
  align-items: center;
  gap: 10px;
}
.gift-emoji {
  font-size: 28px;
}
.gift-details {
  display: flex;
  flex-direction: column;
}
.gift-name {
  font-size: 15px;
  font-weight: 600;
}
.gift-score {
  font-size: 12px;
  color: var(--van-text-color-2);
}
.gift-actions {
  display: flex;
  gap: 6px;
}
.page-footer {
  padding: 16px;
}
</style>
