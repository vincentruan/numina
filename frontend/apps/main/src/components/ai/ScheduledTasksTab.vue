<template>
  <div class="scheduled-tasks-tab">
    <van-skeleton v-if="loading" title :row="4" class="tab-skeleton" />

    <template v-else>
      <van-pull-refresh v-model="refreshing" @refresh="onRefresh">
        <van-list :loading="listLoading" :finished="true" finished-text="">
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
                <span v-if="task.is_default" class="task-card__badge task-card__badge--default">
                  {{ t('scheduledTasks.badgeDefault') }}
                </span>
                <span v-else-if="isOwner" class="task-card__badge task-card__badge--custom">
                  {{ t('scheduledTasks.badgeCustom') }}
                </span>
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

          <!-- Mode toggle -->
          <div class="form-mode-toggle">
            <span
              class="form-mode-toggle__item"
              :class="{ active: formMode === 'ui' }"
              @click="onFormModeChange('ui')"
            >{{ t('scheduledTasks.modeUI') }}</span>
            <span
              class="form-mode-toggle__item"
              :class="{ active: formMode === 'cron' }"
              @click="onFormModeChange('cron')"
            >{{ t('scheduledTasks.modeCron') }}</span>
          </div>

          <!-- Frequency -->
          <van-field :label="t('scheduledTasks.frequency')">
            <template #input>
              <van-radio-group v-model="form.frequency" direction="horizontal">
                <van-radio name="daily">{{ t('scheduledTasks.daily') }}</van-radio>
                <van-radio name="weekly">{{ t('scheduledTasks.weekly') }}</van-radio>
                <van-radio v-if="formMode === 'cron'" name="custom">{{ t('scheduledTasks.custom') }}</van-radio>
              </van-radio-group>
            </template>
          </van-field>

          <!-- UI mode: hour + minute pickers -->
          <template v-if="formMode === 'ui'">
            <van-field :label="t('scheduledTasks.time')">
              <template #input>
                <div class="time-input-group">
                  <input
                    type="number"
                    class="time-input"
                    :value="form.hour"
                    min="0"
                    max="23"
                    @input="(e) => { form.hour = clamp(parseInt((e.target as HTMLInputElement).value) || 0, 0, 23) }"
                  />
                  <span class="time-sep">{{ t('scheduledTasks.timeSepHour') }}</span>
                  <input
                    type="number"
                    class="time-input"
                    :value="form.minute"
                    min="0"
                    max="59"
                    @input="(e) => { form.minute = clamp(parseInt((e.target as HTMLInputElement).value) || 0, 0, 59) }"
                  />
                  <span class="time-sep">{{ t('scheduledTasks.timeSepMin') }}</span>
                </div>
              </template>
            </van-field>

            <van-field v-if="form.frequency === 'weekly'" :label="t('scheduledTasks.weeklyDay')">
              <template #input>
                <div class="weekly-days">
                  <button
                    v-for="(label, idx) in dayLabelsForCron"
                    :key="idx"
                    type="button"
                    class="weekly-day-btn"
                    :class="{ active: form.weeklyDay === idx }"
                    @click="form.weeklyDay = idx"
                  >{{ label }}</button>
                </div>
              </template>
            </van-field>
          </template>

          <!-- Cron mode: time picker or raw cron input -->
          <template v-else>
            <van-field
              v-if="form.frequency !== 'custom'"
              v-model="form.time"
              :label="t('scheduledTasks.time')"
              type="time"
              :placeholder="t('scheduledTasks.timePlaceholder')"
            />
            <van-field
              v-else
              v-model="form.customCron"
              :label="t('scheduledTasks.cron')"
              :placeholder="t('scheduledTasks.cronPlaceholder')"
              :error-message="cronError"
              @blur="validateCron"
              @update:model-value="cronError = ''"
            />
          </template>

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

// Form mode: 'ui' = friendly pickers, 'cron' = raw expression
// Default to 'ui' for new tasks; parsed from cron when editing
const formMode = ref<'ui' | 'cron'>('ui')

const SKILLS: SchedulableSkillId[] = ['asset-report', 'literacy-weekly-report']

type Frequency = 'daily' | 'weekly' | 'custom'

const form = reactive({
  skill_id: SKILLS[0] as SchedulableSkillId,
  frequency: 'daily' as Frequency,
  time: '09:00',
  customCron: '',
  is_enabled: true,
  hour: 9,
  minute: 0,
  weeklyDay: 1, // UI index: 0=Mon ... 6=Sun; cron conversion handled in buildCron/parseCronToForm
})

// i18n dayLabels are Monday-first: ['周一',...,'周日'].
// UI index 0=Monday ... 6=Sunday; cron uses 0/7=Sunday, 1-6=Monday-Saturday.
// vue-i18n returns the raw key path for an array-valued message unless the
// message is resolved as an object, so this yields [] and the weekly day
// picker disappeared. Fall back to English labels rather than an empty list —
// the cron value is numeric, only the button text suffers.
const FALLBACK_DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const dayLabelsForCron = computed(() => {
  const labels = t('familyConfig.dayLabels', { returnObjects: true }) as unknown
  return Array.isArray(labels) && labels.length >= 7
    ? (labels as string[])
    : FALLBACK_DAY_LABELS
})

const skillColumns = computed(() =>
  SKILLS.map((value) => ({ text: skillLabel(value), value }))
)

function clamp(val: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, val))
}

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

