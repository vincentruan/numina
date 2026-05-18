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
              <button class="action-btn action-btn--success" :disabled="actioningId === wish.id" @click="openRealize(wish)">
                <van-icon name="gift-o" size="16" />
                <span>{{ t('wishReview.btn.realize') }}</span>
              </button>
              <button class="action-btn action-btn--muted" :disabled="actioningId === wish.id" @click="defer(wish.id)">
                <van-icon name="clock-o" size="16" />
                <span>{{ t('wishReview.btn.defer') }}</span>
              </button>
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
              <button class="action-btn action-btn--primary" :disabled="actioningId === wish.id" @click="openApprove(wish)">
                <van-icon name="passed" size="16" />
                <span>{{ t('wishReview.btn.approve') }}</span>
              </button>
              <button class="action-btn action-btn--danger" :disabled="actioningId === wish.id" @click="openReject(wish)">
                <van-icon name="close" size="16" />
                <span>{{ t('wishReview.btn.reject') }}</span>
              </button>
            </div>
          </div>
        </div>

        <div v-if="pendingItems.length === 0 && redemptionItems.length === 0" class="empty">
          <p>{{ t('wishReview.emptyState') }}</p>
        </div>
      </template>
    </template>

    <!-- Approve dialog -->
    <div v-if="approveTarget" class="dialog-overlay" tabindex="-1" autofocus @click.self="approveTarget = null" @keydown.escape="approveTarget = null">
      <div class="dialog" role="dialog" aria-modal="true">
        <h3 class="dialog-title"><van-icon name="passed" size="20" color="#28a745" /> {{ t('wishReview.dialog.approveTitle') }}</h3>
        <p class="dialog-desc">{{ t('wishReview.dialog.approveDesc', { name: approveTarget.name }) }}</p>
        <div class="cost-readonly">
          <span class="cost-label">{{ t('wishReview.dialog.costLabel') }}</span>
          <span class="cost-value">{{ approveTarget.star_coin_cost ?? '-' }} ⭐</span>
        </div>
        <div v-if="dialogError" class="error-msg">{{ dialogError }}</div>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="approveTarget = null">{{ t('wishReview.btn.cancel') }}</button>
          <button class="btn-submit" :disabled="actioning" @click="approve">{{ t('wishReview.btn.confirmApprove') }}</button>
        </div>
      </div>
    </div>

    <!-- Reject dialog -->
    <div v-if="rejectTarget" class="dialog-overlay" tabindex="-1" autofocus @click.self="rejectTarget = null" @keydown.escape="rejectTarget = null">
      <div class="dialog" role="dialog" aria-modal="true">
        <h3 class="dialog-title"><van-icon name="close" size="20" color="#dc3545" /> {{ t('wishReview.dialog.rejectTitle') }}</h3>
        <p class="dialog-desc">{{ t('wishReview.dialog.rejectDesc', { name: rejectTarget.name }) }}</p>
        <input v-model="rejectReason" class="input" :placeholder="t('wishReview.dialog.rejectReasonPlaceholder')" maxlength="200" />
        <div v-if="dialogError" class="error-msg">{{ dialogError }}</div>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="rejectTarget = null">{{ t('wishReview.btn.cancel') }}</button>
          <button class="btn-reject-confirm" :disabled="actioning" @click="reject">{{ t('wishReview.btn.confirmReject') }}</button>
        </div>
      </div>
    </div>

    <!-- Realize dialog -->
    <div v-if="realizeTarget" class="dialog-overlay" tabindex="-1" autofocus @click.self="realizeTarget = null" @keydown.escape="realizeTarget = null">
      <div class="dialog" role="dialog" aria-modal="true">
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
  if (!approveTarget.value) return
  const cost = approveTarget.value.star_coin_cost
  if (!cost || cost < 1) return
  actioning.value = true
  dialogError.value = ''
  try {
    await approveChildWish(approveTarget.value.id, cost)
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
    dialogError.value = t('wishReview.error.operationFailed')
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
  background: var(--bg-secondary);
  min-height: 100vh;
  padding: 16px 16px 80px;
}
.loading, .empty {
  text-align: center;
  margin-top: 60px;
  color: var(--text-tertiary);
  font-size: 16px;
}
.section { margin-bottom: 20px; }
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 8px;
}
.wish-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 16px;
  box-shadow: var(--shadow-elevated, 0 2px 8px rgba(1, 1, 32, 0.06));
  margin-bottom: 10px;
}
.wish-card.redemption { border-left: 4px solid var(--color-success); }
.card-top { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.wish-emoji { font-size: 28px; flex-shrink: 0; }
.wish-info { flex: 1; }
.wish-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 2px;
}
.child-name {
  font-size: 13px;
  color: var(--text-tertiary);
  margin: 0 0 2px;
}
.wish-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 2px 0;
}
.cost { font-size: 13px; color: var(--color-cost, #f5a623); font-weight: 600; margin: 2px 0 0; }
.priority-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  display: inline-block;
  margin-top: 4px;
}
.priority-badge.high { background: var(--badge-high-bg, #ffe0e0); color: var(--badge-high-text, #c0392b); }
.priority-badge.medium { background: var(--badge-medium-bg, #fff3cd); color: var(--badge-medium-text, #856404); }
.priority-badge.low { background: var(--badge-low-bg, #e8f4fd); color: var(--badge-low-text, #1a6fa8); }
/* Piano-key action buttons */
.card-actions {
  display: flex;
  border-top: 1px solid var(--separator);
  margin-top: 12px;
  overflow: hidden;
}
.action-btn {
  flex: 1;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 12px 4px;
  border: none;
  background: transparent;
  color: var(--van-text-color-2, #969799);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
  position: relative;
  min-height: 44px;
}
.action-btn + .action-btn::before {
  content: '';
  position: absolute;
  left: 0;
  top: 20%;
  height: 60%;
  width: 1px;
  background: var(--separator);
}
.action-btn:active {
  background: rgba(128, 128, 128, 0.08);
}
.action-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.action-btn--primary {
  color: var(--van-primary-color, #1989fa);
}
.action-btn--success {
  color: var(--color-success);
}
.action-btn--danger {
  color: var(--van-danger-color, #ee0a24);
}
.action-btn--muted {
  color: var(--van-text-color-3, #c8c9cc);
}

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
  background: var(--card-bg);
  border-radius: 20px 20px 0 0;
  padding: 24px 20px 32px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.dialog h3 {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}
.dialog-title {
  display: flex;
  align-items: center;
  gap: 6px;
}
.cost-readonly {
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
.dialog-desc {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}
.input {
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
.btn-submit {
  flex: 2;
  padding: 12px;
  border: none;
  border-radius: 10px;
  background: var(--color-success);
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
  background: var(--error-bg, #f8d7da);
  color: var(--error-text, #721c24);
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
}
</style>
