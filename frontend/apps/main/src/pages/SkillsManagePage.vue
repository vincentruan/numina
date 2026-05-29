<template>
  <div class="skills-manage-page">
    <PageHeader :title="t('skills.title')" />

    <!-- U14 (R9): the "固定技能" section is removed entirely. The chat and
         time_machine entries are no longer skills — they're routing
         capabilities (see _ROUTING_CAPABILITIES in ai_capabilities.py) and
         shouldn't appear in skill management. The api response's `fixed`
         array is also empty after the U1 backend change. -->

    <!-- Builtin skills (toggle) -->
    <van-cell-group inset :title="t('skills.builtinSkills')" class="section">
      <van-cell
        v-for="skill in allBuiltinSkills"
        :key="skill.id"
        :title="t(`skills.capability.${skill.id}.name`)"
        :label="t(`skills.capability.${skill.id}.description`)"
        center
      >
        <template #value>
          <van-switch
            :model-value="skill.is_enabled"
            size="20px"
            :disabled="!isOwner"
            @change="(v: boolean) => onToggle(skill.id, v)"
            @click.stop
          />
        </template>
      </van-cell>
    </van-cell-group>

    <!-- Custom skills (toggle + edit + delete) -->
    <van-cell-group inset :title="t('skills.customSkills')" class="section">
      <van-cell
        v-for="skill in groupedSkills?.custom ?? []"
        :key="skill.id"
        :title="`${skill.icon || '✨'} ${skill.name || skill.id}`"
        :label="skill.description"
        center
      >
        <template #value>
          <div class="custom-skill-actions">
            <van-switch
              :model-value="skill.is_enabled"
              size="20px"
              :disabled="!isOwner"
              @change="(v: boolean) => onToggle(skill.id, v)"
              @click.stop
            />
            <van-icon v-if="isOwner" name="edit" size="18" class="action-icon" @click.stop="onEditSkill(skill)" />
            <van-icon v-if="isOwner" name="delete-o" size="18" class="action-icon delete-icon" @click.stop="onDeleteSkill(skill)" />
          </div>
        </template>
      </van-cell>
      <van-cell v-if="!groupedSkills?.custom?.length" :title="t('common.noData')" />
    </van-cell-group>

    <!-- Add skill button -->
    <div v-if="isOwner" class="add-skill-section">
      <van-button block type="primary" icon="plus" @click="onCreateSkill">
        {{ t('skills.form.createBtn') }}
      </van-button>
    </div>

    <!-- Create/Edit form popup -->
    <van-popup
      v-model:show="showForm"
      position="bottom"
      round
      :style="{ height: '90%', display: 'flex', flexDirection: 'column' }"
    >
      <div class="form-header">
        <span class="form-title">{{ isEditing ? t('skills.form.updateBtn') : t('skills.form.createBtn') }}</span>
        <van-button size="small" type="primary" :loading="saving" :disabled="!formValid" @click="onSubmitForm">
          {{ isEditing ? t('skills.form.updateBtn') : t('skills.form.createBtn') }}
        </van-button>
      </div>

      <div class="form-body">
        <!-- Skill ID (only for create) -->
        <van-field
          v-if="!isEditing"
          v-model="formDraft.skill_id"
          :label="t('skills.form.skillId')"
          :placeholder="t('skills.form.skillIdPlaceholder')"
          :error-message="skillIdError"
          @update:model-value="validateSkillId"
        />

        <!-- Name -->
        <van-field
          v-model="formDraft.name"
          :label="t('skills.form.skillName')"
          :placeholder="t('skills.form.skillNamePlaceholder')"
          required
        />

        <!-- Description -->
        <van-field
          v-model="formDraft.description"
          :label="t('skills.form.skillDescription')"
          :placeholder="t('skills.form.skillDescriptionPlaceholder')"
        />

        <!-- Icon -->
        <van-field :label="t('skills.form.skillIcon')">
          <template #input>
            <div class="icon-picker">
              <span
                v-for="emoji in emojiOptions"
                :key="emoji"
                class="icon-option"
                :class="{ active: formDraft.icon === emoji }"
                @click="formDraft.icon = emoji"
              >{{ emoji }}</span>
            </div>
          </template>
        </van-field>

        <!-- Color -->
        <van-field :label="t('skills.form.skillColor')">
          <template #input>
            <div class="color-picker">
              <span
                v-for="color in colorOptions"
                :key="color"
                class="color-option"
                :class="{ active: formDraft.color === color }"
                :style="{ backgroundColor: color }"
                @click="formDraft.color = color"
              />
            </div>
          </template>
        </van-field>

        <!-- Input Mode -->
        <van-field :label="t('skills.form.skillInputMode')">
          <template #input>
            <van-radio-group v-model="formDraft.input_mode" direction="horizontal">
              <van-radio name="trigger">{{ t('skills.form.inputModeTrigger') }}</van-radio>
              <van-radio name="free_text">{{ t('skills.form.inputModeFreeText') }}</van-radio>
            </van-radio-group>
          </template>
        </van-field>

        <!-- Prompt Content -->
        <van-field
          v-model="formDraft.prompt_content"
          type="textarea"
          :label="t('skills.form.skillPrompt')"
          :placeholder="t('skills.form.skillPromptPlaceholder')"
          :autosize="{ minHeight: 150 }"
          required
        />
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import {
  getSkillsGrouped,
  createCustomSkill,
  updateCustomSkill,
  deleteCustomSkill,
  toggleSkill,
  type SkillDefinition,
  type SkillListResponse,
} from '@/api/ai'

