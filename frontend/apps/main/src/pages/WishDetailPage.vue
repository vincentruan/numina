<template>
  <div class="wish-detail-page">
    <PageHeader title="心愿详情" />

    <template v-if="wish">
      <!-- Hero Card: Pastel Cloud Gradient -->
      <div class="hero-card" :class="wish.status">
        <!-- Decorative blob (handled via ::before in CSS) -->

        <div class="hero-top">
          <!-- Status icon -->
          <div class="hero-status-icon">
            <van-icon v-if="wish.status === 'realized'" name="success" size="28" />
            <van-icon v-else-if="wish.status === 'cancelled'" name="cross" size="28" />
            <van-icon v-else name="star" size="28" />
          </div>
          <div class="hero-info">
            <div class="hero-name">{{ wish.name }}</div>
            <div class="hero-category">
              <template v-if="wish.category">{{ wish.category.icon }} {{ wish.category.name }}</template>
              <template v-else>未分类</template>
            </div>
          </div>
          <!-- Status badge -->
          <van-tag :type="statusType" size="medium" class="hero-status-tag">{{ statusText }}</van-tag>
        </div>

        <!-- Stats row -->
        <div class="hero-values">
          <div class="hero-value-item">
            <div class="hero-value-label">预期价格</div>
            <div class="hero-value-num">
              <span v-if="wish.expected_price">¥{{ wish.expected_price.toLocaleString() }}</span>
              <span v-else class="hero-value-unset">未设置</span>
            </div>
          </div>
          <div class="hero-value-item">
            <div class="hero-value-label">优先级</div>
            <div class="hero-value-num">{{ priorityText }}</div>
          </div>
          <div class="hero-value-item">
            <div class="hero-value-label">状态</div>
            <div class="hero-value-num">{{ statusText }}</div>
          </div>
        </div>

        <div v-if="wish.realized_asset_id" class="hero-realized-info">已转化为资产</div>

        <div v-if="wish.description" class="hero-description">{{ wish.description }}</div>
      </div>

      <!-- Detail Info -->
      <van-cell-group inset title="详细信息">
        <van-cell title="状态" :value="statusText">
          <template #value>
            <van-tag :type="statusType">{{ statusText }}</van-tag>
          </template>
        </van-cell>
        <van-cell title="预期价格">
          <template #value>
            <span v-if="wish.expected_price">¥{{ wish.expected_price.toLocaleString() }}</span>
            <span v-else class="unset">未设置</span>
          </template>
        </van-cell>
        <van-cell title="优先级" :value="priorityText" />
        <van-cell title="分类" :value="wish.category?.name || '未分类'" />
        <van-cell title="创建时间" :value="formatDate(wish.created_at)" />
        <van-cell title="更新时间" :value="formatDate(wish.updated_at)" />
      </van-cell-group>

      <!-- Notes -->
      <van-cell-group v-if="wish.description" inset title="备注">
        <van-cell :title="wish.description" />
      </van-cell-group>

      <!-- Actions -->
      <div class="actions">
        <template v-if="wish.status === 'pending'">
          <van-button v-if="wish.converts_to_asset" block type="primary" @click="showRealizeDialog = true">
            转化为资产
          </van-button>
          <van-button block type="default" plain @click="$router.push(`/wishes/${wish.id}/edit`)">
            编辑
          </van-button>
          <van-button block type="warning" plain @click="onCancel">
            取消心愿
          </van-button>
        </template>
        <template v-else-if="wish.status === 'cancelled'">
          <van-button block type="success" plain @click="onReactivate">
            重新激活
          </van-button>
          <van-button block type="primary" plain @click="$router.push(`/wishes/${wish.id}/edit`)">
            编辑
          </van-button>
        </template>
        <template v-else>
          <van-button block type="primary" plain @click="$router.push(`/wishes/${wish.id}/edit`)">
            编辑
          </van-button>
        </template>
        <van-button block type="danger" plain :loading="deleting" class="delete-btn" @click="onDelete">
          删除
        </van-button>
      </div>

      <!-- Realize Dialog -->
      <van-popup v-model:show="showRealizeDialog" round position="bottom" :style="{ height: '60%' }">
        <div class="realize-dialog">
          <div class="dialog-title">转化为资产</div>
          <van-form @submit="onRealize">
            <van-cell-group inset>
              <van-field
                v-model="realizeForm.purchase_price"
                name="purchase_price"
                label="购入价格"
                type="number"
                inputmode="decimal"
                placeholder="请输入购入价格"
                :rules="[{ required: true, message: '请输入购入价格' }]"
              />
              <van-field
                v-model="realizeForm.purchase_date"
                name="purchase_date"
                label="购入日期"
                placeholder="点击选择"
                readonly
                :rules="[{ required: true, message: '请选择购入日期' }]"
                @click="showDatePicker = true"
              />
              <van-field
                v-model="selectedCategoryName"
                name="category"
                label="分类"
                placeholder="点击选择"
                readonly
                @click="showCategoryPicker = true"
              />
            </van-cell-group>
            <div style="margin: 16px">
              <van-button round block type="primary" native-type="submit" :loading="realizing">
                确认转化
              </van-button>
            </div>
          </van-form>
        </div>
      </van-popup>

      <!-- Date Picker -->
      <van-calendar v-model:show="showDatePicker" @confirm="onDateConfirm" />

      <!-- Category Picker -->
      <van-popup v-model:show="showCategoryPicker" round position="bottom">
        <van-picker
          :columns="categoryColumns"
          @confirm="onCategoryConfirm"
          @cancel="showCategoryPicker = false"
        />
      </van-popup>
    </template>

    <van-loading v-else class="page-loading" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useWishStore } from '@/stores/wish'
