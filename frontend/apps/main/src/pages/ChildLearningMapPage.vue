<template>
  <div class="child-learning-map-page">
    <PageHeader :title="t('learning.childMap', { name: childName })" />

    <van-skeleton v-if="loading && mapItems.length === 0" :rows="5" :round="true" />

    <template v-else>
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <!-- Empty state -->
        <EmptyState v-if="mapItems.length === 0" :description="t('learning.noProgress')" />

        <template v-else>
          <!-- DNA Graph Visualization -->
          <DnaGraph2D :items="mapItems" :loading="loading" />
        </template>
      </van-pull-refresh>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChildLearningMap' })

import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showFailToast } from 'vant'
import { usePageLoading } from '@/composables/usePageLoading'
import {
  getChildMap,
  getTopicsBatch,
  getLearningChildren,
  type ProgressResponse,
  type TopicResponse,
} from '@/api/learning'
import http from '@/api'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import DnaGraph2D from '@/components/learning/DnaGraph2D.vue'

const { t } = useI18n()
const route = useRoute()
const { increment, decrement } = usePageLoading()

const childId = route.params.childId as string
const childName = ref('')

const loading = ref(true)
const refreshing = ref(false)
const progressList = ref<ProgressResponse[]>([])
const topicMap = ref<Map<string, TopicResponse>>(new Map())

// Composite items: progress + topic
const mapItems = computed(() =>
  progressList.value
    .filter((p) => topicMap.value.has(p.topic_id))
    .map((p) => ({
      ...p,
      topic: topicMap.value.get(p.topic_id)!,
    })),
)

async function load() {
  loading.value = true
  try {
    const [progress, children] = await Promise.all([
      getChildMap(childId),
      getLearningChildren(),
    ])
    progressList.value = progress

    // Resolve child display name from API (don't rely on query param)
    if (!childName.value) {
      const child = children.find((c) => String(c.child_id) === String(childId))
      childName.value = child?.child_name || ''
    }
    // Fallback: if children list didn't include the child, fetch directly
    if (!childName.value) {
      try {
        const allChildren = await http.get('/family/children')
        const list = allChildren.data as Array<{ id: string; display_name: string }>
        const found = list.find((c) => String(c.id) === String(childId))
        childName.value = found?.display_name || childId
      } catch {
        childName.value = childId
      }
    }

    // Fetch topic details in batch (single request instead of N+1)
    const uniqueTopicIds = [...new Set(progress.map((p) => p.topic_id))]
    const topicDetails = uniqueTopicIds.length > 0
      ? await getTopicsBatch(uniqueTopicIds)
      : []
    const newMap = new Map<string, TopicResponse>()
    for (const topic of topicDetails) {
      newMap.set(topic.id, topic)
    }
    topicMap.value = newMap
  } catch {
    showFailToast(t('toast.operationFailed'))
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
  // Use query param as immediate hint; load() will resolve from API
  childName.value = (route.query.name as string) || ''
  await load()
  decrement()
})
</script>

<style scoped>
.child-learning-map-page {
  min-height: 100vh;
  padding-bottom: 20px;
}
</style>
