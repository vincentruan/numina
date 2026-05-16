<template>
  <div class="review-page">
    <PageHeader :title="t('wishReview.title')" />

    <div v-if="loading" class="loading">{{ t('wishReview.loading') }}</div>

    <template v-else>
      <div v-if="error" class="error-msg">{{ error }}</div>

      <template v-else>
        <!-- Redemption requested (priority) -->
        <div v-if="redemptionItems.length > 0" class="section">
          <h3 class="section-title">{{ t('wishReview.section.redemptionRequested') }}</h3>
          <div v-for="wish in redemptionItems" :key="wish.id" class="wish-card redemption">
            <div class="card-top">
              <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
              <div class="wish-info">
                <p class="wish-name">{{ wish.name }}</p>
                <p class="child-name">{{ wish.child_display_name }}</p>
                <p class="cost">{{ t('wishReview.costLabel', { cost: wish.star_coin_cost }) }}</p>
              </div>
            </div>
            <div class="card-actions">
              <button class="btn-realize" :disabled="actioningId === wish.id" @click="openRealize(wish)">{{ t('wishReview.btn.realize') }}</button>
              <button class="btn-defer" :disabled="actioningId === wish.id" @click="defer(wish.id)">{{ t('wishReview.btn.defer') }}</button>
            </div>
          </div>
        </div>

        <!-- Pending review -->
        <div v-if="pendingItems.length > 0" class="section">
          <h3 class="section-title">{{ t('wishReview.section.pendingReview') }}</h3>
          <div v-for="wish in pendingItems" :key="wish.id" class="wish-card">
            <div class="card-top">
              <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
              <div class="wish-info">
                <p class="wish-name">{{ wish.name }}</p>
                <p class="child-name">{{ wish.child_display_name }}</p>
                <p v-if="wish.description" class="wish-desc">{{ wish.description }}</p>
                <span class="priority-badge" :class="wish.priority">{{ priorityLabel(wish.priority) }}</span>
              </div>
            </div>
            <div class="card-actions">
              <button class="btn-approve" :disabled="actioningId === wish.id" @click="openApprove(wish)">{{ t('wishReview.btn.approve') }}</button>
              <button class="btn-reject" :disabled="actioningId === wish.id" @click="openReject(wish)">{{ t('wishReview.btn.reject') }}</button>
            </div>
          </div>
        </div>

        <div v-if="pendingItems.length === 0 && redemptionItems.length === 0" class="empty">
          <p>{{ t('wishReview.emptyState') }}</p>
        </div>
      </template>
    </template>

    <!-- Approve dialog -->
    <div v-if="approveTarget" class="dialog-overlay" @click.self="approveTarget = null">
      <div class="dialog">
        <h3>{{ t('wishReview.dialog.approveTitle') }}</h3>
        <p class="dialog-desc">{{ t('wishReview.dialog.approveDesc', { name: approveTarget.name }) }}</p>
        <input
          v-model.number="costInput"
          type="number"
          class="input"
          :placeholder="t('wishReview.dialog.costPlaceholder')"
          min="1"
        />
        <div v-if="dialogError" class="error-msg">{{ dialogError }}</div>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="approveTarget = null">{{ t('wishReview.btn.cancel') }}</button>
          <button class="btn-submit" :disabled="actioning || !costInput || costInput < 1" @click="approve">{{ t('wishReview.btn.confirmApprove') }}</button>
        </div>
      </div>
    </div>

    <!-- Reject dialog -->
    <div v-if="rejectTarget" class="dialog-overlay" @click.self="rejectTarget = null">
      <div class="dialog">
        <h3>{{ t('wishReview.dialog.rejectTitle') }}</h3>
        <p class="dialog-desc">{{ t('wishReview.dialog.rejectTitle') }}「{{ rejectTarget.name }}」</p>
        <input v-model="rejectReason" class="input" :placeholder="t('wishReview.dialog.rejectReasonPlaceholder')" maxlength="200" />
        <div v-if="dialogError" class="error-msg">{{ dialogError }}</div>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="rejectTarget = null">{{ t('wishReview.btn.cancel') }}</button>
          <button class="btn-reject-confirm" :disabled="actioning" @click="reject">{{ t('wishReview.btn.confirmReject') }}</button>
        </div>
      </div>
    </div>

    <!-- Realize dialog -->
    <div v-if="realizeTarget" class="dialog-overlay" @click.self="realizeTarget = null">
      <div class="dialog">
        <h3>{{ t('wishReview.dialog.realizeTitle') }}</h3>
        <p class="dialog-desc">{{ t('wishReview.dialog.realizeDesc', { name: realizeTarget.name, cost: realizeTarget.star_coin_cost }) }}</p>
        <div v-if="dialogError" class="error-msg">{{ dialogError }}</div>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="realizeTarget = null">{{ t('wishReview.btn.cancel') }}</button>
          <button class="btn-realize-confirm" :disabled="actioning" @click="realize">{{ t('wishReview.btn.confirmRealize') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  listParentChildWishes, approveChildWish, rejectChildWish, realizeChildWish, deferChildWish,
  type ParentWish
} from '@/api/childWishes'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()

const wishes = ref<ParentWish[]>([])
const loading = ref(true)
const error = ref('')
const actioningId = ref<string | null>(null)

const approveTarget = ref<ParentWish | null>(null)
const rejectTarget = ref<ParentWish | null>(null)
const realizeTarget = ref<ParentWish | null>(null)
const costInput = ref<number | null>(null)
const rejectReason = ref('')
const actioning = ref(false)
const dialogError = ref('')

const pendingItems = computed(() => wishes.value.filter(w => w.status === 'pending_review'))
const redemptionItems = computed(() => wishes.value.filter(w => w.status === 'redemption_requested'))

function priorityLabel(p: string) {
  return p === 'high' ? t('wishReview.priority.high') : p === 'medium' ? t('wishReview.priority.medium') : t('wishReview.priority.low')
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    wishes.value = await listParentChildWishes()
  } catch {
    error.value = t('wishReview.loadingFailed')
  } finally {
    loading.value = false
  }
}