import { getCategories } from '@/api/categories'
import type { Category } from '@/types'
import { realizeWish } from '@/api/wishes'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()

const route = useRoute()
const router = useRouter()
const wishStore = useWishStore()
const deleting = ref(false)
const acting = ref(false)

// Realize dialog
const showRealizeDialog = ref(false)
const realizing = ref(false)
const showDatePicker = ref(false)
const showCategoryPicker = ref(false)
const realizeForm = ref({
  purchase_price: '',
  purchase_date: '',
  category_id: ''
})
const categories = ref<Category[]>([])

const wish = computed(() => wishStore.currentWish)

const statusMap: Record<string, { text: string; type: 'primary' | 'success' | 'warning' | 'danger' | 'default' }> = {
  pending: { text: '待实现', type: 'primary' },
  realized: { text: '已实现', type: 'success' },
  cancelled: { text: '已取消', type: 'default' }
}

const statusText = computed(() => statusMap[wish.value?.status || '']?.text || '')
const statusType = computed(() => statusMap[wish.value?.status || '']?.type || 'default')

const priorityMap: Record<string, string> = {
  low: '低',
  medium: '中',
  high: '高'
}
const priorityText = computed(() => priorityMap[wish.value?.priority || 'medium'] || '中')

const categoryColumns = computed(() => {
  return categories.value.map(c => ({ text: `${c.icon} ${c.name}`, value: c.id }))
})

const selectedCategoryName = computed(() => {
  if (!realizeForm.value.category_id) return ''
  const cat = categories.value.find(c => c.id === realizeForm.value.category_id)
  return cat ? `${cat.icon} ${cat.name}` : ''
})

function formatDate(dateStr: string) {
  return dateStr.slice(0, 10)
}

function onDateConfirm(date: Date) {
  realizeForm.value.purchase_date = date.toISOString().slice(0, 10)
  showDatePicker.value = false
}

function onCategoryConfirm({ selectedOptions }: { selectedOptions: Array<{ text: string; value: string }> }) {
  realizeForm.value.category_id = selectedOptions[0].value
  showCategoryPicker.value = false
}

