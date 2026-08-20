<template>
  <van-swipe-cell
    :disabled="!contract.is_active"
    class="rental-swipe"
    :left-width="0"
    :right-width="contract.is_active ? 140 : 0"
    stop-propagation
  >
    <div class="rental-card" :class="{ inactive: !contract.is_active }" @click="$emit('click')">
      <div class="card-header">
        <span class="role-badge" :class="contract.role">
          <van-icon :name="contract.role === 'landlord' ? 'arrow-down' : 'arrow-up'" />
          {{ contract.role === 'landlord' ? t('rental.roleLandlord') : t('rental.roleTenant') }}
        </span>
        <span v-if="contract.is_active" class="status active">{{ t('rental.active') }}</span>
        <span v-else class="status inactive">{{ t('rental.inactive') }}</span>
      </div>
      <div class="card-body">
        <div class="rent-amount">{{ formatConverted(contract.monthly_rent, contract.currency) }}</div>
        <div class="rent-label">{{ t('rental.monthlyRent') }}</div>
      </div>
      <div class="card-meta">
        <span v-if="contract.counterparty" class="meta-item">
          <van-icon name="user-o" />
          {{ contract.counterparty }}
        </span>
        <span class="meta-item">
          <van-icon name="calendar-o" />
          {{ contract.start_date }} ~ {{ contract.end_date || t('rental.openEnded') }}
        </span>
        <span v-if="Number(contract.deposit) > 0" class="meta-item">
          <van-icon name="cash-back-record" />
          {{ t('rental.deposit') }} {{ formatConverted(contract.deposit, contract.currency) }}
        </span>
      </div>
      <div v-if="contract.notes" class="card-notes">{{ contract.notes }}</div>
    </div>

    <!-- Swipe right actions: active contracts only -->
    <template v-if="contract.is_active" #right>
      <van-button
        square
        type="danger"
        class="swipe-action-btn"
        :text="t('rental.endContract')"
        @click.stop="$emit('end')"
      />
      <van-button
        square
        type="primary"
        class="swipe-action-btn"
        :text="t('rental.editContract')"
        @click.stop="$emit('edit')"
      />
    </template>
  </van-swipe-cell>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { RentalContract } from '@/types'
import { useCurrency } from '@/composables/useCurrency'

const { t } = useI18n()
const { formatConverted } = useCurrency()

defineProps<{
  contract: RentalContract
}>()

defineEmits<{
  click: []
  edit: []
  end: []
}>()
</script>

<style scoped>
.rental-swipe {
  touch-action: pan-y;
  border-radius: 12px;
  overflow: hidden;
}
.swipe-action-btn {
  height: 100%;
  min-width: 70px;
  font-size: 13px;
  font-weight: 500;
}
.rental-card {
  background: var(--card-bg);
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  cursor: pointer;
}
[data-theme='dark'] .rental-card {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.28);
}
.rental-card.inactive {
  opacity: 0.6;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.role-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
}
.role-badge.landlord {
  background: rgba(5, 150, 105, 0.12);
  color: #059669;
}
.role-badge.tenant {
  background: rgba(220, 38, 38, 0.1);
  color: #dc2626;
}
.status {
  font-size: 11px;
}
.status.active {
  color: #059669;
}
.status.inactive {
  color: var(--text-secondary, #999);
}
.card-body {
  display: flex;
  flex-direction: column;
  margin-bottom: 8px;
}
.rent-amount {
  font-size: 22px;
  font-weight: 600;
  color: var(--text-primary);
}
.rent-label {
  font-size: 12px;
  color: var(--text-secondary, #999);
}
.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary, #999);
}
.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.card-notes {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--separator, rgba(0, 0, 0, 0.06));
  font-size: 12px;
  color: var(--text-secondary, #999);
}
</style>
