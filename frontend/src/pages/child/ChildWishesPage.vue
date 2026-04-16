<template>
  <div class="wishes-page">
    <!-- Stats bar -->
    <div v-if="stats" class="stats-bar">
      <span class="balance">⭐ {{ stats.balance }}</span>
      <span class="wish-count">{{ stats.active_wish_count }} 个心愿进行中</span>
    </div>

    <div v-if="loading" class="loading">加载中...</div>
    <div v-if="error" class="error-msg">{{ error }}</div>

    <!-- Active wishes with savings jar -->
    <div v-if="!loading && activeWishes.length > 0" class="section">
      <h3 class="section-title">进行中</h3>
      <div v-for="wish in activeWishes" :key="wish.id" class="wish-card">
        <div class="wish-top">
          <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
          <div class="wish-info">
            <p class="wish-name">{{ wish.name }}</p>
            <span class="priority-badge" :class="wish.priority">{{ priorityLabel(wish.priority) }}</span>
          </div>
        </div>
        <!-- Savings jar progress -->
        <div v-if="wish.has_cost_set && wish.progress !== null" class="jar-wrap">
          <div class="jar">
            <div class="jar-fill" :class="jarClass(wish.progress)" :style="{ width: (wish.progress * 100) + '%' }"></div>
          </div>
          <span class="jar-pct">{{ Math.round((wish.progress ?? 0) * 100) }}%</span>
        </div>
        <div v-else class="jar-pending">等待爸妈设定目标 ⏳</div>
        <button
          v-if="wish.status === 'active' && wish.progress !== null && wish.progress >= 1"
          class="btn-redeem"
          :disabled="actioningId === wish.id"
          @click="redeem(wish.id)"
        >让爸妈实现 🎉</button>
      </div>
    </div>

    <!-- Redemption requested -->
    <div v-if="!loading && redemptionWishes.length > 0" class="section">
      <h3 class="section-title">兑现申请中</h3>
      <div v-for="wish in redemptionWishes" :key="wish.id" class="wish-card">
        <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
        <div class="wish-info">
          <p class="wish-name">{{ wish.name }}</p>
          <span class="status-badge redemption">等待爸妈兑现 🎁</span>
        </div>
      </div>
    </div>

    <!-- Pending review -->
    <div v-if="!loading && pendingWishes.length > 0" class="section">
      <h3 class="section-title">审核中</h3>
      <div v-for="wish in pendingWishes" :key="wish.id" class="wish-card">
        <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
        <div class="wish-info">
          <p class="wish-name">{{ wish.name }}</p>
          <span class="status-badge pending">等待爸妈审核 ⏳</span>
        </div>
      </div>
    </div>

    <!-- Realized -->
    <div v-if="!loading && realizedWishes.length > 0" class="section">
      <h3 class="section-title">已实现 🎊</h3>
      <div v-for="wish in realizedWishes" :key="wish.id" class="wish-card realized">
        <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
        <div class="wish-info">
          <p class="wish-name">{{ wish.name }}</p>
          <span class="status-badge realized">已实现 ✅</span>
        </div>
      </div>
    </div>

    <!-- Rejected -->
    <div v-if="!loading && rejectedWishes.length > 0" class="section">
      <h3 class="section-title">未通过</h3>
      <div v-for="wish in rejectedWishes" :key="wish.id" class="wish-card rejected">
        <span class="wish-emoji">{{ wish.emoji || '🌟' }}</span>
        <div class="wish-info">
          <p class="wish-name">{{ wish.name }}</p>
          <span class="status-badge rejected">未通过 ❌</span>
          <p v-if="wish.rejection_reason" class="rejection-reason">{{ wish.rejection_reason }}</p>
        </div>
      </div>
    </div>

    <!-- Empty state -->
    <div v-if="!loading && totalWishes === 0" class="empty">
      <p>还没有心愿，快许个愿吧 🌠</p>
    </div>

    <!-- Create wish button -->
    <button class="btn-create" @click="showCreate = true">+ 许个愿</button>

    <!-- Create wish dialog -->
    <div v-if="showCreate" class="dialog-overlay" @click.self="showCreate = false">
      <div class="dialog">
        <h3>许个愿 🌟</h3>
        <input v-model="form.name" class="input" placeholder="心愿名称（最多50字）" maxlength="50" />
        <input v-model="form.emoji" class="input" placeholder="表情符号（可选）" maxlength="4" />
        <textarea v-model="form.description" class="input textarea" placeholder="描述（可选，最多200字）" maxlength="200"></textarea>
        <div class="priority-select">
          <span>优先级：</span>
          <button
            v-for="p in priorities"
            :key="p.value"
            class="priority-btn"
            :class="{ active: form.priority === p.value }"
            @click="form.priority = p.value"
          >{{ p.label }}</button>
        </div>
        <div v-if="createError" class="error-msg">{{ createError }}</div>
        <div class="dialog-actions">
          <button class="btn-cancel" @click="showCreate = false">取消</button>
          <button class="btn-submit" :disabled="creating || !form.name.trim()" @click="createWish">提交</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  listChildWishes, getChildWishStats, createChildWish, requestRedemption,
  type ChildWishList, type ChildWishStats
} from '@/api/childWishes'

