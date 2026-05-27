<script setup lang="ts">
import type { Agent } from '@/types/agent'
import AgentCard from './AgentCard.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  systemAgents: Agent[]
  customAgents: Agent[]
  showCreate?: boolean
}>()

const emit = defineEmits<{
  consult: [agent: Agent]
  edit: [agent: Agent]
  create: []
}>()
</script>

<template>
  <!-- System agents zone: AI问答, 数鸣 (always present when at least one is enabled). -->
  <div v-if="systemAgents.length" class="agent-section">
    <div class="agent-section__title">{{ t('agents.systemAgents') }}</div>
    <div class="agent-grid">
      <AgentCard
        v-for="agent in systemAgents"
        :key="agent.id"
        :agent="agent"
        :show-actions="true"
        @consult="emit('consult', $event)"
        @edit="emit('edit', $event)"
      />
    </div>
  </div>

  <!-- Slot for content between system and custom zones (e.g. apps section) -->
  <slot name="between" />

  <!-- Custom agents zone — title renders unconditionally so the empty-state
       hint is visible even when no custom agents exist (per R1 + AE11). -->
  <div class="agent-section">
    <div class="agent-section__title">{{ t('agents.customAgents') }}</div>
    <div class="agent-grid">
      <AgentCard
        v-for="agent in customAgents"
        :key="agent.id"
        :agent="agent"
        :show-actions="true"
        @consult="emit('consult', $event)"
        @edit="emit('edit', $event)"
      />
      <div v-if="showCreate" class="agent-card agent-card--create" @click="emit('create')">
        <div class="agent-card__icon">＋</div>
        <div class="agent-card__body">
          <div class="agent-card__name">{{ t('agents.createAgent') }}</div>
        </div>
      </div>
    </div>
    <van-empty
      v-if="!customAgents.length && !showCreate"
      :description="t('agents.noCustomAgents')"
    />
  </div>
</template>

<style scoped>
.agent-section {
  margin-bottom: 16px;
}

.agent-section__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--van-text-color-2);
  padding: 0 4px 8px;
}

.agent-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.agent-card--create {
  border: 2px dashed var(--van-border-color);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100px;
  cursor: pointer;
}

.agent-card--create .agent-card__icon {
  font-size: 28px;
  color: var(--van-text-color-3);
}

.agent-card--create .agent-card__name {
  color: var(--van-text-color-3);
  font-size: 13px;
}
</style>
