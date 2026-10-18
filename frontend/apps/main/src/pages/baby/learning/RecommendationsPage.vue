<template>
  <div class="recommendations-page">
    <PageHeader :title="t('learning.smartRecommendations')" />
    <van-skeleton v-if="loading" :rows="5" :round="true" />
    <template v-else>
      <EmptyState v-if="recommendations.length === 0" :description="t('learning.noRecommendations')" />
      <van-cell-group v-else inset>
        <van-cell
          v-for="topic in recommendations"
          :key="topic.topic_id"
          :title="topic.topic_name"
        >
          <template #label>
            <div class="reason-tags">
              <van-tag
                v-for="reason in topic.reasons"
                :key="reason"
                :type="reasonToTagType(reason)"
                round
                plain
              >
                {{ reason }}
              </van-tag>
            </div>
          </template>
        </van-cell>
      </van-cell-group>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Recommendations' })

import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useBabyStore } from '@/stores/baby'
import { getRecommendations, type RecommendationTopicItem } from '@/api/learning'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const { t } = useI18n()
const babyStore = useBabyStore()
const loading = ref(true)
const recommendations = ref<RecommendationTopicItem[]>([])

function reasonToTagType(reason: string): 'primary' | 'success' | 'warning' | 'default' {
  if (reason === 'weak_point') return 'warning'
  if (reason === 'mastery_gained') return 'success'
  return 'primary'
}

onMounted(async () => {
  const childId = babyStore.selectedChildId
  if (!childId) {
    loading.value = false
    return
  }
  try {
    const res = await getRecommendations(childId)
    recommendations.value = res.path?.topics ?? []
  } catch {
    recommendations.value = []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.recommendations-page {
  min-height: 100vh;
  padding-bottom: 20px;
}

.reason-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
}
</style>
