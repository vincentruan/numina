<script setup lang="ts">
/**
 * QuickActions — shortcut action buttons for the tutoring session.
 *
 * Provides context-aware buttons for the child to interact with
 * the Socratic tutor without typing long responses.
 */
import { useI18n } from 'vue-i18n'
import type { TutorPhase } from '@/composables/useSmartTutor'

interface Props {
  phase: TutorPhase
  isStreaming: boolean
}

defineProps<Props>()
const emit = defineEmits<{
  hint: []
  understand: []
  needMoreHelp: []
  showKnowledgeMap: []
}>()

const { t } = useI18n()
</script>

<template>
  <div class="quick-actions">
    <van-button
      size="small"
      plain
      type="primary"
      :disabled="isStreaming"
      @click="emit('hint')"
    >
      💡 {{ t('learning.smart_tutor.btn_hint') }}
    </van-button>
    <van-button
      size="small"
      plain
      type="success"
      :disabled="isStreaming"
      @click="emit('understand')"
    >
      ✅ {{ t('learning.smart_tutor.btn_understand') }}
    </van-button>
    <van-button
      v-if="phase === 'focused_guidance' || phase === 'prerequisite_retrace'"
      size="small"
      plain
      type="warning"
      :disabled="isStreaming"
      @click="emit('needMoreHelp')"
    >
      🆘 {{ t('learning.smart_tutor.btn_more_help') }}
    </van-button>
    <van-button
      size="small"
      plain
      icon="chart-trending-o"
      :disabled="isStreaming"
      @click="emit('showKnowledgeMap')"
    />
  </div>
</template>

<style scoped>
.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px;
}

.quick-actions .van-button {
  font-size: 12px;
}
</style>
