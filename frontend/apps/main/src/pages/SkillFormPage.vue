<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter, useRoute } from 'vue-router'
import { showToast, showFailToast } from 'vant'
import {
  getSkillsGrouped,
  createCustomSkill,
  updateCustomSkill,
  type SkillDefinition,
} from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'
import MarkdownEditor from '@/components/common/MarkdownEditor.vue'

const { t } = useI18n()
const router = useRouter()
const route = useRoute()

const editingId = computed(() => {
  const v = route.params.id
  return Array.isArray(v) ? v[0] : v
})
const isEdit = computed(() => !!editingId.value)

const saving = ref(false)
const loaded = ref(!isEdit.value)
const skillIdError = ref('')
const existingSkillIds = ref<Set<string>>(new Set())

const form = reactive({
  skill_id: '',
  name: '',
  description: '',
  icon: '✨',
  color: '#6366f1',
  input_mode: 'trigger' as 'trigger' | 'free_text',
  prompt_content: '',
})

const emojiOptions = ['✨', '📊', '🔔', '💡', '🎯', '📈', '🔍', '💰', '🏠', '📋', '⚡', '🛡️', '🎨', '📦', '🔧', '💳', '📱', '🌐', '🤖', '📝']
const colorOptions = ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#f97316', '#a855f7']

const builtinIds = ['alerts', 'allocation', 'disposal', 'liability', 'report', 'spending_leak']
const RESERVED_NAMES = ['chat', 'time_machine']

const formValid = computed(() => {
  if (!isEdit.value && !form.skill_id) return false
  if (!isEdit.value && skillIdError.value) return false
  if (!form.name) return false
  if (!isEdit.value && !form.prompt_content) return false
  return true
})

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
    skillIdError.value = t('skills.form.skillIdReserved')
    return
  }
  if (existingSkillIds.value.has(value)) {
    skillIdError.value = t('skills.form.skillIdExists')
  }
}

function loadSkill(skill: SkillDefinition) {
  form.skill_id = skill.id
  form.name = skill.name || ''
  form.description = skill.description || ''
  form.icon = skill.icon || '✨'
  form.color = skill.color || '#6366f1'
  form.input_mode = (skill.input_mode as 'trigger' | 'free_text') || 'trigger'
  form.prompt_content = ''
}

async function onSubmit() {
  if (!formValid.value) return
  saving.value = true
  try {
    if (isEdit.value && editingId.value) {
      await updateCustomSkill(editingId.value, {
        name: form.name,
        description: form.description || undefined,
        icon: form.icon,
        color: form.color,
        input_mode: form.input_mode,
        prompt_content: form.prompt_content || undefined,
      })
      showToast(t('skills.form.updateSuccess'))
    } else {
      await createCustomSkill({
        skill_id: form.skill_id,
        name: form.name,
        description: form.description || undefined,
        icon: form.icon,
        color: form.color,
        input_mode: form.input_mode,
        prompt_content: form.prompt_content,
      })
      showToast(t('skills.form.createSuccess'))
    }
    router.back()
  } catch {
    showFailToast(t('toast.operationFailed'))
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const res = await getSkillsGrouped()
    existingSkillIds.value = new Set(res.custom.map((s) => s.id))
    if (isEdit.value && editingId.value) {
      const skill = res.custom.find((s) => s.id === editingId.value)
      if (skill) {
        loadSkill(skill)
      } else {
        showFailToast(t('toast.loadFailed'))
        router.replace({ name: 'SkillsManage' })
        return
      }
    }
  } catch {
    showFailToast(t('toast.loadFailed'))
    if (isEdit.value) {
      router.replace({ name: 'SkillsManage' })
      return
    }
  } finally {
    loaded.value = true
  }
})
</script>

<template>
  <div class="skill-form-page">
    <PageHeader
      :title="isEdit ? t('skills.form.editTitle') : t('skills.form.createTitle')"
    />

    <template v-if="loaded">
      <van-cell-group inset class="section">
        <van-field
          v-if="!isEdit"
          v-model="form.skill_id"
          :label="t('skills.form.skillId')"
          :placeholder="t('skills.form.skillIdPlaceholder')"
          :error-message="skillIdError"
          @update:model-value="validateSkillId"
        />
        <van-field
          v-model="form.name"
          :label="t('skills.form.skillName')"
          :placeholder="t('skills.form.skillNamePlaceholder')"
          required
        />
        <van-field
          v-model="form.description"
          :label="t('skills.form.skillDescription')"
          :placeholder="t('skills.form.skillDescriptionPlaceholder')"
        />
      </van-cell-group>

      <van-cell-group inset :title="t('skills.form.skillIcon')" class="section">
        <div class="icon-grid">
          <div
            v-for="emoji in emojiOptions"
            :key="emoji"
            class="icon-option"
            :class="{ 'icon-option--active': form.icon === emoji }"
            @click="form.icon = emoji"
          >
            {{ emoji }}
          </div>
        </div>
      </van-cell-group>

      <van-cell-group inset :title="t('skills.form.skillColor')" class="section">
        <div class="color-grid">
          <div
            v-for="color in colorOptions"
            :key="color"
            class="color-option"
            :class="{ 'color-option--active': form.color === color }"
            :style="{ background: color }"
            @click="form.color = color"
          />
        </div>
      </van-cell-group>

      <van-cell-group inset class="section">
        <van-field :label="t('skills.form.skillInputMode')">
          <template #input>
            <van-radio-group v-model="form.input_mode" direction="horizontal">
              <van-radio name="trigger">{{ t('skills.form.inputModeTrigger') }}</van-radio>
              <van-radio name="free_text">{{ t('skills.form.inputModeFreeText') }}</van-radio>
            </van-radio-group>
          </template>
        </van-field>
      </van-cell-group>

      <van-cell-group inset :title="t('skills.form.skillPrompt')" class="section">
        <MarkdownEditor
          v-model="form.prompt_content"
          :placeholder="isEdit ? t('skills.form.skillPromptPlaceholderEdit') : t('skills.form.skillPromptPlaceholder')"
        />
      </van-cell-group>

      <div class="bottom-bar">
        <van-button
          type="primary"
          block
          round
          :loading="saving"
          :disabled="!formValid"
          @click="onSubmit"
        >
          {{ isEdit ? t('skills.form.updateBtn') : t('skills.form.createBtn') }}
        </van-button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.skill-form-page {
  background: var(--van-background);
  min-height: 100vh;
  padding-bottom: calc(120px + env(safe-area-inset-bottom));
}

.section {
  margin-top: 12px;
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
  font-size: 22px;
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
  flex-wrap: wrap;
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
  padding: 12px 16px;
  background: var(--van-background);
}
</style>
