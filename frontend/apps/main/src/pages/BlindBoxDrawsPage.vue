<template>
  <div class="blind-box-draws-page">
    <van-nav-bar
      :title="t('baby.blindBoxDraws')"
      left-arrow
      @click-left="$router.back()"
    />

    <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
      <EmptyState v-if="!loading && draws.length === 0" :description="t('blindBoxDraw.historyEmpty')" />

      <div v-else class="draws-list">
        <DrawHistoryList :draws="draws" />
      </div>
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useBlindBoxStore } from '@/stores/blindBox'
import { storeToRefs } from 'pinia'
import DrawHistoryList from '@/components/blindBox/DrawHistoryList.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const { t } = useI18n()
const store = useBlindBoxStore()
const { draws, loading } = storeToRefs(store)
const refreshing = ref(false)

onMounted(() => store.fetchDraws())

async function onRefresh() {
  await store.fetchDraws()
  refreshing.value = false
}
</script>

<style scoped>
.blind-box-draws-page {
  min-height: 100vh;
  background: var(--van-background);
}
.draws-list {
  padding: 12px;
}
</style>
