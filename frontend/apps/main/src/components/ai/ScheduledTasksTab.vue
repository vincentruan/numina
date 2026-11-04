<template>
  <div class="scheduled-tasks-tab">
    <van-skeleton v-if="loading" title :row="4" class="tab-skeleton" />

    <template v-else>
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <van-list
          :loading="listLoading"
          :finished="true"
          finished-text=""
        >
          <EmptyState
            v-if="tasks.length === 0"
            :description="
              isOwner ? t('scheduledTasks.emptyOwner') : t('scheduledTasks.emptyMember')
            "
          >
            <van-button
              v-if="isOwner"
              type="primary"
              size="small"
              icon="plus"
              @click="openCreate"
            >
              {{ t('scheduledTasks.createFirst') }}
            </van-button>
          </EmptyState>

          <div v-else class="task-list">
            <div v-for="task in tasks" :key="task.id" class="task-card">
              <div class="task-card__header">
                <div class="task-card__title">
                  <span class="task-card__skill">{{ skillLabel(task.skill_id) }}</span>
                  <span
                    class="task-card__status"
                    :class="`task-card__status--${task.status}`"
                  >
                    {{ statusLabel(task.status) }}
                  </span>
                </div>
                <van-switch
                  v-if="isOwner"
                  :model-value="task.is_enabled"
                  size="20px"
                  :loading="togglingId === task.id"
                  @update:model-value="(v: boolean) => onToggle(task, v)"
                />
                <span v-else class="task-card__readonly">
                  {{ task.is_enabled ? t('scheduledTasks.enabled') : t('scheduledTasks.disabled') }}
                </span>
              </div>

              <div class="task-card__schedule">
                <span class="task-card__cron">{{ describeCron(task.cron_expression) }}</span>
                <code class="task-card__raw">{{ task.cron_expression }}</code>
              </div>

              <div class="task-card__times">
                <span>
                  {{ t('scheduledTasks.nextRun') }}:
                  {{ formatTime(task.next_run_at) }}
                </span>
                <span>
                  {{ t('scheduledTasks.lastRun') }}:
                  {{ task.last_run_at ? formatTime(task.last_run_at) : t('scheduledTasks.never') }}
                </span>
              </div>

              <div v-if="task.last_error" class="task-card__error">
                <van-icon name="warning-o" />
                <span>{{ task.last_error }}</span>
              </div>

              <div v-if="isOwner" class="task-card__actions">
                <button class="action-btn action-btn--edit" @click="openEdit(task)">
                  <van-icon name="edit" size="18" />
                  <span>{{ t('common.edit') }}</span>
                </button>
                <button
                  class="action-btn action-btn--danger"
                  :disabled="deletingId === task.id"
                  @click="onDelete(task)"
                >
                  <van-icon :name="deletingId === task.id ? 'loading' : 'delete-o'" size="18" />
                  <span>{{ t('common.delete') }}</span>
                </button>
              </div>
            </div>
          </div>
        </van-list>
      </van-pull-refresh>

      <div v-if="isOwner" class="page-actions">
        <van-button block plain icon="plus" @click="openCreate">
          {{ t('scheduledTasks.create') }}
        </van-button>
      </div>
    </template>

    <van-popup
      v-model:show="showForm"
      position="bottom"
      round
      :style="{ maxHeight: '85vh', paddingBottom: 'env(safe-area-inset-bottom)' }"
    >
      <div class="form-popup">
        <div class="form-popup__header">
          <span class="form-popup__title">
            {{ editingId ? t('scheduledTasks.editTitle') : t('scheduledTasks.createTitle') }}
          </span>
          <van-icon name="cross" size="20" @click="showForm = false" />
        </div>

        <van-form @submit="onSubmit">
          <van-field
            :model-value="skillLabel(form.skill_id)"
            readonly
            is-link
            :label="t('scheduledTasks.skill')"
            :rules="[{ required: true, message: t('scheduledTasks.skillRequired') }]"
            @click="showSkillPicker = true"
          />

          <van-field :label="t('scheduledTasks.frequency')">
            <template #input>
              <van-radio-group v-model="form.frequency" direction="horizontal">
                <van-radio name="daily">{{ t('scheduledTasks.daily') }}</van-radio>
                <van-radio name="weekly">{{ t('scheduledTasks.weekly') }}</van-radio>
                <van-radio name="custom">{{ t('scheduledTasks.custom') }}</van-radio>
              </van-radio-group>
            </template>
          </van-field>

          <van-field
            v-if="form.frequency === 'custom'"
            v-model="form.customCron"
            :label="t('scheduledTasks.cron')"
            :placeholder="t('scheduledTasks.cronPlaceholder')"
            :error-message="cronError"
            @blur="validateCron"
            @update:model-value="cronError = ''"
          />

          <van-field
            v-else
            v-model="form.time"
            :label="t('scheduledTasks.time')"
            type="time"
            :placeholder="t('scheduledTasks.timePlaceholder')"
          />

          <van-field :label="t('scheduledTasks.enabledLabel')">
            <template #input>
              <van-switch v-model="form.is_enabled" size="20px" />
            </template>
          </van-field>

          <div class="form-popup__actions">
            <van-button
              block
              type="primary"
              native-type="submit"
              :loading="submitting"
            >
              {{ t('common.save') }}
            </van-button>
          </div>
        </van-form>
      </div>
    </van-popup>

    <van-popup v-model:show="showSkillPicker" position="bottom" round destroy-on-close>
      <van-picker
        :columns="skillColumns"
        @confirm="onSkillConfirm"
        @cancel="showSkillPicker = false"
      />
    </van-popup>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { showConfirmDialog, showFailToast, showSuccessToast } from 'vant'
