<template>
  <div class="preset-paths-page">
    <PageHeader :title="t('learning.presetPaths')" />
    <van-skeleton v-if="loading" :rows="5" :round="true" />
    <template v-else>
      <EmptyState v-if="presetPaths.length === 0" :description="t('learning.presetPathsEmpty')" />
      <van-cell-group v-else inset>
        <van-cell
          v-for="pp in presetPaths"
          :key="pp.id"
          :title="presetPathDisplayName(pp)"
          :label="pp.subject"
          is-link
        >
          <template #value>
            <van-tag plain type="primary">{{ t('learning.topicCount', { count: pp.topic_count }) }}</van-tag>
          </template>
        </van-cell>
      </van-cell-group>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'PresetPaths' })

import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getPresetPaths, type PresetPathResponse } from '@/api/learning'
import PageHeader from '@/components/common/PageHeader.vue'
import EmptyState from '@/components/common/EmptyState.vue'

const { t, locale } = useI18n()
const loading = ref(true)
const presetPaths = ref<PresetPathResponse[]>([])

function presetPathDisplayName(pp: PresetPathResponse): string {
  return locale.value.startsWith('zh') && pp.name_zh ? pp.name_zh : pp.name
}

onMounted(async () => {
  try {
    presetPaths.value = await getPresetPaths()
  } catch {
    presetPaths.value = []
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.preset-paths-page {
  min-height: 100vh;
  padding-bottom: 20px;
}
</style>