/** Build cron expression from form values. Returns null if invalid. */
function buildCron(): string | null {
  if (formMode.value === 'cron' && form.frequency === 'custom') {
    const value = form.customCron.trim()
    if (!/^\S+ \S+ \S+ \S+ \S+$/.test(value)) return null
    return value
  }
  let hour: number, minute: number
  if (formMode.value === 'ui') {
    hour = form.hour
    minute = form.minute
  } else {
    const [h, m] = form.time.split(':')
    if (h === undefined || m === undefined) return null
    hour = Number(h)
    minute = Number(m)
    if (Number.isNaN(hour) || Number.isNaN(minute)) return null
  }
  if (form.frequency === 'daily') {
    return `${minute} ${hour} * * *`
  }
  if (form.frequency === 'weekly') {
    // UI idx: 0=Mon..6=Sun; cron: 1=Mon..6=Sat, 0/7=Sun
    const cronDow = form.weeklyDay === 6 ? 0 : form.weeklyDay + 1
    return `${minute} ${hour} * * ${cronDow}`
  }
  return null
}

function validateCron() {
  cronError.value =
    buildCron() === null ? t('scheduledTasks.cronInvalid') : ''
}

function onFormModeChange(nextMode: 'ui' | 'cron') {
  if (formMode.value === nextMode) return
  if (nextMode === 'cron') {
    // Switching into Cron mode must expose the raw expression, even when the
    // current UI state is a simple daily/weekly schedule.
    form.customCron = buildCron() ?? form.customCron
    form.frequency = 'custom'
  } else {
    // Switching back derives hour/minute/day from the current raw expression.
    if (form.frequency === 'custom') parseCronToForm(form.customCron || '0 9 * * *')
  }
  formMode.value = nextMode
  cronError.value = ''
}

function resetForm() {
  form.skill_id = SKILLS[0]
  form.frequency = 'daily'
  form.time = '09:00'
  form.customCron = ''
  form.is_enabled = true
  form.hour = 9
  form.minute = 0
  form.weeklyDay = 1
  cronError.value = ''
  formMode.value = 'ui'
}

/** Parse cron expression into form fields for editing. Sets formMode automatically. */
function parseCronToForm(cronExpression: string) {
  const parts = cronExpression.trim().split(/\s+/)
  if (parts.length !== 5) {
    formMode.value = 'cron'
    form.frequency = 'custom'
    form.customCron = cronExpression
    return
  }
  const [min, hour, dom, month, dow] = parts
  form.minute = parseInt(min) || 0
  form.hour = parseInt(hour) || 0
  form.time = `${String(form.hour).padStart(2, '0')}:${String(form.minute).padStart(2, '0')}`
  if (dom === '*' && month === '*' && dow === '*') {
    form.frequency = 'daily'
    formMode.value = 'ui'
  } else if (dom === '*' && month === '*' && /^([0-7])$/.test(dow)) {
    form.frequency = 'weekly'
    const cronDow = parseInt(dow) % 7
    // cron 0/7=Sun -> UI idx 6; cron 1-6=Mon-Sat -> UI idx 0-5
    form.weeklyDay = cronDow === 0 ? 6 : cronDow - 1
    formMode.value = 'ui'
  } else {
    form.frequency = 'custom'
    form.customCron = cronExpression
    formMode.value = 'cron'
  }
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
  parseCronToForm(task.cron_expression)
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

.task-card__badge {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 4px;
  flex-shrink: 0;
}

.task-card__badge--default {
  color: var(--text-secondary);
  background: color-mix(in srgb, var(--text-secondary) 10%, transparent);
}

.task-card__badge--custom {
  color: var(--van-primary-color);
  background: color-mix(in srgb, var(--van-primary-color) 12%, transparent);
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

/* Form mode toggle */
.form-mode-toggle {
  display: flex;
  gap: 0;
  margin: 8px 0 12px;
  border: 1px solid var(--border-light, #ebedf0);
  border-radius: 8px;
  overflow: hidden;
}

.form-mode-toggle__item {
  flex: 1;
  text-align: center;
  padding: 6px 0;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--card-bg, var(--van-background-2));
  cursor: pointer;
  transition: all 0.15s;
}

.form-mode-toggle__item.active {
  color: #fff;
  background: var(--van-primary-color);
}

.form-mode-toggle__item + .form-mode-toggle__item {
  border-left: 1px solid var(--border-light, #ebedf0);
}

/* Time input (UI mode) */
.time-input-group {
  display: flex;
  align-items: center;
  gap: 4px;
}

.time-input {
  width: 52px;
  height: 30px;
  border: 1px solid var(--border-light, #ebedf0);
  border-radius: 6px;
  text-align: center;
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  background: var(--card-bg, var(--van-background-2));
  outline: none;
  -moz-appearance: textfield;
}

.time-input::-webkit-outer-spin-button,
.time-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.time-input:focus {
  border-color: var(--van-primary-color);
}

.time-sep {
  font-size: 13px;
  color: var(--text-secondary);
}

/* Weekly day picker (UI mode) */
.weekly-days {
  display: flex;
  gap: 4px;
}

.weekly-day-btn {
  min-width: 34px;
  height: 30px;
  border: 1px solid var(--border-light, #ebedf0);
  border-radius: 6px;
  background: var(--card-bg, var(--van-background-2));
  color: var(--text-primary);
  font-size: 12px;
  cursor: pointer;
  padding: 0 6px;
  transition: all 0.15s;
}

.weekly-day-btn.active {
  background: var(--van-primary-color);
  color: #fff;
  border-color: var(--van-primary-color);
}

[data-theme='dark'] .weekly-day-btn.active {
  color: #fff;
}
</style>