function openApprove(wish: ParentWish) {
  approveTarget.value = wish
  costInput.value = null
  dialogError.value = ''
}

function openReject(wish: ParentWish) {
  rejectTarget.value = wish
  rejectReason.value = ''
  dialogError.value = ''
}

function openRealize(wish: ParentWish) {
  realizeTarget.value = wish
  dialogError.value = ''
}

async function approve() {
  if (!approveTarget.value || !costInput.value || costInput.value < 1) return
  actioning.value = true
  dialogError.value = ''
  try {
    await approveChildWish(approveTarget.value.id, costInput.value)
    approveTarget.value = null
    await load()
  } catch {
    dialogError.value = t('wishReview.error.operationFailed')
  } finally {
    actioning.value = false
  }
}

async function reject() {
  if (!rejectTarget.value) return
  actioning.value = true
  dialogError.value = ''
  try {
    await rejectChildWish(rejectTarget.value.id, rejectReason.value || undefined)
    rejectTarget.value = null
    await load()
  } catch {
    dialogError.value = t('wishReview.error.operationFailed')
  } finally {
    actioning.value = false
  }
}

async function realize() {
  if (!realizeTarget.value) return
  actioning.value = true
  dialogError.value = ''
  try {
    await realizeChildWish(realizeTarget.value.id)
    realizeTarget.value = null
    await load()
  } catch {
    dialogError.value = t('wishReview.error.insufficientCoins')
  } finally {
    actioning.value = false
  }
}

