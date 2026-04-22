<template>
  <div class="wish-detail-page">
    <PageHeader title="心愿详情" />

    <template v-if="wish">
      <!-- Status Banner -->
      <div class="status-banner" :class="wish.status">
        <div class="status-icon">
          <van-icon v-if="wish.status === 'realized'" name="success" size="32" />
          <van-icon v-else-if="wish.status === 'cancelled'" name="cross" size="32" />
          <van-icon v-else name="star" size="32" />
        </div>
        <div class="status-text">{{ statusText }}</div>
        <div v-if="wish.realized_asset_id" class="realized-info">
          已转化为资产
        </div>
      </div>

      <!-- Main Card -->
      <div class="main-card">
        <div class="wish-header">
          <div class="wish-name">{{ wish.name }}</div>
          <van-tag v-if="wish.category" type="primary" size="medium">
            {{ wish.category.icon }} {{ wish.category.name }}
          </van-tag>
        </div>

        <div class="wish-meta">
          <div class="meta-item">
            <van-icon name="gold-coin-o" />
            <span v-if="wish.expected_price">¥{{ wish.expected_price.toLocaleString() }}</span>
            <span v-else class="unset">未设置</span>
          </div>
          <div class="meta-item">
            <van-icon name="clock-o" />
            <span>优先级：{{ priorityText }}</span>
          </div>
        </div>

        <div v-if="wish.description" class="wish-description">
          {{ wish.description }}
        </div>
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
          <van-button block type="primary" @click="showRealizeDialog = true">
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
import { useAssetStore } from '@/stores/asset'
import { getCategories } from '@/api/categories'
import type { Category } from '@/types'
import { realizeWish } from '@/api/wishes'
import PageHeader from '@/components/common/PageHeader.vue'

const { t } = useI18n()

const route = useRoute()
const router = useRouter()
const wishStore = useWishStore()
const assetStore = useAssetStore()
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
    await showConfirmDialog({ title: '确认取消', message: '确定要取消这个心愿吗？' })
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
    await showConfirmDialog({ title: '确认删除', message: `确定要删除「${wish.value?.name}」吗？` })
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
.status-banner {
  padding: 24px 16px;
  text-align: center;
  color: #fff;
}
.status-banner.pending {
  background: linear-gradient(135deg, #1989fa 0%, #1976d2 100%);
}
.status-banner.realized {
  background: linear-gradient(135deg, #07c160 0%, #06ad56 100%);
}
.status-banner.cancelled {
  background: linear-gradient(135deg, #969799 0%, #7d7e80 100%);
}
.status-icon {
  margin-bottom: 8px;
}
.status-text {
  font-size: 18px;
  font-weight: 600;
}
.realized-info {
  font-size: 13px;
  opacity: 0.85;
  margin-top: 4px;
}
.main-card {
  background: var(--card-bg);
  margin: -16px 12px 12px;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

[data-theme='dark'] .main-card {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.4);
}

.wish-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.wish-name {
  font-size: 18px;
  font-weight: 600;
  flex: 1;
  margin-right: 8px;
  color: var(--text-primary);
}
.wish-meta {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: var(--text-secondary);
}
.meta-item .van-icon {
  color: var(--text-tertiary);
}
.unset {
  color: var(--text-tertiary);
}
.wish-description {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.5;
  padding-top: 8px;
  border-top: 1px solid var(--separator);
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
  font-weight: 600;
  text-align: center;
  margin-bottom: 16px;
  color: var(--text-primary);
}
</style>