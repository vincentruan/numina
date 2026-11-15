<template>
  <div class="learning-castle-page">
    <van-pull-refresh
      v-model="refreshing"
      :pulling-text="t('common.pullRefresh.pulling')"
      :loosing-text="t('common.pullRefresh.loosing')"
      :loading-text="t('common.pullRefresh.loading')"
      :success-text="t('common.pullRefresh.success')"
      @refresh="onRefresh"
    >
      <KnowledgeCastle
        :castle="castle"
        :state="state"
        :new-topic-id="newTopicId"
        :new-subject="newSubject"
        :new-domain="newDomain"
        @retry="load"
        @window-select="onWindowSelect"
      />
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningCastlePage' })

import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { fetchCastle, getTopicDetail, type CastleIndex, type CastleWindow } from '@/api/learning'
import KnowledgeCastle from '@/components/learning/KnowledgeCastle.vue'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()

const castle = ref<CastleIndex | null>(null)
const state = ref<'loading' | 'error' | 'content'>('loading')
const refreshing = ref(false)
const newTopicId = ref<string | null>(null)
const newSubject = ref<string | null>(null)
const newDomain = ref<string | null>(null)

async function load(): Promise<void> {
  if (!castle.value) state.value = 'loading'
  try {
    castle.value = await fetchCastle()
    state.value = 'content'
  } catch {
    // An error must not render as an empty castle (U5).
    if (!castle.value) state.value = 'error'
  }
}

async function onRefresh(): Promise<void> {
  try {
    await load()
  } finally {
    refreshing.value = false
  }
}

function onWindowSelect(win: CastleWindow): void {
  const mode = win.reason === '复习到期' ? 'review' : 'practice'
  router.push(`/learning/practice/${win.topic_id}?mode=${mode}`)
}

onMounted(() => {
  // Capture ?new= so only that brick animates (F1); then clear it so a
  // subsequent spontaneous open animates nothing (F3).
  const q = route.query.new
  newTopicId.value = typeof q === 'string' && q.length > 0 ? q : null
  if (newTopicId.value) {
    router.replace({ query: { ...route.query, new: undefined } })
    void resolveNewTopicAnchor(newTopicId.value)
  }
  load()
})

/**
 * Castle bricks are aggregated, so the tower/floor to animate is not derivable
 * from the castle payload — resolve the topic's own subject/domain instead.
 * A failure here only loses the animation; it never blocks the castle.
 */
async function resolveNewTopicAnchor(topicId: string): Promise<void> {
  try {
    const topic = await getTopicDetail(topicId)
    newSubject.value = topic.subject ?? null
    newDomain.value = topic.domain ?? ''
  } catch {
    newSubject.value = null
    newDomain.value = null
  }
}
</script>

<style scoped>
.learning-castle-page {
  min-height: 100vh;
  background: var(--color-canvas);
}
</style>
