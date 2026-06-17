<template>
  <div v-if="visible" class="dialog-overlay" tabindex="-1" @click.self="close" @keydown.escape="close">
    <div class="dialog" role="dialog" aria-modal="true">
      <!-- Stage 1: edit -->
      <template v-if="stage === 'edit'">
        <h3 class="dialog-title">{{ t('wishCostEdit.title') }}</h3>
        <p class="dialog-desc">{{ wish.name }}</p>
        <div class="cost-current">
          <span class="cost-label">{{ t('wishCostEdit.currentLabel') }}</span>
          <span class="cost-value">{{ wish.star_coin_cost ?? '-' }} ⭐</span>
        </div>
        <van-field
          class="cost-input"
          type="number"
          input-align="left"
          :model-value="newCostInput"
          :placeholder="t('wishCostEdit.placeholder')"
          @update:model-value="onCostInput"
        />
        <div v-if="inputError" class="error-msg">{{ inputError }}</div>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="close">{{ t('wishCostEdit.cancel') }}</button>
          <button class="btn-next" :disabled="!isValidInput" @click="onNext">
            {{ t('wishCostEdit.next') }}
          </button>
        </div>
      </template>

      <!-- Stage 2: warning -->
      <template v-else-if="stage === 'warning'">
        <h3 class="dialog-title">⚠️ {{ t('wishCostEdit.warningTitle') }}</h3>
        <p v-if="daysBefore !== null && daysAfter !== null" class="dialog-desc">
          {{ t('wishCostEdit.warningBodyDays', { before: daysBefore, after: daysAfter }) }}
        </p>
        <p v-else class="dialog-desc">
          {{ t('wishCostEdit.warningBodyProgress', {
            beforeCost: wish.star_coin_cost,
            afterCost: newCost,
            beforePct: progressBeforePct,
            afterPct: progressAfterPct,
          }) }}
        </p>
        <div v-if="submitError" class="error-msg">{{ submitError }}</div>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="stage = 'edit'">{{ t('wishCostEdit.reconsider') }}</button>
          <button class="btn-confirm" :disabled="submitting" @click="commit">
            {{ t('wishCostEdit.confirm') }}
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { showToast, showSuccessToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { updateChildWishCost, type ParentWish } from '@/api/childWishes'
import { getChildBalance, getChildLedger, type ChildLedgerEntry } from '@/api/family'
import { daysEstimate, reachabilityTint } from '@numina/math'

const props = defineProps<{
  visible: boolean
  wish: ParentWish
}>()

const emit = defineEmits<{
  'update:visible': [value: boolean]
  saved: []
}>()

const { t } = useI18n()

type Stage = 'edit' | 'warning'

const stage = ref<Stage>('edit')
const newCostInput = ref('')
const submitting = ref(false)
const submitError = ref('')
const childBalance = ref<number | null>(null)
const childLedger = ref<ChildLedgerEntry[]>([])

const childProgress = computed(() => {
  if (childBalance.value === null || !props.wish.star_coin_cost || props.wish.star_coin_cost <= 0) return 0
  return Math.min(1, childBalance.value / props.wish.star_coin_cost)
})

const newCost = computed(() => {
  const n = Number(newCostInput.value)
  return Number.isFinite(n) && n > 0 ? Math.round(n) : null
})

const isValidInput = computed(() => newCost.value !== null && newCost.value !== props.wish.star_coin_cost)

const inputError = computed(() => {
  if (!newCostInput.value) return ''
  if (newCost.value === null) return t('wishCostEdit.errors.invalid')
  if (newCost.value === props.wish.star_coin_cost) return t('wishCostEdit.errors.unchanged')
  return ''
})

const progressBeforePct = computed(() => Math.round((childProgress.value ?? 0) * 100))

const progressAfterPct = computed(() => {
  if (childBalance.value === null || newCost.value === null) return 0
  return Math.min(100, Math.round((childBalance.value / newCost.value) * 100))
})

const daysBefore = computed<number | null>(() => {
  if (childBalance.value === null || props.wish.star_coin_cost === null) return null
  return daysEstimate(
    childBalance.value,
    {
      wish_id: props.wish.id,
      name: props.wish.name,
      priority: props.wish.priority,
      star_coin_cost: props.wish.star_coin_cost,
      progress: childProgress.value,
      covered: childBalance.value >= props.wish.star_coin_cost,
    },
    childLedger.value,
  )
})

const daysAfter = computed<number | null>(() => {
  if (childBalance.value === null || newCost.value === null) return null
  return daysEstimate(
    childBalance.value,
    {
      wish_id: props.wish.id,
      name: props.wish.name,
      priority: props.wish.priority,
      star_coin_cost: newCost.value,
      progress: childBalance.value / newCost.value,
      covered: childBalance.value >= newCost.value,
    },
    childLedger.value,
  )
})

function shouldWarn(): boolean {
  if (childProgress.value <= 0) return false
  if (newCost.value === null) return false
  if (newCost.value === props.wish.star_coin_cost) return false

  if (daysBefore.value !== null && daysAfter.value !== null) {
    if (Math.abs(daysAfter.value - daysBefore.value) >= 1) return true
  }

  if (childBalance.value !== null && props.wish.star_coin_cost !== null) {
    const tintBefore = reachabilityTint(
      {
        wish_id: props.wish.id,
        name: props.wish.name,
        priority: props.wish.priority,
        star_coin_cost: props.wish.star_coin_cost,
        progress: childProgress.value,
        covered: childBalance.value >= props.wish.star_coin_cost,
      },
      daysBefore.value,
    )
    const tintAfter = reachabilityTint(
      {
        wish_id: props.wish.id,
        name: props.wish.name,
        priority: props.wish.priority,
        star_coin_cost: newCost.value,
        progress: childBalance.value / newCost.value,
        covered: childBalance.value >= newCost.value,
      },
      daysAfter.value,
    )
    if (tintBefore !== tintAfter) return true
  }

  const oldCost = props.wish.star_coin_cost ?? 0
  if (oldCost > 0) {
    const ratio = Math.abs(newCost.value - oldCost) / oldCost
    if (ratio >= 0.05) return true
  }
  return false
}

function onCostInput(value: string) {
  newCostInput.value = value
  submitError.value = ''
}

function onNext() {
  if (!isValidInput.value) return
  submitError.value = ''
  if (shouldWarn()) {
    stage.value = 'warning'
  } else {
    commit()
  }
}

async function commit() {
  if (newCost.value === null) return
  submitting.value = true
  submitError.value = ''
  try {
    await updateChildWishCost(props.wish.id, newCost.value)
    showSuccessToast(t('wishCostEdit.success'))
    emit('saved')
    close()
  } catch {
    submitError.value = t('wishCostEdit.error')
  } finally {
    submitting.value = false
  }
}

function close() {
  stage.value = 'edit'
  newCostInput.value = ''
  submitError.value = ''
  emit('update:visible', false)
}

watch(
  () => [props.visible, props.wish.child_user_id] as const,
  async ([v, childId]) => {
    if (v && childId) {
      try {
        const [balanceRes, ledgerRes] = await Promise.all([
          getChildBalance(childId),
          getChildLedger(childId),
        ])
        childBalance.value = balanceRes.data.balance
        childLedger.value = ledgerRes.data
      } catch {
        childBalance.value = null
        childLedger.value = []
      }
    } else if (!v) {
      childBalance.value = null
      childLedger.value = []
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-end;
  z-index: 100;
}

.dialog {
  background: var(--card-bg);
  border-radius: 20px 20px 0 0;
  padding: 24px 20px 32px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.dialog-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.dialog-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}

.cost-current {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-secondary);
  border-radius: 10px;
  padding: 10px 14px;
}

.cost-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.cost-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-cost, #f5a623);
}

.cost-input {
  border: 1px solid var(--separator);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 15px;
  outline: none;
  width: 100%;
  box-sizing: border-box;
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.error-msg {
  background: var(--error-bg, #f8d7da);
  color: var(--error-text, #721c24);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
}

.dialog-actions { display: flex; gap: 10px; }

.btn-cancel {
  flex: 1;
  padding: 12px;
  border: 1px solid var(--separator);
  border-radius: 10px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 15px;
  cursor: pointer;
}

.btn-next,
.btn-confirm {
  flex: 2;
  padding: 12px;
  border: none;
  border-radius: 10px;
  background: var(--van-primary-color);
  color: var(--color-on-primary);
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}

.btn-confirm {
  background: var(--color-cost);
}

.btn-next:disabled,
.btn-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