async function onRealize() {
  if (!wish.value) return
  realizing.value = true
  try {
    const payload = {
      purchase_price: parseFloat(realizeForm.value.purchase_price),
      purchase_date: realizeForm.value.purchase_date,
      category_id: realizeForm.value.category_id || undefined
    }
    const res = await realizeWish(wish.value.id, payload)
    showToast(t('toast.assetConverted'))
    showRealizeDialog.value = false
    router.push(`/assets/${res.data.id}`)
  } finally {
    realizing.value = false
  }
}

async function onCancel() {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmCancel') })
    acting.value = true
    await wishStore.updateWish(wish.value!.id, { status: 'cancelled' })
    showToast(t('toast.wishCancelled'))
  } catch {
    // cancelled
  } finally {
    acting.value = false
  }
}

async function onReactivate() {
  acting.value = true
  try {
    await wishStore.updateWish(wish.value!.id, { status: 'pending' })
    showToast(t('toast.wishReactivated'))
  } finally {
    acting.value = false
  }
}

async function onDelete() {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('toast.confirmDelete', { name: wish.value?.name }) })
    deleting.value = true
    await wishStore.deleteWish(wish.value!.id)
    showToast(t('toast.deleteSuccess'))
    router.back()
  } catch {
    // cancelled
  } finally {
    deleting.value = false
  }
}

onMounted(async () => {
  const id = route.params.id as string
  await wishStore.fetchWish(id)

  // Pre-fill form
  if (wish.value?.expected_price) {
    realizeForm.value.purchase_price = String(wish.value.expected_price)
  }
  if (wish.value?.category_id) {
    realizeForm.value.category_id = wish.value.category_id
  }

  // Load categories for picker
  const catRes = await getCategories()
  categories.value = catRes.data
})
</script>

<style scoped>
.wish-detail-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}

/* ── Hero Card: Pastel Cloud Gradient (light mode) ── */
.hero-card {
  background:
    linear-gradient(135deg,
      rgba(239, 44, 193, 0.10) 0%,
      rgba(189, 187, 255, 0.18) 45%,
      rgba(160, 195, 255, 0.14) 100%),
    #ffffff;
  padding: 20px 16px 16px;
  color: #000000;
  position: relative;
  overflow: hidden;
}

/* Decorative soft blob */
.hero-card::before {
  content: '';
  position: absolute;
  top: -40px;
  right: -30px;
  width: 180px;
  height: 180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(189, 187, 255, 0.22) 0%, transparent 70%);
  pointer-events: none;
}

/* Dark mode */
[data-theme='dark'] .hero-card {
  background:
    linear-gradient(135deg,
      rgba(189, 187, 255, 0.08) 0%,
      rgba(189, 187, 255, 0.04) 50%,
      transparent 100%),
    #010120;
  color: #ffffff;
}
[data-theme='dark'] .hero-card::before {
  background: radial-gradient(circle, rgba(189, 187, 255, 0.10) 0%, transparent 70%);
}

/* Realized: soft green tint over gradient base */
.hero-card.realized {
  background:
    linear-gradient(135deg,
      rgba(5, 150, 105, 0.10) 0%,
      rgba(189, 187, 255, 0.12) 50%,
      rgba(160, 195, 255, 0.10) 100%),
    #ffffff;
}
[data-theme='dark'] .hero-card.realized {
  background:
    linear-gradient(135deg,
      rgba(5, 150, 105, 0.12) 0%,
      rgba(189, 187, 255, 0.06) 100%),
    #010120;
}

/* Cancelled: muted overlay */
.hero-card.cancelled {
  background:
    linear-gradient(135deg,
      rgba(0, 0, 0, 0.04) 0%,
      rgba(0, 0, 0, 0.02) 100%),
    #f5f5f5;
  color: rgba(0, 0, 0, 0.55);
}
[data-theme='dark'] .hero-card.cancelled {
  background:
    linear-gradient(135deg,
      rgba(255, 255, 255, 0.03) 0%,
      rgba(255, 255, 255, 0.01) 100%),
    #0d0d1a;
  color: rgba(255, 255, 255, 0.50);
}

.hero-top {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-bottom: 16px;
  position: relative;
}

