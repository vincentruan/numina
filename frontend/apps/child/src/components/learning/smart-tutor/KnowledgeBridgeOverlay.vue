<script setup lang="ts">
/**
 * KnowledgeBridgeOverlay — visualizes the prerequisite knowledge chain.
 *
 * Shows the current question's position in the knowledge graph and
 * highlights broken prerequisite links (knowledge gaps) that need
 * to be addressed before the child can master the current topic.
 */
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { KnowledgeBridge } from '@/composables/useSmartTutor'

interface Props {
  bridge: KnowledgeBridge | null
  visible: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{ close: [] }>()

const { t } = useI18n()

const nodes = computed(() => props.bridge?.prerequisite_chain ?? [])

const masteryColor = (level: string): string => {
  const colors: Record<string, string> = {
    mastered: '#4AD97A',
    learning: '#4A90D9',
    assessing: '#D9A34A',
    available: '#9B59B6',
    locked: '#ccc',
    review: '#E74C3C',
  }
  return colors[level] ?? '#ccc'
}

const masteryLabel = (level: string): string => {
  const keys: Record<string, string> = {
    mastered: 'learning.smart_tutor.mastery_mastered',
    learning: 'learning.smart_tutor.mastery_learning',
    assessing: 'learning.smart_tutor.mastery_assessing',
    available: 'learning.smart_tutor.mastery_available',
    locked: 'learning.smart_tutor.mastery_locked',
    review: 'learning.smart_tutor.mastery_review',
  }
  return t(keys[level] ?? '') || level
}
</script>

<template>
  <van-popup
    :show="visible"
    position="bottom"
    round
    :style="{ maxHeight: '60vh' }"
    @close="emit('close')"
  >
    <div class="knowledge-bridge">
      <div class="knowledge-bridge__header">
        <h3>{{ t('learning.smart_tutor.knowledge_bridge_title') }}</h3>
        <van-icon name="cross" @click="emit('close')" />
      </div>

      <div v-if="bridge?.broken_link" class="knowledge-bridge__alert">
        <span>⚠️</span>
        {{ t('learning.smart_tutor.broken_link_hint', {
          name: bridge.broken_link.name || '前置知识',
        }) }}
      </div>

      <div class="knowledge-bridge__chain">
        <div
          v-for="node in nodes"
          :key="node.topic_id"
          class="knowledge-bridge__node"
          :class="{
            'knowledge-bridge__node--current': node.is_current,
            'knowledge-bridge__node--broken':
              bridge?.broken_link?.topic_id === node.topic_id,
          }"
        >
          <div
            class="knowledge-bridge__dot"
            :style="{ backgroundColor: masteryColor(node.mastery_level) }"
          />
          <div class="knowledge-bridge__info">
            <span class="knowledge-bridge__name">
              {{ node.name || `Topic ${node.topic_id}` }}
            </span>
            <span class="knowledge-bridge__mastery">
              {{ masteryLabel(node.mastery_level) }}
            </span>
          </div>
          <span v-if="node.is_current" class="knowledge-bridge__badge">
            {{ t('learning.smart_tutor.current_topic') }}
          </span>
        </div>
      </div>

      <div v-if="nodes.length === 0" class="knowledge-bridge__empty">
        {{ t('learning.smart_tutor.no_bridge_data') }}
      </div>
    </div>
  </van-popup>
</template>

<style scoped>
.knowledge-bridge {
  padding: 16px;
}

.knowledge-bridge__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.knowledge-bridge__header h3 {
  margin: 0;
  font-size: 16px;
}

.knowledge-bridge__alert {
  background: #fff3cd;
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  gap: 6px;
}

[data-theme='dark'] .knowledge-bridge__alert {
  background: rgba(255, 193, 7, 0.15);
}

.knowledge-bridge__chain {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.knowledge-bridge__node {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--color-canvas, #f5f5f5);
  transition: background 0.2s;
}

.knowledge-bridge__node--current {
  border: 2px solid var(--color-primary, #0a0a0a);
  background: rgba(74, 144, 217, 0.08);
}

.knowledge-bridge__node--broken {
  border: 2px solid #E74C3C;
  background: rgba(231, 76, 60, 0.06);
}

.knowledge-bridge__dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.knowledge-bridge__info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.knowledge-bridge__name {
  font-size: 14px;
  font-weight: 500;
}

.knowledge-bridge__mastery {
  font-size: 11px;
  color: var(--color-body, #999);
}

.knowledge-bridge__badge {
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 10px;
  background: var(--color-primary, #0a0a0a);
  color: var(--color-canvas, #fff);
}

.knowledge-bridge__empty {
  text-align: center;
  padding: 24px;
  color: var(--color-body, #999);
  font-size: 14px;
}
</style>
