<template>
  <div class="review-page">
    <PageHeader title="心愿审核" />

    <div v-if="loading" class="loading">加载中...</div>
    <div v-if="error" class="error-msg">{{ error }}</div>

    <!-- Redemption requested (priority) -->
    <div v-if="!loading && redemptionItems.length > 0" class="section">
      <h3 class="section-title">待兑现 🎁</h3>
      <div v-for="wish in redemptionItems" :key="wish.id" class="wish-card redemption">
        <div class="card-top">
          <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
          <div class="wish-info">
            <p class="wish-name">{{ wish.name }}</p>
            <p class="child-name">{{ wish.child_display_name }}</p>
            <p class="cost">目标积分：{{ wish.star_coin_cost }} ⭐</p>
          </div>
        </div>
        <div class="card-actions">
          <button class="btn-realize" :disabled="actioningId === wish.id" @click="openRealize(wish)">兑现</button>
          <button class="btn-defer" :disabled="actioningId === wish.id" @click="defer(wish.id)">暂不兑现</button>
        </div>
      </div>
    </div>

    <!-- Pending review -->
    <div v-if="!loading && pendingItems.length > 0" class="section">
      <h3 class="section-title">待审核 ⏳</h3>
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
          <button class="btn-approve" :disabled="actioningId === wish.id" @click="openApprove(wish)">批准</button>
          <button class="btn-reject" :disabled="actioningId === wish.id" @click="openReject(wish)">拒绝</button>
        </div>
      </div>
    </div>

    <div v-if="!loading && pendingItems.length === 0 && redemptionItems.length === 0" class="empty">
      <p>暂无待处理心愿 ✅</p>
    </div>

    <!-- Approve dialog -->
    <div v-if="approveTarget" class="dialog-overlay" @click.self="approveTarget = null">
      <div class="dialog">
        <h3>批准心愿</h3>
        <p class="dialog-desc">「{{ approveTarget.name }}」需要多少星星币？</p>
        <input
          v-model.number="costInput"
          type="number"
          class="input"
          placeholder="积分数量（≥1）"
          min="1"
        />
        <div v-if="dialogError" class="error-msg">{{ dialogError }}</div>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="approveTarget = null">取消</button>
          <button class="btn-submit" :disabled="actioning || !costInput || costInput < 1" @click="approve">确认批准</button>
        </div>
      </div>
    </div>

    <!-- Reject dialog -->
    <div v-if="rejectTarget" class="dialog-overlay" @click.self="rejectTarget = null">
      <div class="dialog">
        <h3>拒绝心愿</h3>
        <p class="dialog-desc">「{{ rejectTarget.name }}」</p>
        <input v-model="rejectReason" class="input" placeholder="拒绝原因（可选）" maxlength="200" />
        <div v-if="dialogError" class="error-msg">{{ dialogError }}</div>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="rejectTarget = null">取消</button>
          <button class="btn-reject-confirm" :disabled="actioning" @click="reject">确认拒绝</button>
        </div>
      </div>
    </div>

    <!-- Realize dialog -->
    <div v-if="realizeTarget" class="dialog-overlay" @click.self="realizeTarget = null">
      <div class="dialog">
        <h3>兑现心愿 🎊</h3>
        <p class="dialog-desc">确认兑现「{{ realizeTarget.name }}」？将扣除 {{ realizeTarget.star_coin_cost }} ⭐ 并创建资产。</p>
        <div v-if="dialogError" class="error-msg">{{ dialogError }}</div>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="realizeTarget = null">取消</button>
          <button class="btn-realize-confirm" :disabled="actioning" @click="realize">确认兑现</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  listParentChildWishes, approveChildWish, rejectChildWish, realizeChildWish, deferChildWish,
  type ParentWish
} from '@/api/childWishes'
import PageHeader from '@/components/common/PageHeader.vue'

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
  return p === 'high' ? '高优先级 🔥' : p === 'medium' ? '中优先级 ⭐' : '低优先级 💤'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    wishes.value = await listParentChildWishes()
  } catch {
    error.value = '加载失败，请刷新重试'
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
    dialogError.value = '操作失败，请重试'
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
    dialogError.value = '操作失败，请重试'
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
    dialogError.value = '积分不足或操作失败，请重试'
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
    error.value = '操作失败，请重试'
  } finally {
    actioningId.value = null
  }
}

onMounted(load)
</script>

<style scoped>
.review-page {
  background: #f8f9fa;
  min-height: 100vh;
  padding: 16px 16px 80px;
}
.loading, .empty {
  text-align: center;
  margin-top: 60px;
  color: #999;
  font-size: 16px;
}
.section { margin-bottom: 20px; }
.section-title { font-size: 14px; font-weight: 600; color: #666; margin: 0 0 8px; }
.wish-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  margin-bottom: 10px;
}
.wish-card.redemption { border-left: 4px solid #28a745; }
.card-top { display: flex; align-items: flex-start; gap: 12px; margin-bottom: 12px; }
.wish-emoji { font-size: 28px; flex-shrink: 0; }
.wish-info { flex: 1; }
.wish-name { font-size: 16px; font-weight: 600; color: #333; margin: 0 0 2px; }
.child-name { font-size: 13px; color: #888; margin: 0 0 2px; }
.wish-desc { font-size: 13px; color: #666; margin: 2px 0; }
.cost { font-size: 13px; color: #f5a623; font-weight: 600; margin: 2px 0 0; }
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

/* Dialogs */
.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: flex-end;
  z-index: 100;
}
.dialog {
  background: #fff;
  border-radius: 20px 20px 0 0;
  padding: 24px 20px 32px;
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.dialog h3 { font-size: 18px; font-weight: 700; color: #333; margin: 0; }
.dialog-desc { font-size: 14px; color: #666; margin: 0; }
.input {
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 15px;
  outline: none;
  width: 100%;
  box-sizing: border-box;
}
.dialog-actions { display: flex; gap: 10px; }
.btn-cancel {
  flex: 1;
  padding: 12px;
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  background: #f8f8f8;
  font-size: 15px;
  cursor: pointer;
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
.error-msg { background: #f8d7da; color: #721c24; border-radius: 8px; padding: 10px 14px; font-size: 14px; }
</style>
