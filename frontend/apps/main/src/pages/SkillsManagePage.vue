<template>
  <div class="skills-manage-page">
    <PageHeader :title="t('skills.title')" />

    <van-cell-group inset :title="t('skills.builtinSkills')" class="section">
      <van-cell
        v-for="skill in skills"
        :key="skill.capability"
        :title="t(`skills.capability.${skill.capability}`)"
        :label="skill.custom_prompt ? t('skills.customPromptActive') : t('skills.defaultPrompt')"
        center
        is-link
        @click="onEditSkill(skill)"
      >
        <template #value>
          <van-switch
            :model-value="skill.is_enabled"
            size="20px"
            :disabled="!isOwner"
            @change="(v: boolean) => onToggle(skill, v)"
            @click.stop
          />
        </template>
      </van-cell>
    </van-cell-group>

    <!-- Prompt editor popup -->
    <van-popup
      v-model:show="showEditor"
      position="bottom"
      round
      :style="{ height: '80%' }"
    >
      <div class="editor-header">
        <span class="editor-title">{{ editingSkill ? t(`skills.capability.${editingSkill.capability}`) : '' }}</span>
        <van-button size="small" type="primary" :loading="saving" @click="onSavePrompt">
          {{ t('common.save') }}
        </van-button>
      </div>

      <div class="editor-body">
        <p class="editor-hint">{{ t('skills.promptHint') }}</p>
        <van-field
          v-model="promptDraft"
          type="textarea"
          :placeholder="activePlaceholder"
          :autosize="{ minHeight: 200 }"
          class="prompt-field"
        />
        <van-button
          v-if="editingSkill?.custom_prompt"
          size="small"
          plain
          type="danger"
          class="reset-btn"
          @click="onResetPrompt"
        >
          {{ t('skills.resetToDefault') }}
        </van-button>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { getSkills, updateSkill, resetSkillPrompt, type SkillConfig } from '@/api/ai'

const { t } = useI18n()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

const skills = ref<SkillConfig[]>([])
const showEditor = ref(false)
const editingSkill = ref<SkillConfig | null>(null)
const promptDraft = ref('')
const saving = ref(false)

const activePlaceholder = computed(() => {
  if (!editingSkill.value) return ''
  return editingSkill.value.default_prompt ?? t('skills.enterPrompt')
})

async function load() {
  const res = await getSkills()
  skills.value = res.data
}

onMounted(load)

function onEditSkill(skill: SkillConfig) {
  if (!isOwner.value) return
  editingSkill.value = skill
  promptDraft.value = skill.custom_prompt ?? ''
  showEditor.value = true
}

async function onToggle(skill: SkillConfig, enabled: boolean) {
  await updateSkill(skill.capability, { is_enabled: enabled })
  skill.is_enabled = enabled
}

async function onSavePrompt() {
  if (!editingSkill.value) return
  saving.value = true
  try {
    const res = await updateSkill(editingSkill.value.capability, {
      custom_prompt: promptDraft.value || '',
    })
    // Update local state
    const idx = skills.value.findIndex((s) => s.capability === editingSkill.value!.capability)
    if (idx !== -1) skills.value[idx] = res.data
    showToast(t('toast.saved'))
    showEditor.value = false
  } finally {
    saving.value = false
  }
}

async function onResetPrompt() {
  if (!editingSkill.value) return
  saving.value = true
  try {
    const res = await resetSkillPrompt(editingSkill.value.capability)
    const idx = skills.value.findIndex((s) => s.capability === editingSkill.value!.capability)
    if (idx !== -1) skills.value[idx] = res.data
    promptDraft.value = ''
    showToast(t('skills.promptReset'))
    showEditor.value = false
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.skills-manage-page {
  min-height: 100vh;
  background: var(--van-background);
}
.section {
  margin-top: 12px;
}
.editor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid var(--van-border-color);
}
.editor-title {
  font-size: 16px;
  font-weight: 600;
}
.editor-body {
  padding: 12px 16px;
  overflow-y: auto;
  height: calc(100% - 60px);
}
.editor-hint {
  font-size: 12px;
  color: var(--van-text-color-3);
  margin: 0 0 8px;
}
.prompt-field :deep(.van-field__control) {
  font-family: monospace;
  font-size: 13px;
}
.reset-btn {
  margin-top: 12px;
}
</style>
