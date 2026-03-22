<template>
  <div class="asset-card" @click="$emit('click')">
    <div v-if="selectable" class="selection-overlay">
      <van-checkbox
        :model-value="selected"
        @click.stop="$emit('update:selected', !selected)"
      />
    </div>
    <div class="card-left">
      <div v-if="asset.image_url && !imageError" class="card-image">
        <img :src="imageUrl" :alt="asset.name" @error="onImageError" />
      </div>
      <div v-else class="card-icon" :style="{ background: asset.category?.color || '#1989fa' }">
        {{ asset.category?.icon || '📦' }}
      </div>
    </div>
    <div class="card-right">
      <div class="card-row-top">
        <span class="card-name">{{ asset.name }}</span>
        <van-tag :type="statusType" size="medium">{{ statusText }}</van-tag>
      </div>
      <div class="card-row-category">
        <span class="card-category-text">{{ asset.category?.name || '未分类' }}</span>
        <span v-if="daysUsed > 0" class="card-days">已使用 {{ daysUsed }} 天</span>
      </div>
      <div class="card-row-prices">
        <div class="price-item">
          <span class="price-label">购入</span>
          <span class="price-value">¥{{ formatPrice(asset.purchase_price) }}</span>
        </div>
        <div class="price-item">
          <span class="price-label">当前</span>
          <span class="price-value current">¥{{ formatPrice(asset.current_value) }}</span>
        </div>
      </div>
      <div class="card-row-bottom">
        <span v-if="asset.daily_cost != null && asset.daily_cost > 0" class="card-daily-cost">
          ⏱ 日均 ¥{{ asset.daily_cost.toFixed(2) }}
        </span>
        <span v-else class="card-daily-cost-placeholder" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Asset } from '@/types'

const props = defineProps<{
  asset: Asset
  selectable?: boolean
  selected?: boolean
}>()

defineEmits<{
  click: []
  'update:selected': [value: boolean]
}>()

const imageError = ref(false)

const imageUrl = computed(() => {
  if (!props.asset.image_url) return ''
  if (props.asset.image_url.startsWith('/')) {
    return `/api/v1${props.asset.image_url}`
  }
  return props.asset.image_url
})

function onImageError() {
  imageError.value = true
}

const daysUsed = computed(() => {
  if (!props.asset.purchase_date) return 0
  const purchase = new Date(props.asset.purchase_date)
  const now = new Date()
  const diff = Math.floor((now.getTime() - purchase.getTime()) / (1000 * 60 * 60 * 24))
  return diff > 0 ? diff : 0
})

function formatPrice(price: number | null | undefined): string {
  if (price == null) return '-'
  if (price >= 10000) {
    return `${(price / 10000).toFixed(1)}万`
  }
  return price.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

const statusMap: Record<string, { text: string; type: 'primary' | 'success' | 'warning' | 'danger' | 'default' }> = {
  in_use: { text: '服役中', type: 'success' },
  idle: { text: '闲置', type: 'warning' },
  sold: { text: '已出售', type: 'default' },
  retired: { text: '已退役', type: 'danger' }
}

const statusText = computed(() => statusMap[props.asset.status]?.text || props.asset.status)
const statusType = computed(() => statusMap[props.asset.status]?.type || 'default')
</script>

<style scoped>
.asset-card {
  position: relative;
  display: flex;
  background: #fff;
  border-radius: 12px;
  padding: 12px;
  margin-bottom: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  transition: transform 0.15s;
}
.asset-card:active {
  transform: scale(0.98);
}
.selection-overlay {
  position: absolute;
  top: 8px;
  left: 8px;
  z-index: 10;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 50%;
  padding: 2px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}
.selection-overlay :deep(.van-checkbox) {
  display: flex;
}
.card-left {
  flex-shrink: 0;
  margin-right: 12px;
}
.card-image {
  width: 88px;
  height: 88px;
  border-radius: 10px;
  overflow: hidden;
}
.card-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.card-icon {
  width: 88px;
  height: 88px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 36px;
}
.card-right {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  min-width: 0;
  gap: 3px;
}
.card-row-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-name {
  font-size: 15px;
  font-weight: 600;
  color: #1a1a1a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 60%;
}
.card-row-category {
  display: flex;
  align-items: center;
  gap: 6px;
}
.card-category-text {
  font-size: 12px;
  color: #999;
}
.card-days {
  font-size: 10px;
  color: #1989fa;
  background: #ecf5ff;
  padding: 1px 6px;
  border-radius: 8px;
  line-height: 1.4;
}
.card-row-prices {
  display: flex;
  gap: 14px;
}
.price-item {
  display: flex;
  align-items: baseline;
  gap: 3px;
}
.price-label {
  font-size: 11px;
  color: #bbb;
}
.price-value {
  font-size: 13px;
  color: #666;
  font-weight: 500;
}
.price-value.current {
  color: #1a1a1a;
  font-weight: 600;
}
.card-row-bottom {
  display: flex;
  align-items: center;
}
.card-daily-cost {
  font-size: 12px;
  color: #ff976a;
  font-weight: 500;
}
</style>
