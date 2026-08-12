<template>
  <div class="badges-page">
    <PageHeader :title="t('badges.title')" />
    <van-pull-refresh
      v-model="refreshing"
      :pulling-text="t('common.pullRefresh.pulling')"
      :loosing-text="t('common.pullRefresh.loosing')"
      :loading-text="t('common.pullRefresh.loading')"
      :success-text="t('common.pullRefresh.success')"
      @refresh="onRefresh"
    >
      <!-- Loading skeleton -->
      <div v-if="loading && !refreshing" class="badges-skeleton">
        <van-skeleton title :row="3" :row-width="['100%', '80%', '60%']" />
        <van-skeleton title :row="3" :row-width="['100%', '80%', '60%']" style="margin-top: 16px" />
      </div>

      <!-- Empty state -->
      <EmptyState v-else-if="!hasAnyData" :illustration="noRecordsSvg" :text="t('badges.empty')" />

      <!-- Badge wall -->
      <BadgeWall v-else :dimensions="dimensions" />
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChildBadges' })

import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { usePageLoading } from '@/composables/usePageLoading'
import { getBadges, type BadgeDimensionData } from '@/api/literacy'
import BadgeWall from '@/components/literacy/BadgeWall.vue'
import EmptyState from '@/components/EmptyState.vue'
import { noRecordsSvg } from '@numina/assets/empty-states'

const { t } = useI18n()
const { increment, decrement } = usePageLoading()

const loading = ref(true)
const refreshing = ref(false)
const dimensions = ref<BadgeDimensionData[]>([])

const hasAnyData = computed(() =>
  dimensions.value.some(
    (d) => d.current_badge !== null || d.history.length > 0,
  ),
)

async function load() {
  loading.value = true
  try {
    const res = await getBadges()
    dimensions.value = res.dimensions
  } catch {
    dimensions.value = []
  } finally {
    loading.value = false
  }
}

async function onRefresh() {
  await load()
  refreshing.value = false
}

onMounted(async () => {
  increment()
  try {
    await load()
  } finally {
    decrement()
  }
})
</script>

<style scoped>
.badges-page {
  padding: var(--space-md);
  background: var(--color-canvas);
  min-height: 100vh;
}

.badges-skeleton {
  display: flex;
  flex-direction: column;
}

.badges-empty {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted-soft);
  text-align: center;
  padding: 40px 16px;
}
</style>