import EmptyState from '@/components/common/EmptyState.vue'
import {
  createScheduledTask,
  deleteScheduledTask,
  fetchScheduledTasks,
  updateScheduledTask,
} from '@/api/ai-scheduled-tasks'
import type { ScheduledTask, SchedulableSkillId } from '@/api/ai-scheduled-tasks'
import { parseApiDate } from '@/utils/format'

const { isOwner } = defineProps<{ isOwner: boolean }>()

const { t, locale } = useI18n()

const tasks = ref<ScheduledTask[]>([])
const loading = ref(true)
const listLoading = ref(false)
const refreshing = ref(false)
const submitting = ref(false)
const togglingId = ref<string | null>(null)
const deletingId = ref<string | null>(null)

const showForm = ref(false)
const showSkillPicker = ref(false)
const editingId = ref<string | null>(null)
const cronError = ref('')

const SKILLS: SchedulableSkillId[] = ['asset-report', 'literacy-weekly-report']

type Frequency = 'daily' | 'weekly' | 'custom'

const form = reactive({
  skill_id: SKILLS[0] as SchedulableSkillId,
  frequency: 'daily' as Frequency,
  time: '09:00',
  customCron: '',
  is_enabled: true,
})

const skillColumns = computed(() =>
  SKILLS.map((value) => ({ text: skillLabel(value), value }))
)

function skillLabel(skillId: string): string {
  if (skillId === 'asset-report') return t('scheduledTasks.skillAssetReport')
  if (skillId === 'literacy-weekly-report') return t('scheduledTasks.skillLiteracyReport')
  return skillId
}

function statusLabel(status: string): string {
  if (status === 'running') return t('scheduledTasks.statusRunning')
  if (status === 'success') return t('scheduledTasks.statusSuccess')
  if (status === 'failed') return t('scheduledTasks.statusFailed')
  return t('scheduledTasks.statusIdle')
}

function describeCron(expression: string): string {
  const parts = expression.trim().split(/\s+/)
  if (parts.length !== 5) return expression
  const [minute, hour, dom, month, dow] = parts
  const time = `${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`
  if (hour === '*' || minute === '*' || dom !== '*' || month !== '*') {
    return t('scheduledTasks.freqCustomDesc')
  }
  if (dow === '*') return t('scheduledTasks.freqDailyAt', { time })
  if (dow === '0' || dow === '7') return t('scheduledTasks.freqWeeklyAt', { time })
  return t('scheduledTasks.freqCustomDesc')
}

