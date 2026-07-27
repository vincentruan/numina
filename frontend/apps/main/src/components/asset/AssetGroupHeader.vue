<template>
  <div
    class="asset-group-header"
    role="button"
    tabindex="0"
    :aria-expanded="!collapsed"
    :aria-label="ariaLabel"
    @click="$emit('toggle')"
    @keydown.enter="$emit('toggle')"
    @keydown.space.prevent="$emit('toggle')"
  >
    <div class="group-header-left">
      <div
        class="group-icon"
        :style="{ background: iconBackground }"
      >
        <SvgIcon :name="iconName" class="group-icon-svg" />
      </div>
      <span class="group-name">{{ displayName }}</span>
      <span class="group-count">({{ count }})</span>
      <span v-if="selectionMode" class="group-selected">
        {{ t('asset.groupSelected', { count: selectedCount }) }}
      </span>
    </div>
    <div class="group-header-right">
      <span class="group-subtotal">{{ currency.format(subtotal) }}</span>
      <van-icon
        name="arrow-down"
        size="14"
        class="group-arrow"
        :class="{ 'group-arrow--collapsed': collapsed }"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { Category } from '@/types'
import { useCurrency } from '@/composables/useCurrency'
import { getIconId } from '@/utils/icon'
import SvgIcon from '@/components/SvgIcon.vue'

const props = withDefaults(defineProps<{
  category?: Category
  count: number
  subtotal: number
  collapsed: boolean
  selectionMode?: boolean
  selectedCount?: number
}>(), {
  category: undefined,
  selectionMode: false,
  selectedCount: 0,
})

defineEmits<{
  toggle: []
}>()

const { t } = useI18n()
const currency = useCurrency()

const displayName = computed(() =>
  props.category?.name ?? t('asset.uncategorized'),
)

const iconName = computed(() =>
  props.category?.icon ? getIconId(props.category.icon) : 'apps-o',
)

const iconBackground = computed(() =>
  props.category?.color ?? 'var(--color-text-tertiary)',
)

const ariaLabel = computed(() =>
  t('asset.ariaToggleGroup', { name: displayName.value }),
)
</script>

<style scoped>
.asset-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 44px;
  padding: 0 14px;
  background: var(--bg-secondary);
  cursor: pointer;
  user-select: none;
  border-radius: 8px 8px 0 0;
  transition: background 0.15s ease;
}

.asset-group-header:active {
  background: var(--bg-tertiary);
}

.asset-group-header:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.group-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
}

.group-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  flex-shrink: 0;
}

.group-icon-svg {
  width: 16px;
  height: 16px;
  fill: white;
  color: white;
}

.group-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.group-count {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.group-selected {
  font-size: 11px;
  color: var(--color-primary);
  font-weight: 500;
  flex-shrink: 0;
}

[data-theme='dark'] .group-selected {
  color: var(--color-lavender);
}

.group-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.group-subtotal {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.group-arrow {
  transition: transform 200ms ease;
  color: var(--text-tertiary);
}

.group-arrow--collapsed {
  transform: rotate(-90deg);
}

@media (prefers-reduced-motion: reduce) {
  .group-arrow {
    transition: none;
  }
}
</style>
