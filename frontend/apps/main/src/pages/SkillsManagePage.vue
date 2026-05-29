<template>
  <div class="skills-manage-page">
    <PageHeader :title="t('skills.title')" />

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
        :is-link="isOwner"
        @click="isOwner && onEditSkill(skill)"
      >
        <template #value>
          <div class="custom-skill-actions" @click.stop>
            <van-switch
              :model-value="skill.is_enabled"
              size="20px"
              :disabled="!isOwner"
              @change="(v: boolean) => onToggle(skill.id, v)"
            />
            <van-icon v-if="isOwner" name="delete-o" size="18" class="action-icon delete-icon" @click="onDeleteSkill(skill)" />
          </div>
        </template>
      </van-cell>
      <van-cell v-if="!groupedSkills?.custom?.length" :title="t('common.noData')" />
    </van-cell-group>

    <div v-if="isOwner" class="bottom-bar">
      <van-button block round type="primary" icon="plus" @click="onCreateSkill">
        {{ t('skills.form.createBtn') }}
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { showToast, showConfirmDialog } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  getSkillsGrouped,
  deleteCustomSkill,
  toggleSkill,
  type SkillDefinition,
  type SkillListResponse,
} from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()
const isOwner = computed(() => authStore.user?.role === 'owner')

const groupedSkills = ref<SkillListResponse | null>(null)
const allBuiltinSkills = ref<SkillDefinition[]>([])

const builtinIds = ['alerts', 'allocation', 'disposal', 'liability', 'report', 'spending_leak']

async function loadSkills() {
  try {
    const res = await getSkillsGrouped()
    groupedSkills.value = res
    allBuiltinSkills.value = builtinIds.map(id => {
      const found = res.builtin?.find((s: { id: string }) => s.id === id)
      return found || { id, skill_type: 'builtin' as const, is_enabled: false, display_order: 100, can_edit: false, can_delete: false }
    })
  } catch {
    showToast(t('toast.loadFailed'))
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
  router.push({ name: 'SkillCreate' })
}

function onEditSkill(skill: SkillDefinition) {
  if (!isOwner.value) return
  router.push({ name: 'SkillEdit', params: { id: skill.id } })
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
  padding-bottom: calc(120px + env(safe-area-inset-bottom));
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

.bottom-bar {
  position: fixed;
  bottom: calc(50px + env(safe-area-inset-bottom));
  left: 0;
  right: 0;
  padding: 12px 16px;
  background: var(--van-background);
}
</style>
