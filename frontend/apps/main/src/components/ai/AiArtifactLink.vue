<template>
  <div class="ai-artifact-link" :class="`kind-${artifact.kind ?? 'other'}`">
    <span class="artifact-icon" aria-hidden="true">{{ kindIcon }}</span>
    <span class="artifact-title">{{ artifact.title }}</span>
    <a
      v-if="safeUrl"
      class="artifact-action"
      :href="safeUrl"
      target="_blank"
      rel="noopener noreferrer"
    >{{ t('aiProcess.openArtifact') }}</a>
    <button
      v-else-if="artifact.path"
      class="artifact-action"
      type="button"
      :disabled="copying"
      @click="copyPath"
    >{{ t('aiProcess.copyPath') }}</button>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast, showSuccessToast, showFailToast } from 'vant'
import type { Artifact } from '@/types/agent-stream'

const props = defineProps<{
  artifact: Artifact
}>()

const { t } = useI18n()
const copying = ref(false)

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

// Reject javascript:/data:/vbscript: hrefs and any non-http(s)/mailto scheme
// before binding to :href. artifact.url is LLM/tool-emitted and reaches the
// DOM without the userMarkdownSanitizer pipeline, so we have to filter here.
const safeUrl = computed(() => {
  const raw = props.artifact.url
  if (!raw) return null
  const trimmed = raw.trim()
  const lower = trimmed.toLowerCase()
  if (
    lower.startsWith('javascript:') ||
    lower.startsWith('data:') ||
    lower.startsWith('vbscript:')
  ) {
    return null
  }
  if (
    lower.startsWith('http://') ||
    lower.startsWith('https://') ||
    lower.startsWith('mailto:') ||
    lower.startsWith('/') ||
    !/^[a-z][a-z0-9+.-]*:/.test(lower)
  ) {
    return trimmed
  }
  return null
})

// Strip newlines, NUL, and Unicode bidi-override / isolate chars before
// clipboard write so a poisoned artifact.path can't inject "\n; rm -rf /"
// or visually-disguised payloads when pasted into a terminal.
// ‪-‮: LRE/RLE/PDF/LRO/RLO bidi-override
// ⁦-⁩: LRI/RLI/FSI/PDI bidi-isolates
function scrubForClipboard(value: string): string {
  return value.replace(/[\r\n\0‪-‮⁦-⁩]/g, '')
}

async function copyPath() {
  if (!props.artifact.path || copying.value) return
  copying.value = true
  try {
    await navigator.clipboard.writeText(scrubForClipboard(props.artifact.path))
    showSuccessToast(t('aiProcess.pathCopied'))
  } catch {
    showFailToast(t('aiProcess.copyFailed'))
  } finally {
    copying.value = false
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

.artifact-action:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  .ai-artifact-link {
    padding: 6px 8px;
    font-size: 12px;
  }

  .artifact-action {
    padding: 8px 12px;
    font-size: 11px;
    min-height: 44px;
    min-width: 44px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }
}
</style>
