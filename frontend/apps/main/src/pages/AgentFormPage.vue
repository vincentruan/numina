<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { showSuccessToast, showFailToast } from 'vant'
import { useAgentStore } from '@/stores/agent'
import { getAgent } from '@/api/agent'
import { getSkillsGrouped } from '@/api/ai'
import type { AgentCreatePayload, AgentUpdatePayload } from '@/types/agent'
import type { SkillDefinition } from '@/api/ai'
import EmptyState from '@/components/common/EmptyState.vue'
import AIBrainIcon from '@/components/common/AIBrainIcon.vue'
import IIcon from '@/components/IIcon.vue'
import { ICON_OPTIONS, EMOJI_TO_ICONIFY } from '@/utils/agent'

const NUMINA_AGENT_NAME = 'numina'

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
  icon: 'lucide:bot',
  color: '#6366F1',
  soul_md: '',
  skills: [],
  model: undefined,
  subagent_enabled: false,
  is_published: false,
})

// U13: agent_type drives the read-only mode for system agents (numina,
// ai-assistant).
const agentType = ref<'system' | 'custom' | null>(null)
const isSystemAgent = computed(() => agentType.value === 'system')

const availableSkills = ref<SkillDefinition[]>([])
const skillsLoading = ref(true)
const submitting = ref(false)

// ICON_OPTIONS is imported from @/utils/agent.ts

const COLOR_OPTIONS = [
  '#6366F1', '#10B981', '#F59E0B', '#EF4444',
  '#3B82F6', '#8B5CF6', '#EC4899', '#14B8A6',
]

onMounted(async () => {
  skillsLoading.value = true
  try {
    const skillData = await getSkillsGrouped()
    availableSkills.value = [
      ...skillData.builtin.filter((s: SkillDefinition) => s.is_enabled),
      ...skillData.custom.filter((s: SkillDefinition) => s.is_enabled),
    ]
    if (!isEdit.value) {
      form.value.skills = availableSkills.value.map(s => s.id)
    }
  } finally {
    skillsLoading.value = false
  }

  if (isEdit.value) {
    const agent = await getAgent(agentId.value)
    agentType.value = agent.agent_type
    
    // Map emoji icon to Iconify if available
    let loadedIcon = agent.icon || 'lucide:bot'
    if (loadedIcon in EMOJI_TO_ICONIFY) {
      loadedIcon = EMOJI_TO_ICONIFY[loadedIcon]
    }

    form.value = {
      agent_name: agent.agent_name,
      display_name: agent.display_name,
      description: agent.description || '',
      icon: loadedIcon,
      color: agent.color || '#6366F1',
      soul_md: agent.soul_md,
      skills: agent.skills || [],
      model: agent.model || undefined,
      subagent_enabled: agent.subagent_enabled,
      is_published: agent.is_published,
    }
  }
})

