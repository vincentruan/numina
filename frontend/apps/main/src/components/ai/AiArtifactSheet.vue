<template>
  <van-popup
    v-model:show="visible"
    round
    position="bottom"
    :style="{ paddingBottom: 'env(safe-area-inset-bottom)' }"
  >
    <div class="artifact-sheet">
      <div class="artifact-sheet__header">
        <span class="artifact-sheet__title">{{ t('aiArtifact.sheetTitle', { count: artifacts.length }) }}</span>
        <van-icon name="cross" size="18" class="artifact-sheet__close" @click="handleClose" />
      </div>

      <div v-if="artifacts.length === 0" class="artifact-sheet__empty">
        {{ t('aiArtifact.emptyMessage') }}
      </div>

      <div v-else class="artifact-sheet__list">
        <div
          v-for="artifact in artifacts"
          :key="artifact.url || artifact.path || artifact.title"
          class="artifact-item"
          @click="handleArtifactTap(artifact)"
        >
          <AiArtifactLink :artifact="artifact" />
        </div>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AiArtifactLink from './AiArtifactLink.vue'
import type { Artifact } from '@/types/agent-stream'

const props = defineProps<{
  visible: boolean
  artifacts: Artifact[]
}>()

const emit = defineEmits<{
  close: []
  'artifact-tap': [artifact: Artifact]
}>()

const { t } = useI18n()

const visible = computed({
  get: () => props.visible,
  set: (v) => {
    if (!v) {
      emit('close')
    }
  },
})

function handleClose() {
  emit('close')
}

function handleArtifactTap(artifact: Artifact) {
  emit('artifact-tap', artifact)
}
</script>

<style scoped>
.artifact-sheet {
  padding: 20px 16px 8px;
}

.artifact-sheet__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.artifact-sheet__title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

.artifact-sheet__close {
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
}

.artifact-sheet__empty {
  padding: 32px 16px;
  text-align: center;
  font-size: 14px;
  color: var(--text-secondary);
}

.artifact-sheet__list {
  max-height: 50vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 8px;
}

.artifact-item {
  cursor: pointer;
}
</style>