const wishList = ref<ChildWishList | null>(null)
const stats = ref<ChildWishStats | null>(null)
const loading = ref(true)
const error = ref('')
const actioningId = ref<string | null>(null)

const showCreate = ref(false)
const creating = ref(false)
const createError = ref('')
const form = ref({ name: '', emoji: '', description: '', priority: 'medium' as 'high' | 'medium' | 'low' })

const priorities = [
  { value: 'high' as const, label: '高 🔥' },
  { value: 'medium' as const, label: '中 ⭐' },
  { value: 'low' as const, label: '低 💤' },
]

const activeWishes = computed(() => wishList.value?.active ?? [])
const pendingWishes = computed(() => wishList.value?.pending_review ?? [])
const redemptionWishes = computed(() => wishList.value?.redemption_requested ?? [])
const realizedWishes = computed(() => wishList.value?.realized ?? [])
const rejectedWishes = computed(() => wishList.value?.rejected ?? [])
const totalWishes = computed(() =>
  activeWishes.value.length + pendingWishes.value.length + redemptionWishes.value.length +
  realizedWishes.value.length + rejectedWishes.value.length
)

function priorityLabel(p: string) {
  return p === 'high' ? '高优先级 🔥' : p === 'medium' ? '中优先级 ⭐' : '低优先级 💤'
}

function jarClass(progress: number) {
  if (progress >= 1) return 'full'
  if (progress >= 0.5) return 'half'
  return 'low'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [list, s] = await Promise.all([listChildWishes(), getChildWishStats()])
    wishList.value = list
    stats.value = s
  } catch {
    error.value = '加载失败，请刷新重试'
  } finally {
    loading.value = false
  }
}

async function redeem(wishId: string) {
  actioningId.value = wishId
  try {
    await requestRedemption(wishId)
    await load()
  } catch {
    error.value = '申请失败，请重试'
  } finally {
    actioningId.value = null
  }
}