const { t } = useI18n()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

// State
const groupedSkills = ref<SkillListResponse | null>(null)
const loading = ref(false)
const showForm = ref(false)
const isEditing = ref(false)
const editingSkillId = ref<string | null>(null)
const saving = ref(false)
const skillIdError = ref('')

// All builtin skills (including disabled ones for toggle display)
const allBuiltinSkills = ref<SkillDefinition[]>([])

// Form draft
const formDraft = ref({
  skill_id: '',
  name: '',
  description: '',
  icon: '✨',
  color: '#6366f1',
  input_mode: 'trigger' as 'trigger' | 'free_text',
  prompt_content: '',
})

// Options
const emojiOptions = ['✨', '📊', '🔔', '💡', '🎯', '📈', '🔍', '💰', '🏠', '📋', '⚡', '🛡️', '🎨', '📦', '🔧', '💳', '📱', '🌐', '🤖', '📝']
const colorOptions = ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#f97316', '#a855f7']

// Builtin skill IDs — must mirror the backend's BUILTIN_CAPABILITIES list.
// chat and time_machine are NOT in this list; they're routing-only
// capabilities, blocked from custom skill IDs via RESERVED_NAMES below.
const builtinIds = ['alerts', 'allocation', 'disposal', 'liability', 'report', 'spending_leak']

// Names reserved for system internal use; cannot be reused as custom skill IDs.
// Mirrors the backend's RESERVED_NAMES constant in ai_skills.py.
const RESERVED_NAMES = ['chat', 'time_machine']

// Computed
const formValid = computed(() => {
  if (!isEditing.value && !formDraft.value.skill_id) return false
  if (!isEditing.value && skillIdError.value) return false
  if (!formDraft.value.name) return false
  if (!formDraft.value.prompt_content) return false
  return true
})

// Methods
async function loadSkills() {
  loading.value = true
  try {
    const res = await getSkillsGrouped()
    groupedSkills.value = res
    // For builtin toggle display, we need all builtin skills including disabled
    // The API returns only enabled ones, so we construct the full list
    allBuiltinSkills.value = builtinIds.map(id => {
      const found = res.builtin?.find((s: { id: string }) => s.id === id)
      return found || { id, skill_type: 'builtin' as const, is_enabled: false, display_order: 100, can_edit: false, can_delete: false }
    })
  } catch {
    showToast(t('toast.loadFailed'))
  } finally {
    loading.value = false
  }
}

