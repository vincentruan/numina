<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showSuccessToast } from 'vant'
import { useAgentStore } from '@/stores/agent'
import { useAuthStore } from '@/stores/auth'
import AIBrainIcon from '@/components/common/AIBrainIcon.vue'
import IIcon from '@/components/IIcon.vue'
import EmptyState from '@/components/common/EmptyState.vue'
import { getAgentIcon, isEmoji } from '@/utils/agent'
import type { Agent } from '@/types/agent'

const NUMINA_AGENT_NAME = 'numina'

const { t } = useI18n()
const router = useRouter()
const agentStore = useAgentStore()
const authStore = useAuthStore()
const isOwner = authStore.user?.role === 'owner'

onMounted(() => {
  agentStore.loadAgents()
})

async function handleToggle(agent: Agent, enabled: boolean) {
  await agentStore.toggleAgentEnabled(agent.id, enabled)
  showSuccessToast(enabled ? t('toast.agentToggleEnabled') : t('toast.agentToggleDisabled'))
}

async function handleDelete(agent: Agent) {
  await showConfirmDialog({
    title: t('agents.form.deleteConfirm'),
  })
  await agentStore.removeAgent(agent.id)
  showSuccessToast(t('agents.form.deleteSuccess'))
}
</script>

<template>
  <div class="page">
    <van-nav-bar :title="t('agents.title')" left-arrow @click-left="router.back()" />

    <!-- System Agents -->
    <van-cell-group inset :title="t('ai.systemAgents')">
      <template #title-extra>
        <span class="hint-text">{{ t('ai.systemAgentHint') }}</span>
      </template>
      <template v-if="agentStore.loading">
        <van-cell v-for="n in 2" :key="n" class="skeleton-cell">
          <template #icon>
            <div class="skeleton-icon skeleton-shimmer"></div>
          </template>
          <template #title>
            <div class="skeleton-title skeleton-shimmer"></div>
          </template>
          <template #label>
            <div class="skeleton-desc skeleton-shimmer" style="width: 85%"></div>
          </template>
          <template #value>
            <div class="skeleton-tag skeleton-shimmer"></div>
          </template>
        </van-cell>
      </template>
      <template v-else>
        <van-cell
          v-for="agent in agentStore.systemAgents"
          :key="agent.id"
          :title="agent.display_name"
          :label="agent.description || ''"
          :is-link="agent.can_edit"
          @click="
            agent.can_edit && router.push({ name: 'AgentEdit', params: { id: agent.id } })
          "
        >
          <template #icon>
            <span
              class="agent-icon-wrapper"
              :style="{
                backgroundColor: agent.agent_name === NUMINA_AGENT_NAME
                  ? 'transparent'
                  : `${agent.color || '#6366F1'}15`
              }"
            >
              <AIBrainIcon
                v-if="agent.agent_name === NUMINA_AGENT_NAME"
                :active="true"
                class="numina-brain-icon"
              />
              <span v-else-if="isEmoji(getAgentIcon(agent.icon))" class="agent-emoji">
                {{ getAgentIcon(agent.icon) || '🤖' }}
              </span>
              <IIcon
                v-else
                :icon="getAgentIcon(agent.icon)"
                size="20"
                :color="agent.color || 'var(--van-primary-color)'"
              />
            </span>
          </template>
          <template #value>
            <!-- System agents are always enabled, tied to core functionality -->
            <van-tag type="primary" size="medium" plain>
              {{ t('agents.alwaysEnabled') }}
            </van-tag>
          </template>
        </van-cell>
      </template>
    </van-cell-group>

    <!-- U15 (R12): Builtin Agents section removed.
         After migration b6745e8a2c14 there are no builtin agents in
         production — the six business agents (asset-health-advisor,
         finance-optimizer, etc.) were demoted to skills. The cell-group
         would otherwise render as an empty section with a header. -->

    <!-- Custom Agents -->
    <van-cell-group inset :title="t('ai.customAgents')">
      <template #title-extra>
        <span class="hint-text">{{ t('ai.customAgentHint') }}</span>
      </template>
      <template v-if="agentStore.loading">
        <van-cell v-for="n in 2" :key="n" class="skeleton-cell">
          <template #icon>
            <div class="skeleton-icon skeleton-shimmer"></div>
          </template>
          <template #title>
            <div class="skeleton-title skeleton-shimmer"></div>
          </template>
          <template #label>
            <div class="skeleton-desc skeleton-shimmer" style="width: 75%"></div>
          </template>
          <template #value>
            <div class="skeleton-switch skeleton-shimmer"></div>
          </template>
        </van-cell>
      </template>
      <template v-else>
        <van-cell
          v-for="agent in agentStore.customAgents"
          :key="agent.id"
          :title="agent.display_name"
          :label="agent.description || ''"
          is-link
          @click="router.push({ name: 'AgentEdit', params: { id: agent.id } })"
        >
          <template #title>
            <span>{{ agent.display_name }}</span>
            <van-tag v-if="agent.agent_type === 'custom' && !agent.is_published" plain type="warning" size="medium" class="publish-tag">
              {{ t('agents.form.draft') }}
            </van-tag>
          </template>
          <template #icon>
            <span
              class="agent-icon-wrapper"
              :style="{
                backgroundColor: agent.agent_name === NUMINA_AGENT_NAME
                  ? 'transparent'
                  : `${agent.color || '#6366F1'}15`
              }"
            >
              <AIBrainIcon
                v-if="agent.agent_name === NUMINA_AGENT_NAME"
                :active="true"
                class="numina-brain-icon"
              />
              <span v-else-if="isEmoji(getAgentIcon(agent.icon))" class="agent-emoji">
                {{ getAgentIcon(agent.icon) || '🤖' }}
              </span>
              <IIcon
                v-else
                :icon="getAgentIcon(agent.icon)"
                size="20"
                :color="agent.color || 'var(--van-primary-color)'"
              />
            </span>
          </template>
          <template #value>
            <div class="cell-actions" @click.stop>
              <van-switch
                :model-value="agent.is_enabled"
                size="20"
                :disabled="!isOwner"
                @update:model-value="(v: boolean) => handleToggle(agent, v)"
              />
              <van-icon
                v-if="agent.can_delete"
                name="delete-o"
                size="18"
                color="var(--van-danger-color)"
                @click="handleDelete(agent)"
              />
            </div>
          </template>
        </van-cell>
        <EmptyState
          v-if="!agentStore.customAgents.length"
          :description="t('agents.noCustomAgents')"
        >
          <van-button
            v-if="isOwner"
            type="primary"
            size="small"
            @click="router.push({ name: 'AgentCreate' })"
          >
            {{ t('ai.createAgent') }}
          </van-button>
        </EmptyState>
      </template>
    </van-cell-group>

    <div v-if="isOwner && agentStore.customAgents.length" class="bottom-bar">
      <van-button
        type="primary"
        block
        round
        @click="router.push({ name: 'AgentCreate' })"
      >
        {{ t('ai.createAgent') }}
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 160px;
}