async function createWish() {
  if (!form.value.name.trim()) return
  creating.value = true
  createError.value = ''
  try {
    await createChildWish({
      name: form.value.name.trim(),
      emoji: form.value.emoji || undefined,
      description: form.value.description || undefined,
      priority: form.value.priority,
    })
    showCreate.value = false
    form.value = { name: '', emoji: '', description: '', priority: 'medium' }
    await load()
  } catch {
    createError.value = '提交失败，请重试'
  } finally {
    creating.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.wishes-page {
  padding: 16px;
  background: #FFF9E6;
  min-height: 100vh;
  padding-bottom: 80px;
}
.stats-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #fff;
  border-radius: 12px;
  padding: 12px 16px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.balance { font-size: 18px; font-weight: 700; color: #f5a623; }
.wish-count { font-size: 13px; color: #999; }
.loading, .empty {
  text-align: center;
  margin-top: 60px;
  color: #999;
  font-size: 16px;
}
.section { margin-bottom: 20px; }
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #666;
  margin: 0 0 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.wish-card {
  display: flex;
  align-items: center;
  background: #fff;
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  gap: 12px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.wish-card.realized { opacity: 0.7; }
.wish-card.rejected { opacity: 0.6; }
.wish-top { display: flex; align-items: center; gap: 12px; width: 100%; }
.wish-emoji { font-size: 28px; flex-shrink: 0; }
.wish-info { flex: 1; }
.wish-name { font-size: 16px; font-weight: 600; color: #333; margin: 0 0 4px; }
.priority-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  display: inline-block;
}
.priority-badge.high { background: #ffe0e0; color: #c0392b; }
.priority-badge.medium { background: #fff3cd; color: #856404; }
.priority-badge.low { background: #e8f4fd; color: #1a6fa8; }
.status-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  display: inline-block;
}
.status-badge.pending { background: #fff3cd; color: #856404; }
.status-badge.redemption { background: #d4edda; color: #155724; }
.status-badge.realized { background: #d4edda; color: #155724; }
.status-badge.rejected { background: #f8d7da; color: #721c24; }
.rejection-reason { font-size: 12px; color: #999; margin: 4px 0 0; }

/* Savings jar */
.jar-wrap {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  width: 100%;
  padding-left: 40px;
}
.jar {
  width: 100%;
  height: 12px;
  background: #f0f0f0;
  border-radius: 6px;
  overflow: hidden;
  position: relative;
}
.jar-fill {
  position: absolute;
  top: 0;
  left: 0;
  height: 100%;
  border-radius: 6px;
  transition: width 0.6s ease;
}
.jar-fill.low { background: #74b9ff; }
.jar-fill.half { background: #fdcb6e; }
.jar-fill.full {
  background: linear-gradient(90deg, #f9ca24, #f0932b);
  animation: goldShimmer 1.5s ease-in-out infinite;
}
@keyframes goldShimmer {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}
.jar-pct { font-size: 12px; color: #666; white-space: nowrap; min-width: 32px; }
.jar-pending { font-size: 12px; color: #aaa; padding-left: 40px; width: 100%; }

.btn-redeem {
  width: 100%;
  background: linear-gradient(135deg, #f9ca24, #f0932b);
  color: #fff;
  border: none;
  border-radius: 20px;
  padding: 10px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  margin-top: 4px;
  animation: goldShimmer 1.5s ease-in-out infinite;
}
.btn-redeem:disabled { opacity: 0.5; cursor: not-allowed; animation: none; }

.btn-create {
  position: fixed;
  bottom: 80px;
  right: 20px;
  background: #f5a623;
  color: #fff;
  border: none;
  border-radius: 24px;
  padding: 12px 20px;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(245,166,35,0.4);
  z-index: 10;
}

/* Dialog */
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
.input {
  border: 1px solid #e0e0e0;
  border-radius: 10px;
  padding: 10px 14px;
  font-size: 15px;
  outline: none;
  width: 100%;
  box-sizing: border-box;
}
.textarea { min-height: 72px; resize: none; }
.priority-select { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.priority-select span { font-size: 14px; color: #666; }
.priority-btn {
  padding: 6px 14px;
  border: 1px solid #e0e0e0;
  border-radius: 16px;
  background: #f8f8f8;
  font-size: 13px;
  cursor: pointer;
}
.priority-btn.active { background: #f5a623; color: #fff; border-color: #f5a623; }
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
  background: #f5a623;
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  cursor: pointer;
}
.btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }
.error-msg { background: #f8d7da; color: #721c24; border-radius: 8px; padding: 10px 14px; font-size: 14px; }
</style>