async function handleSubmit() {
  // U13 defensive guard — system agents are not mutable; the save button is
  // also removed from the DOM via v-if so this path is unreachable from
  // the UI, but keep the guard against programmatic invocation.
  if (isSystemAgent.value) return
  submitting.value = true
  try {
    if (isEdit.value) {
      const payload: AgentUpdatePayload = {}
      payload.display_name = form.value.display_name
      payload.description = form.value.description
      payload.icon = form.value.icon
      payload.color = form.value.color
      payload.soul_md = form.value.soul_md
      payload.skills = form.value.skills
      payload.model = form.value.model
      payload.subagent_enabled = form.value.subagent_enabled
      payload.is_published = form.value.is_published
      await agentStore.editAgent(agentId.value, payload)
      showSuccessToast(t('agents.form.updateSuccess'))
    } else {
      await agentStore.addAgent(form.value)
      showSuccessToast(t('agents.form.createSuccess'))
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

const skillIcons: Record<string, string> = {}

function getSkillIcon(skill: SkillDefinition): string {
  if (skill.skill_type === 'builtin') {
    return skillIcons[skill.id] || '✨'
  }
  return skill.icon || '✨'
}
</script>

<template>
  <div class="page">
    <van-nav-bar
      :title="isEdit ? t('agents.editAgent') : t('agents.createAgent')"
      left-arrow
      @click-left="router.back()"
    />

    <!-- U13: read-only banner — system agents (数鸣, AI问答) cannot be edited.
         Owners can still navigate here to inspect the agent's configuration.
         Text already has 🔒 emoji, so no left-icon needed. Scrollable for long text. -->
    <van-notice-bar
      v-if="isSystemAgent"
      :scrollable="true"
      :text="t('agents.form.systemAgentBanner')"
    />

    <van-cell-group inset>
      <van-field
        v-if="!isEdit"
        v-model="form.agent_name"
        :label="t('agents.form.agentName')"
        :placeholder="t('agents.form.agentNameHint')"
        :disabled="isSystemAgent"
      />
      <van-field
        v-model="form.display_name"
        :label="t('agents.form.displayName')"
        required
        :disabled="isSystemAgent"
      />
      <van-field
        v-model="form.description"
        :label="t('agents.form.description')"
        type="textarea"
        rows="2"
        autosize
        :disabled="isSystemAgent"
      />
    </van-cell-group>

    <van-cell-group inset :title="t('agents.form.icon')">
      <div class="icon-grid" :class="{ 'icon-grid--readonly': isSystemAgent }">
        <div
          v-for="icon in ICON_OPTIONS"
          :key="icon"
          class="icon-option"
          :class="{ 'icon-option--active': form.icon === icon }"
          @click="!isSystemAgent && (form.icon = icon)"
        >
          <AIBrainIcon
            v-if="isSystemAgent && form.agent_name === NUMINA_AGENT_NAME && form.icon === icon"
            :active="true"
            class="numina-brain-icon"
          />
          <IIcon
            v-else
            :icon="icon"
            size="24"
            :color="form.icon === icon ? 'var(--van-primary-color)' : 'var(--van-text-color-2)'"
          />
        </div>
      </div>
    </van-cell-group>

    <van-cell-group inset :title="t('agents.form.color')">
      <div class="color-grid" :class="{ 'color-grid--readonly': isSystemAgent }">
        <div
          v-for="color in COLOR_OPTIONS"
          :key="color"
          class="color-option"
          :class="{ 'color-option--active': form.color === color }"
          :style="{ background: color }"
          @click="!isSystemAgent && (form.color = color)"
        />
      </div>
    </van-cell-group>

    <van-cell-group v-if="!isSystemAgent" inset :title="t('agents.form.soulMd')">
      <van-field
        v-model="form.soul_md"
        type="textarea"
        rows="8"
        autosize
        :placeholder="t('agents.form.soulMdHint')"
      />
    </van-cell-group>

    <!-- Skills section: for system agents (numina with sentinel ['*']),
         render the family's currently-enabled skills as locked rows so the
         owner sees what numina actually has access to. For custom
         agents, render normal toggleable rows. -->
    <van-cell-group v-if="isSystemAgent || !isSystemAgent" inset :title="t('agents.form.skills')">
      <van-skeleton v-if="skillsLoading" :row="3" />
      <EmptyState
        v-else-if="!availableSkills.length"
        :description="t('agents.form.noEnabledSkills')"
      />
      <template v-else>
        <van-cell
          v-for="skill in availableSkills"
          :key="skill.id"
          :title="skill.skill_type === 'builtin' ? t(`skills.capability.${skill.id}.name`) : (skill.name || skill.id)"
          :label="skill.skill_type === 'builtin' ? t(`skills.capability.${skill.id}.description`) : (skill.description || '')"
          center
        >
          <template #icon>
            <span class="skill-icon">{{ getSkillIcon(skill) }}</span>
          </template>
          <template #right-icon>
            <van-icon v-if="isSystemAgent" name="lock" />
            <van-checkbox
              v-else
              :model-value="(form.skills || []).includes(skill.id)"
              @update:model-value="toggleSkill(skill.id)"
            />
          </template>
        </van-cell>
      </template>
    </van-cell-group>

    <van-cell-group v-if="!isSystemAgent" inset>
      <van-cell center :title="t('agents.form.isPublished')" :label="t('agents.form.publishedHint')">
        <template #right-icon>
          <van-switch v-model="form.is_published" size="22px" />
        </template>
      </van-cell>
    </van-cell-group>

    <!-- Save button: removed from DOM (not just disabled) for system agents. -->
    <div v-if="!isSystemAgent" class="bottom-bar">
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
  padding-bottom: calc(120px + env(safe-area-inset-bottom));
}

.icon-grid {
  display: grid;
  grid-template-columns: repeat(10, 1fr);
  gap: 4px;
  padding: 12px 16px;
}

.icon-grid--readonly,
.color-grid--readonly {
  opacity: 0.6;
  pointer-events: none;
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

.numina-brain-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
}

.numina-brain-icon :deep(.ai-button-wrapper) {
  transform: translateY(0) scale(0.65);
  margin: 0;
  width: 32px;
  height: 32px;
}

.numina-brain-icon :deep(.ai-button-3d) {
  width: 36px;
  height: 36px;
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
  bottom: calc(50px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  z-index: 1;
  padding: 12px 16px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: var(--van-background);
}

.skill-icon {
  margin-right: 8px;
  font-size: 20px;
}
</style>
