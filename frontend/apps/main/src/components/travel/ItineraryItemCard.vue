<template>
  <div class="timeline-card" :class="`timeline-card--${item.type}`" role="listitem" :aria-label="cardAriaLabel">
    <van-swipe-cell>
      <div class="card-body" @click="$emit('edit', item)">
        <div class="card-icon">
          <van-icon :name="typeIcon" size="22" />
        </div>
        <div class="card-content">
          <div class="card-header">
            <span class="card-type">{{ typeName }}</span>
            <span v-if="item.start_time" class="card-time">{{ item.start_time }}</span>
            <span v-if="item.end_time" class="card-time-sep">–</span>
            <span v-if="item.end_time" class="card-time">{{ item.end_time }}</span>
          </div>
          <div v-if="item.location" class="card-location">
            <van-icon name="location-o" size="12" />
            {{ item.location }}
          </div>
          <div v-if="item.description" class="card-desc">{{ item.description }}</div>
        </div>
        <div class="card-right">
          <div v-if="item.cost_amount" class="card-cost">
            {{ formatCost(item.cost_amount, item.cost_currency || 'CNY') }}
          </div>
          <div v-if="item.cost_amount" class="card-linked" :title="t('travel.itinerary.linkedExpense')">
            <van-icon name="link-o" size="12" />
          </div>
        </div>
      </div>
      <template #left>
        <van-button
          square
          type="primary"
          class="action-button"
          @click.stop="$emit('edit', item)"
        >
          <van-icon name="edit" />
        </van-button>
      </template>
      <template #right>
        <van-button
          square
          type="danger"
          class="action-button"
          @click.stop="$emit('delete', item)"
        >
          <van-icon name="delete-o" />
        </van-button>
      </template>
    </van-swipe-cell>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import type { ItineraryItem, ItineraryItemTypeDef } from '@/types/travel'

const props = defineProps<{
  item: ItineraryItem
  customTypes?: ItineraryItemTypeDef[]
}>()

defineEmits<{
  edit: [item: ItineraryItem]
  delete: [item: ItineraryItem]
}>()

const { t } = useI18n()
const { formatIn } = useCurrency()

const ICON_MAP: Record<string, string> = {
  accommodation: 'hotel-o',
  dining: 'restaurant-o',
  transport: 'car-o',
  activity: 'fire-o',
  custom: 'star-o',
}

const typeIcon = computed(() => {
  if (props.item.type === 'custom' && props.item.custom_type_id && props.customTypes) {
    const ct = props.customTypes.find(c => c.id === props.item.custom_type_id)
    if (ct) return ct.icon
  }
  return ICON_MAP[props.item.type] || 'star-o'
})

const typeName = computed(() => {
  if (props.item.type === 'custom' && props.item.custom_type_id && props.customTypes) {
    const ct = props.customTypes.find(c => c.id === props.item.custom_type_id)
    if (ct) return ct.name
  }
  return t(`travel.itinerary.types.${props.item.type}`)
})

const cardAriaLabel = computed(() => {
  const parts = [typeName.value]
  if (props.item.start_time) parts.push(props.item.start_time)
  if (props.item.location) parts.push(props.item.location)
  return parts.join(', ')
})

function formatCost(amount: string, currency: string): string {
  return formatIn(amount, currency)
}
</script>

<style scoped>
.timeline-card {
  margin: 8px 12px;
  border-radius: 12px;
  background: var(--card-bg);
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
}

.card-body {
  display: flex;
  align-items: flex-start;
  padding: 12px;
  gap: 10px;
  cursor: pointer;
  min-height: 44px;
}

.card-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.timeline-card--accommodation .card-icon {
  background: rgba(100, 149, 237, 0.15);
  color: #6495ed;
}

.timeline-card--dining .card-icon {
  background: rgba(255, 140, 0, 0.15);
  color: #ff8c00;
}

.timeline-card--transport .card-icon {
  background: rgba(60, 179, 113, 0.15);
  color: #3cb371;
}

.timeline-card--activity .card-icon {
  background: rgba(220, 80, 80, 0.15);
  color: #dc5050;
}

.timeline-card--custom .card-icon {
  background: rgba(147, 112, 219, 0.15);
  color: #9370db;
}

.card-content {
  flex: 1;
  min-width: 0;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.card-type {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.card-time {
  font-size: 13px;
  color: var(--text-secondary);
}

.card-time-sep {
  font-size: 13px;
  color: var(--text-secondary);
}

.card-location {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  flex-shrink: 0;
}

.card-cost {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.card-linked {
  color: var(--text-secondary);
  opacity: 0.6;
}

.action-button {
  height: 100%;
  min-width: 44px;
}
</style>