function formatTime(iso: string): string {
  return parseApiDate(iso).toLocaleString(locale.value, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function buildCron(): string | null {
  if (form.frequency === 'custom') {
    const value = form.customCron.trim()
    if (!/^\S+ \S+ \S+ \S+ \S+$/.test(value)) return null
    return value
  }
  const [hour, minute] = form.time.split(':')
  if (hour === undefined || minute === undefined) return null
  const h = Number(hour)
  const m = Number(minute)
  if (Number.isNaN(h) || Number.isNaN(m)) return null
  return form.frequency === 'daily' ? `${m} ${h} * * *` : `${m} ${h} * * 0`
}

function validateCron() {
  cronError.value =
    buildCron() === null ? t('scheduledTasks.cronInvalid') : ''
}

function resetForm() {
  form.skill_id = SKILLS[0]
  form.frequency = 'daily'
  form.time = '09:00'
  form.customCron = ''
  form.is_enabled = true
  cronError.value = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  showForm.value = true
}

function openEdit(task: ScheduledTask) {
  editingId.value = task.id
  form.skill_id = task.skill_id as SchedulableSkillId
  form.is_enabled = task.is_enabled
  form.customCron = task.cron_expression
  form.frequency = 'custom'
  cronError.value = ''
  showForm.value = true
}

function onSkillConfirm({ selectedOptions }: { selectedOptions: Array<{ value?: string }> }) {
  const picked = selectedOptions[0]?.value
  if (picked) form.skill_id = picked as SchedulableSkillId
  showSkillPicker.value = false
}

async function load() {
  try {
    const res = await fetchScheduledTasks()
    tasks.value = res.data.items
  } catch {
    showFailToast(t('toast.operationFailed2'))
  }
}

async function onRefresh() {
  refreshing.value = true
  await load()
  refreshing.value = false
}

async function onSubmit() {
  const cron = buildCron()
  if (cron === null) {
    cronError.value = t('scheduledTasks.cronInvalid')
    return
  }

  submitting.value = true
  try {
    if (editingId.value) {
      await updateScheduledTask(editingId.value, {
        skill_id: form.skill_id,
        cron_expression: cron,
        is_enabled: form.is_enabled,
      })
      showSuccessToast(t('toast.saved'))
    } else {
      await createScheduledTask({
        skill_id: form.skill_id,
        cron_expression: cron,
        is_enabled: form.is_enabled,
      })
      showSuccessToast(t('toast.addSuccess'))
    }
    showForm.value = false
    await load()
  } catch {
    showFailToast(t('toast.operationFailed2'))
  } finally {
    submitting.value = false
  }
}

async function onToggle(task: ScheduledTask, enabled: boolean) {
  togglingId.value = task.id
  try {
    const res = await updateScheduledTask(task.id, { is_enabled: enabled })
    const index = tasks.value.findIndex((item) => item.id === task.id)
    if (index !== -1) tasks.value[index] = res.data
    showSuccessToast(t('toast.saved'))
  } catch {
    showFailToast(t('toast.operationFailed2'))
  } finally {
    togglingId.value = null
  }
}

async function onDelete(task: ScheduledTask) {
  try {
    await showConfirmDialog({
      title: t('scheduledTasks.deleteTitle'),
      message: t('scheduledTasks.deleteConfirm', { name: skillLabel(task.skill_id) }),
      confirmButtonColor: 'var(--van-danger-color)',
    })
  } catch {
    return
  }

  deletingId.value = task.id
  try {
    await deleteScheduledTask(task.id)
    tasks.value = tasks.value.filter((item) => item.id !== task.id)
    showSuccessToast(t('toast.deleted'))
  } catch {
    showFailToast(t('toast.operationFailed2'))
  } finally {
    deletingId.value = null
  }
}

onMounted(async () => {
  if (isOwner) {
    await load()
  }
  loading.value = false
})
</script>

<style scoped>
.scheduled-tasks-tab {
  padding-bottom: 24px;
}

.tab-skeleton {
  padding: 16px;
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 12px 16px 0;
}

.task-card {
  background: var(--bg-card, var(--card-bg));
  border-radius: 16px;
  border: 1px solid var(--border-light);
  overflow: hidden;
}

.task-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 14px 12px;
  border-bottom: 1px solid var(--border-light);
}

.task-card__title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.task-card__skill {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-card__status {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  flex-shrink: 0;
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--text-secondary) 12%, transparent);
}

.task-card__status--success {
  color: var(--van-success-color);
  background: color-mix(in srgb, var(--van-success-color) 12%, transparent);
}

.task-card__status--failed {
  color: var(--van-danger-color);
  background: color-mix(in srgb, var(--van-danger-color) 12%, transparent);
}

.task-card__status--running {
  color: var(--van-warning-color);
  background: color-mix(in srgb, var(--van-warning-color) 12%, transparent);
}

.task-card__readonly {
  font-size: 12px;
  color: var(--text-secondary);
}

.task-card__schedule {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px 0;
  flex-wrap: wrap;
}

.task-card__cron {
  font-size: 14px;
  color: var(--text-primary);
}

.task-card__raw {
  font-size: 12px;
  font-family: monospace;
  color: var(--text-tertiary);
  background: color-mix(in srgb, var(--text-secondary) 8%, transparent);
  padding: 2px 6px;
  border-radius: 4px;
}

.task-card__times {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 14px 12px;
  font-size: 12px;
  color: var(--text-secondary);
}

.task-card__error {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: 0 14px 12px;
  font-size: 12px;
  color: var(--van-danger-color);
  word-break: break-all;
}

.task-card__actions {
  display: flex;
  border-top: 1px solid var(--border-light);
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  padding: 10px 4px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  cursor: pointer;
  position: relative;
  -webkit-tap-highlight-color: transparent;
}

.action-btn + .action-btn::before {
  content: '';
  position: absolute;
  left: 0;
  top: 20%;
  height: 60%;
  width: 1px;
  background: var(--border-light);
}

.action-btn:active {
  background: color-mix(in srgb, var(--text-secondary) 8%, transparent);
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.action-btn--edit {
  color: #4f46e5;
}

[data-theme='dark'] .action-btn--edit {
  color: #818cf8;
}

.action-btn--danger {
  color: #ee0a24;
}

.page-actions {
  padding: 16px 16px 0;
}

.form-popup {
  padding: 16px;
  max-height: 85vh;
  overflow-y: auto;
}

.form-popup__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.form-popup__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.form-popup__actions {
  padding-top: 16px;
}
</style>
