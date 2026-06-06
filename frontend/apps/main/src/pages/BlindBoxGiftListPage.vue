<template>
  <div class="blind-box-gift-list-page">
    <van-nav-bar
      :title="t('blindBox.giftPoolTitle')"
      left-arrow
      @click-left="$router.back()"
      @click-right="$router.push('/blind-box/gifts/new')"
    >
      <template #right>
        <van-icon name="plus" size="18" />
      </template>
    </van-nav-bar>

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <EmptyState v-if="!loading && gifts.length === 0" :description="t('blindBox.giftPoolEmpty')" />

      <div v-else class="gift-list" role="list" :aria-label="t('blindBox.giftPoolTitle')">
        <div
          v-for="gift in gifts"
          :key="gift.id"
          class="gift-item"
          role="listitem"
          :aria-label="t('blindBox.giftScoreAriaLabel', { emoji: gift.emoji ?? '', name: gift.name, score: gift.value_score })"
        >
          <div class="gift-info">
            <span class="gift-emoji" aria-hidden="true">{{ gift.emoji ?? '🎁' }}</span>
            <div class="gift-details">
              <span class="gift-name">{{ gift.name }}</span>
              <span class="gift-score">{{ t('blindBox.giftScore', { score: gift.value_score }) }}</span>
            </div>
          </div>
          <div class="gift-actions">
            <van-button
              size="small"
              type="primary"
              plain
              :aria-label="`${t('blindBox.editGift')} ${gift.name}`"
              @click="$router.push(`/blind-box/gifts/${gift.id}/edit`)"
            >
              {{ t('blindBox.editGift') }}
            </van-button>
            <van-button
              size="small"
              type="danger"
              plain
              :aria-label="`${t('blindBox.deleteGift')} ${gift.name}`"
              @click="onDelete(gift)"
            >
              {{ t('blindBox.deleteGift') }}
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
        {{ t('blindBox.configBtn') }}
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useBlindBoxStore } from '@/stores/blindBox'
import EmptyState from '@/components/common/EmptyState.vue'
import { storeToRefs } from 'pinia'
import type { BlindBoxGift } from '@/types/blindBox'

const { t } = useI18n()
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
    title: t('blindBox.deleteTitle'),
    message: t('toast.confirmDelete', { name: gift.name }),
  })
  await store.deleteGift(gift.id)
  showToast(t('toast.deleteSuccess'))
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
