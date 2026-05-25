<template>
  <div class="ai-artifact-link" :class="`kind-${artifact.kind ?? 'other'}`">
    <span class="artifact-icon" aria-hidden="true">{{ kindIcon }}</span>
    <span class="artifact-title">{{ artifact.title }}</span>
    <a
      v-if="artifact.url"
      class="artifact-action"
      :href="artifact.url"
      target="_blank"
      rel="noopener noreferrer"
    >{{ t('aiProcess.openArtifact') }}</a>
    <button
      v-else-if="artifact.path"
      class="artifact-action"
      type="button"
      @click="copyPath"
    >{{ t('aiProcess.copyPath') }}</button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import type { Artifact } from '@/types/agent-stream'

const props = defineProps<{
  artifact: Artifact
}>()

const { t } = useI18n()

const kindIcon = computed(() => {
  switch (props.artifact.kind) {
    case 'report':
      return '📊'
    case 'file':
      return '📄'
    case 'image':
      return '🖼️'
    case 'link':
      return '🔗'
    default:
      return '📎'
  }
})

async function copyPath() {
  if (!props.artifact.path) return
  try {
    await navigator.clipboard.writeText(props.artifact.path)
    showToast(t('aiProcess.pathCopied'))
  } catch {
    showToast(t('aiProcess.copyFailed'))
  }
}
</script>

<style scoped>
.ai-artifact-link {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 4px;
  background: var(--bg-secondary);
  border: 1px solid var(--color-card-border);
  font-size: 13px;
  color: var(--text-primary);
}

.artifact-icon {
  font-size: 14px;
  flex-shrink: 0;
}

.artifact-title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-action {
  flex-shrink: 0;
  padding: 4px 10px;
  font-size: 12px;
  color: var(--color-action-blue);
  background: var(--card-bg);
  border: 1px solid var(--color-card-border);
  border-radius: 4px;
  text-decoration: none;
  cursor: pointer;
}

.artifact-action:hover {
  opacity: 0.85;
}

@media (max-width: 768px) {
  .ai-artifact-link {
    padding: 6px 8px;
    font-size: 12px;
  }

  .artifact-action {
    padding: 4px 8px;
    font-size: 11px;
  }
}
</style>
