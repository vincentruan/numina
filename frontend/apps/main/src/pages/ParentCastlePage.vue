<template>
  <div class="parent-castle-page">
    <PageHeader :title="t('learning.castle.parentPageTitle')" />

    <van-pull-refresh
      v-model="refreshing"
      @refresh="onRefresh"
    >
      <ParentKnowledgeCastle
        :castle="castle"
        :state="state"
        @retry="load"
      />
    </van-pull-refresh>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ParentCastle' })

import { ref, onMounted, onActivated } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { fetchChildCastle, type CastleIndex } from '@/api/learning'
import { useBabyStore } from '@/stores/baby'
import PageHeader from '@/components/common/PageHeader.vue'
import ParentKnowledgeCastle from '@/components/learning/ParentKnowledgeCastle.vue'

const { t } = useI18n()
const router = useRouter()
const babyStore = useBabyStore()

const castle = ref<CastleIndex | null>(null)
const state = ref<'loading' | 'error' | 'content'>('loading')
const refreshing = ref(false)

async function load(): Promise<void> {
  const childId = babyStore.selectedChildId
  if (!childId) {
    router.replace('/baby/learning')
    return
  }
  if (!castle.value) state.value = 'loading'
  try {
    castle.value = await fetchChildCastle(childId)
    state.value = 'content'
  } catch {
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

// Skip first onActivated — Vue 3 fires both onMounted and onActivated on first mount
let hasActivated = false

onMounted(() => {
  if (!babyStore.selectedChildId) {
    router.replace('/baby/learning')
    return
  }
  load()
})

onActivated(async () => {
  if (!hasActivated) { hasActivated = true; return }
  // Reload when re-activated (e.g. switching back from another page)
  if (babyStore.selectedChildId) {
    castle.value = null
    await load()
  }
})
</script>

<style scoped>
.parent-castle-page {
  min-height: 100vh;
  background: var(--bg-primary);
}
</style>