.hint-text {
  font-size: 12px;
  color: var(--van-text-color-3);
  margin-left: 8px;
}

.agent-icon-wrapper {
  margin-right: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  flex-shrink: 0;
}

.agent-emoji {
  font-size: 20px;
}

.numina-brain-icon {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.numina-brain-icon :deep(.ai-button-wrapper) {
  transform: translateY(0) scale(0.7);
  margin: 0;
  width: 32px;
  height: 32px;
}

.numina-brain-icon :deep(.ai-button-3d) {
  width: 36px;
  height: 36px;
}

.cell-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.publish-tag {
  margin-left: 6px;
}

.bottom-bar {
  position: fixed;
  bottom: calc(50px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  z-index: 1;
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: var(--van-background);
}

:deep(.van-cell) {
  align-items: flex-start;
}

:deep(.van-cell__title) {
  flex: 1;
  min-width: 0;
}

:deep(.van-cell__value) {
  flex: none;
  display: flex;
  align-items: center;
  padding-top: 2px;
}

/* Skeleton Shimmer Layout */
.skeleton-cell {
  pointer-events: none;
}

.skeleton-icon {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  margin-right: 12px;
  flex-shrink: 0;
}

.skeleton-title {
  width: 100px;
  height: 16px;
  border-radius: 4px;
  margin-top: 3px;
}

.skeleton-desc {
  height: 12px;
  border-radius: 3px;
  margin-top: 8px;
}

.skeleton-tag {
  width: 60px;
  height: 20px;
  border-radius: 4px;
}

.skeleton-switch {
  width: 44px;
  height: 22px;
  border-radius: 11px;
}

.skeleton-shimmer {
  background: linear-gradient(
    90deg,
    rgba(0, 0, 0, 0.06) 25%,
    rgba(0, 0, 0, 0.12) 37%,
    rgba(0, 0, 0, 0.06) 63%
  );
  background-size: 400% 100%;
  animation: shimmer-swipe 1.4s ease-in-out infinite;
}

[data-theme='dark'] .skeleton-shimmer {
  background: linear-gradient(
    90deg,
    rgba(255, 255, 255, 0.05) 25%,
    rgba(255, 255, 255, 0.12) 37%,
    rgba(255, 255, 255, 0.05) 63%
  );
  background-size: 400% 100%;
}

@keyframes shimmer-swipe {
  0% {
    background-position: 100% 50%;
  }
  100% {
    background-position: 0% 50%;
  }
}
</style>