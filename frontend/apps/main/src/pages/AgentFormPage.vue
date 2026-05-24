<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { showToast } from 'vant'
import { useAgentStore } from '@/stores/agent'
import { getAgent } from '@/api/agent'
import { getSkillsGrouped } from '@/api/ai'
import type { AgentCreatePayload, AgentUpdatePayload } from '@/types/agent'
import type { SkillDefinition } from '@/api/ai'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()
const agentStore = useAgentStore()

const isEdit = computed(() => !!route.params.id)
const agentId = computed(() => route.params.id as string)

const form = ref<AgentCreatePayload>({
  agent_name: '',
  display_name: '',
  description: '',
  icon: '🤖',
  color: '#6366F1',
  soul_md: '',
  skills: [],
  model: undefined,
  subagent_enabled: false,
})

const isBuiltin = ref(false)
const availableSkills = ref<SkillDefinition[]>([])
const submitting = ref(false)

const ICON_OPTIONS = ['🤖', '🏥', '💰', '🎯', '📊', '🔍', '💡', '🛡️', '📈', '🧮',
  '🏠', '💳', '🎓', '🌟', '⚡', '🔧', '📋', '🧠', '✨', '🎨']

const COLOR_OPTIONS = [
  '#6366F1', '#10B981', '#F59E0B', '#EF4444',
  '#3B82F6', '#8B5CF6', '#EC4899', '#14B8A6',
]

onMounted(async () => {
  const skillData = await getSkillsGrouped()
  availableSkills.value = [...skillData.builtin.filter((s: SkillDefinition) => s.is_enabled), ...skillData.custom.filter((s: SkillDefinition) => s.is_enabled)]

  if (isEdit.value) {
    const agent = await getAgent(agentId.value)
    isBuiltin.value = agent.is_builtin
    form.value = {
      agent_name: agent.agent_name,
      display_name: agent.display_name,
      description: agent.description || '',
      icon: agent.icon || '🤖',
      color: agent.color || '#6366F1',
      soul_md: agent.soul_md,
      skills: agent.skills || [],
      model: agent.model || undefined,
      subagent_enabled: agent.subagent_enabled,
    }
  }
})

async function handleSubmit() {
  submitting.value = true
  try {
    if (isEdit.value) {
      const payload: AgentUpdatePayload = {}
      if (isBuiltin.value) {
        payload.icon = form.value.icon
        payload.color = form.value.color
      } else {
        payload.display_name = form.value.display_name
        payload.description = form.value.description
        payload.icon = form.value.icon
        payload.color = form.value.color
        payload.soul_md = form.value.soul_md
        payload.skills = form.value.skills
        payload.model = form.value.model
        payload.subagent_enabled = form.value.subagent_enabled
      }
      await agentStore.editAgent(agentId.value, payload)
      showToast(t('agents.form.updateSuccess'))
    } else {
      await agentStore.addAgent(form.value)
      showToast(t('agents.form.createSuccess'))
    }
    router.back()
  } finally {
    submitting.value = false
  }
}

function toggleSkill(skillId: string) {
  const skills = form.value.skills || []
  const idx = skills.indexOf(skillId)
  if (idx >= 0) {
    skills.splice(idx, 1)
  } else {
    skills.push(skillId)
  }
  form.value.skills = [...skills]
}
</script>

<template>
  <div class="page">
    <van-nav-bar
      :title="isEdit ? t('agents.editAgent') : t('agents.createAgent')"
      left-arrow
      @click-left="router.back()"
    />

    <van-cell-group inset>
      <van-field
        v-if="!isEdit"
        v-model="form.agent_name"
        :label="t('agents.form.agentName')"
        :placeholder="t('agents.form.agentNameHint')"
      />
      <van-field
        v-model="form.display_name"
        :label="t('agents.form.displayName')"
        required
      />
      <van-field
        v-model="form.description"
        :label="t('agents.form.description')"
        type="textarea"
        rows="2"
        autosize
      />
    </van-cell-group>

    <van-cell-group inset :title="t('agents.form.icon')">
      <div class="icon-grid">
        <div
          v-for="icon in ICON_OPTIONS"
          :key="icon"
          class="icon-option"
          :class="{ 'icon-option--active': form.icon === icon }"
          @click="form.icon = icon"
        >
          {{ icon }}
        </div>
      </div>
    </van-cell-group>

    <van-cell-group inset :title="t('agents.form.color')">
      <div class="color-grid">
        <div
          v-for="color in COLOR_OPTIONS"
          :key="color"
          class="color-option"
          :class="{ 'color-option--active': form.color === color }"
          :style="{ background: color }"
          @click="form.color = color"
        />
      </div>
    </van-cell-group>

    <van-cell-group v-if="!isBuiltin" inset :title="t('agents.form.soulMd')">
      <van-field
        v-model="form.soul_md"
        type="textarea"
        rows="8"
        autosize
        :placeholder="t('agents.form.soulMdHint')"
      />
    </van-cell-group>

    <van-cell-group v-if="!isBuiltin" inset :title="t('agents.form.skills')">
      <van-cell
        v-for="skill in availableSkills"
        :key="skill.id"
        :title="skill.name || skill.id"
        :label="skill.description || ''"
      >
        <template #right-icon>
          <van-checkbox
            :model-value="(form.skills || []).includes(skill.id)"
            @update:model-value="toggleSkill(skill.id)"
          />
        </template>
      </van-cell>
    </van-cell-group>

    <van-cell-group v-if="!isBuiltin" inset>
      <van-field
        v-model="form.model"
        :label="t('agents.form.model')"
        :placeholder="t('agents.form.modelInherit')"
      />
      <van-cell :title="t('agents.form.subagentEnabled')">
        <template #value>
          <van-switch v-model="form.subagent_enabled" size="20" />
        </template>
      </van-cell>
    </van-cell-group>

    <div class="bottom-bar">
      <van-button
        type="primary"
        block
        round
        :loading="submitting"
        @click="handleSubmit"
      >
        {{ isEdit ? t('agents.form.updateBtn') : t('agents.form.createBtn') }}
      </van-button>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding-bottom: 80px;
}

.icon-grid {
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  gap: 4px;
  padding: 12px 16px;
}

.icon-option {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  height: 40px;
  border-radius: 8px;
  cursor: pointer;
  border: 2px solid transparent;
}

.icon-option--active {
  border-color: var(--van-primary-color);
  background: var(--van-primary-color-light);
}

.color-grid {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
}

.color-option {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  cursor: pointer;
  border: 3px solid transparent;
}

.color-option--active {
  border-color: var(--van-text-color);
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