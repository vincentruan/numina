<script setup lang="ts">
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { useAgentStore } from '@/stores/agent'
import { useAuthStore } from '@/stores/auth'
import NuminaLogo from '@/components/common/NuminaLogo.vue'
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
  showToast(enabled ? t('toast.agentToggleEnabled') : t('toast.agentToggleDisabled'))
}

async function handleDelete(agent: Agent) {
  await showConfirmDialog({
    title: t('agents.form.deleteConfirm'),
  })
  await agentStore.removeAgent(agent.id)
  showToast(t('agents.form.deleteSuccess'))
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
          <span style="margin-right: 8px; font-size: 20px;">
            <NuminaLogo
              v-if="agent.agent_name === NUMINA_AGENT_NAME"
              class="numina-logo-small"
            />
            <span v-else>{{ agent.icon || '🤖' }}</span>
          </span>
        </template>
        <template #value>
          <van-switch
            :model-value="agent.is_enabled"
            size="20"
            :disabled="!isOwner"
            @update:model-value="(v: boolean) => handleToggle(agent, v)"
          />
        </template>
      </van-cell>
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
      <van-cell
        v-for="agent in agentStore.customAgents"
        :key="agent.id"
        :title="agent.display_name"
        :label="agent.description || ''"
        is-link
        @click="router.push({ name: 'AgentEdit', params: { id: agent.id } })"
      >
        <template #icon>
          <span style="margin-right: 8px; font-size: 20px;">{{ agent.icon || '🤖' }}</span>
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
      <van-empty
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
      </van-empty>
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
  padding-bottom: 80px;
}

.hint-text {
  font-size: 12px;
  color: var(--van-text-color-3);
  margin-left: 8px;
}

.cell-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.bottom-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: var(--van-background);
}
</style>