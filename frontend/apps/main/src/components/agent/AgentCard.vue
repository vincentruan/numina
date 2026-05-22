<script setup lang="ts">
import type { Agent } from '@/types/agent'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  agent: Agent
  showActions?: boolean
}>()

const emit = defineEmits<{
  consult: [agent: Agent]
  edit: [agent: Agent]
}>()
</script>

<template>
  <div
    class="agent-card"
    :style="{ '--agent-color': agent.color || '#6366F1' }"
    @click="emit('consult', agent)"
  >
    <div class="agent-card__icon">{{ agent.icon || '🤖' }}</div>
    <div class="agent-card__body">
      <div class="agent-card__name">{{ agent.display_name }}</div>
      <div class="agent-card__desc">{{ agent.description || '' }}</div>
    </div>
    <div v-if="showActions" class="agent-card__actions" @click.stop>
      <van-button
        size="small"
        type="primary"
        plain
        @click="emit('consult', agent)"
      >
        {{ agent.is_builtin ? t('agents.consult') : t('agents.chat') }}
      </van-button>
      <van-button
        v-if="agent.can_edit"
        size="small"
        plain
        @click="emit('edit', agent)"
      >
        {{ t('agents.edit') }}
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.agent-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px;
  border-radius: 12px;
  background: var(--van-background-2);
  border: 1px solid var(--van-border-color);
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}

.agent-card:active {
  transform: scale(0.97);
}

.agent-card__icon {
  font-size: 32px;
  line-height: 1;
}

.agent-card__name {
  font-size: 15px;
  font-weight: 600;
  color: var(--van-text-color);
}

.agent-card__desc {
  font-size: 12px;
  color: var(--van-text-color-2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.agent-card__actions {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}
</style>