async function defer(wishId: string) {
  actioningId.value = wishId
  try {
    await deferChildWish(wishId)
    await load()
  } catch {
    error.value = t('wishReview.error.operationFailed')
  } finally {
    actioningId.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.review-page {
  background: var(--bg-secondary, #f8f9fa);
  min-height: 100vh;
  padding: 16px 16px 80px;
}
.loading, .empty {
  text-align: center;
  margin-top: 60px;
  color: var(--text-tertiary, #999);
  font-size: 16px;
}
.section { margin-bottom: 20px; }
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary, #666);
  margin: 0 0 8px;
}
.wish-card {
  background: var(--card-bg, #fff);
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(1, 1, 32, 0.06);
  margin-bottom: 10px;
}
[data-theme='dark'] .wish-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.wish-card.redemption { border-left: 4px solid #28a745; }
.card-top { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.wish-emoji { font-size: 28px; flex-shrink: 0; }
.wish-info { flex: 1; }
.wish-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary, #333);
  margin: 0 0 2px;
}
.child-name {
  font-size: 13px;
  color: var(--text-tertiary, #888);
  margin: 0 0 2px;
}
.wish-desc {
  font-size: 13px;
  color: var(--text-secondary, #666);
  margin: 2px 0;
}
.cost { font-size: 13px; color: #f5a623; font-weight: 600; margin: 2px 0 0; }
[data-theme='dark'] .cost { color: #ffc04d; }
.priority-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  display: inline-block;
  margin-top: 4px;
}
.priority-badge.high { background: #ffe0e0; color: #c0392b; }
.priority-badge.medium { background: #fff3cd; color: #856404; }
.priority-badge.low { background: #e8f4fd; color: #1a6fa8; }
[data-theme='dark'] .priority-badge.high { background: rgba(192, 57, 43, 0.2); color: #e57373; }
[data-theme='dark'] .priority-badge.medium { background: rgba(133, 100, 4, 0.2); color: #ffb74d; }
[data-theme='dark'] .priority-badge.low { background: rgba(26, 111, 168, 0.2); color: #64b5f6; }
.card-actions { display: flex; gap: 8px; }
.card-actions button {
  flex: 1;
  padding: 8px 0;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.card-actions button:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-approve { background: #28a745; color: #fff; }
.btn-reject { background: #dc3545; color: #fff; }
.btn-realize { background: linear-gradient(135deg, #f9ca24, #f0932b); color: #fff; }
.btn-defer { background: #6c757d; color: #fff; }
[data-theme='dark'] .btn-defer { background: rgba(108, 117, 125, 0.6); }

/* Dialogs */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: flex-end;
  z-index: 100;
}
.dialog {
  background: var(--card-bg, #fff);
  border-radius: 20px 20px 0 0;
  padding: 24px 20px 32px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
[data-theme='dark'] .dialog {
  background: #1a1a2e;
}
.dialog h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary, #333);
  margin: 0;
}
.dialog-desc {
  font-size: 14px;
  color: var(--text-secondary, #666);
  margin: 0;
}
.input {
  border: 1px solid var(--separator, #e0e0e0);
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 15px;
  outline: none;
  width: 100%;
  box-sizing: border-box;
  background: var(--bg-secondary, #f8f8f8);
  color: var(--text-primary, #333);
}
[data-theme='dark'] .input {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  color: #ffffff;
}
.dialog-actions { display: flex; gap: 10px; }
.btn-cancel {
  flex: 1;
  padding: 12px;
  border: 1px solid var(--separator, #e0e0e0);
  border-radius: 10px;
  background: var(--bg-secondary, #f8f8f8);
  color: var(--text-primary, #333);
  font-size: 15px;
  cursor: pointer;
}
[data-theme='dark'] .btn-cancel {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.8);
}
.btn-submit {
  flex: 2;
  padding: 12px;
  border: none;
  border-radius: 10px;
  background: #28a745;
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}
.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-reject-confirm {
  flex: 2;
  padding: 12px;
  border: none;
  border-radius: 10px;
  background: #dc3545;
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}
.btn-reject-confirm:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-realize-confirm {
  flex: 2;
  padding: 12px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #f9ca24, #f0932b);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}
.btn-realize-confirm:disabled { opacity: 0.5; cursor: not-allowed; }
.error-msg {
  background: #f8d7da;
  color: #721c24;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
}
[data-theme='dark'] .error-msg {
  background: rgba(220, 53, 69, 0.15);
  color: #f1aeb5;
}
</style>