function validateSkillId(value: string) {
  skillIdError.value = ''
  if (!value) return

  if (!/^[a-z][a-z0-9_-]*$/.test(value)) {
    skillIdError.value = t('skills.form.skillIdInvalid')
    return
  }
  if (value.length > 64) {
    skillIdError.value = t('skills.form.skillIdInvalid')
    return
  }
  if (builtinIds.includes(value)) {
    skillIdError.value = t('skills.form.skillIdConflict')
    return
  }
  if (RESERVED_NAMES.includes(value)) {
    // U14: chat and time_machine are reserved for system internal use.
    // Mirror the backend's RESERVED_NAMES check (per U1 RESERVED_NAMES).
    skillIdError.value = t('skills.form.skillIdReserved')
    return
  }
  if (groupedSkills.value?.custom.some(s => s.id === value)) {
    skillIdError.value = t('skills.form.skillIdExists')
    return
  }
}

async function onToggle(skillId: string, enabled: boolean) {
  if (!isOwner.value) return
  try {
    await toggleSkill(skillId, enabled)
    await loadSkills()
  } catch {
    showToast(t('toast.operationFailed'))
  }
}

function onCreateSkill() {
  isEditing.value = false
  editingSkillId.value = null
  formDraft.value = {
    skill_id: '',
    name: '',
    description: '',
    icon: '✨',
    color: '#6366f1',
    input_mode: 'trigger',
    prompt_content: '',
  }
  skillIdError.value = ''
  showForm.value = true
}

function onEditSkill(skill: SkillDefinition) {
  if (!isOwner.value) return
  isEditing.value = true
  editingSkillId.value = skill.id
  formDraft.value = {
    skill_id: skill.id,
    name: skill.name || '',
    description: skill.description || '',
    icon: skill.icon || '✨',
    color: skill.color || '#6366f1',
    input_mode: (skill.input_mode as 'trigger' | 'free_text') || 'trigger',
    prompt_content: '',
  }
  showForm.value = true
}

async function onSubmitForm() {
  if (!formValid.value) return
  saving.value = true
  try {
    if (isEditing.value && editingSkillId.value) {
      await updateCustomSkill(editingSkillId.value, {
        name: formDraft.value.name,
        description: formDraft.value.description || undefined,
        icon: formDraft.value.icon,
        color: formDraft.value.color,
        input_mode: formDraft.value.input_mode,
        prompt_content: formDraft.value.prompt_content || undefined,
      })
      showToast(t('skills.form.updateSuccess'))
    } else {
      await createCustomSkill({
        skill_id: formDraft.value.skill_id,
        name: formDraft.value.name,
        description: formDraft.value.description || undefined,
        icon: formDraft.value.icon,
        color: formDraft.value.color,
        input_mode: formDraft.value.input_mode,
        prompt_content: formDraft.value.prompt_content,
      })
      showToast(t('skills.form.createSuccess'))
    }
    showForm.value = false
    await loadSkills()
  } catch {
    showToast(t('toast.operationFailed'))
  } finally {
    saving.value = false
  }
}

async function onDeleteSkill(skill: SkillDefinition) {
  if (!isOwner.value) return
  try {
    await showConfirmDialog({
      title: t('common.confirm'),
      message: t('skills.form.deleteConfirm', { name: skill.name || skill.id }),
    })
    await deleteCustomSkill(skill.id)
    showToast(t('skills.form.deleteSuccess'))
    await loadSkills()
  } catch {
    // cancelled
  }
}

onMounted(loadSkills)
</script>

<style scoped>
.skills-manage-page {
  padding-bottom: 80px;
}

.section {
  margin-top: 12px;
}

.custom-skill-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.action-icon {
  color: var(--van-text-color-2);
  cursor: pointer;
}

.delete-icon {
  color: var(--van-danger-color);
}

.add-skill-section {
  padding: 16px;
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--van-background);
  border-top: 1px solid var(--van-border-color);
}

.form-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px;
  border-bottom: 1px solid var(--van-border-color);
}

.form-title {
  font-size: 16px;
  font-weight: 600;
}

.form-body {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 20px;
}

.icon-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.icon-option {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  cursor: pointer;
  font-size: 18px;
  border: 2px solid transparent;
}

.icon-option.active {
  border-color: var(--van-primary-color);
  background: var(--van-primary-color-light);
}

.color-picker {
  display: flex;
  gap: 8px;
}

.color-option {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid transparent;
}

.color-option.active {
  border-color: var(--van-text-color);
  box-shadow: 0 0 0 2px var(--van-background);
}
</style>