/* Status icon container: glass badge */
.hero-status-icon {
  width: 52px;
  height: 52px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: rgba(0, 0, 0, 0.06);
  border: 1px solid rgba(0, 0, 0, 0.08);
  color: rgba(0, 0, 0, 0.65);
}
[data-theme='dark'] .hero-status-icon {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.12);
  color: rgba(255, 255, 255, 0.75);
}
.hero-card.realized .hero-status-icon {
  background: rgba(5, 150, 105, 0.10);
  border-color: rgba(5, 150, 105, 0.20);
  color: #059669;
}
[data-theme='dark'] .hero-card.realized .hero-status-icon {
  color: #6ee7a0;
}

.hero-info {
  flex: 1;
  min-width: 0;
}

/* Wish name: display-level, tight negative tracking */
.hero-name {
  font-size: clamp(18px, 5vw, 22px);
  font-weight: 500;
  letter-spacing: -0.22px;
  line-height: 1.15;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #000000;
}
[data-theme='dark'] .hero-name {
  color: #ffffff;
}
.hero-card.cancelled .hero-name {
  color: rgba(0, 0, 0, 0.50);
}
[data-theme='dark'] .hero-card.cancelled .hero-name {
  color: rgba(255, 255, 255, 0.45);
}

/* Mono label for category */
.hero-category {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.45);
  font-family: 'Georgia', monospace;
}
[data-theme='dark'] .hero-category {
  color: rgba(255, 255, 255, 0.45);
}

.hero-status-tag {
  flex-shrink: 0;
}

/* Stats row: glass container, 8px radius, dark-blue-tinted shadow */
.hero-values {
  display: flex;
  align-items: flex-start;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  padding: 12px 0;
  margin-bottom: 8px;
  box-shadow: rgba(1, 1, 32, 0.08) 0px 2px 8px;
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
}
[data-theme='dark'] .hero-values {
  background: rgba(255, 255, 255, 0.06);
  border-color: rgba(255, 255, 255, 0.12);
  box-shadow: rgba(1, 1, 32, 0.40) 0px 2px 8px;
}

.hero-value-item {
  flex: 1;
  text-align: center;
  border-right: 1px solid rgba(0, 0, 0, 0.08);
}
[data-theme='dark'] .hero-value-item {
  border-right-color: rgba(255, 255, 255, 0.12);
}
.hero-value-item:last-child {
  border-right: none;
}

/* Mono label for value headers */
.hero-value-label {
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.055px;
  text-transform: uppercase;
  color: rgba(0, 0, 0, 0.40);
  font-family: 'Georgia', monospace;
  margin-bottom: 4px;
}
[data-theme='dark'] .hero-value-label {
  color: rgba(255, 255, 255, 0.40);
}

.hero-value-num {
  font-size: 16px;
  font-weight: 500;
  letter-spacing: -0.16px;
  color: #000000;
}
[data-theme='dark'] .hero-value-num {
  color: #ffffff;
}

.hero-value-unset {
  font-size: 13px;
  color: rgba(0, 0, 0, 0.35);
}
[data-theme='dark'] .hero-value-unset {
  color: rgba(255, 255, 255, 0.30);
}

.hero-realized-info {
  font-size: 12px;
  font-weight: 500;
  color: #059669;
  text-align: center;
  margin-bottom: 4px;
}
[data-theme='dark'] .hero-realized-info {
  color: #6ee7a0;
}

.hero-description {
  font-size: 14px;
  color: rgba(0, 0, 0, 0.55);
  line-height: 1.5;
  padding-top: 8px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  margin-top: 4px;
}
[data-theme='dark'] .hero-description {
  color: rgba(255, 255, 255, 0.50);
  border-top-color: rgba(255, 255, 255, 0.10);
}

.actions {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.delete-btn {
  margin-top: 4px;
}

.page-loading {
  display: flex;
  justify-content: center;
  padding-top: 40vh;
}

.realize-dialog {
  padding: 16px;
}

.dialog-title {
  font-size: 16px;
  font-weight: 500;
  letter-spacing: -0.16px;
  text-align: center;
  margin-bottom: 16px;
  color: var(--text-primary);
}
</style>