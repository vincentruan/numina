<template>
  <div class="suggestion-wrap">
    <span class="suggestion-label">{{ t('wish.suggestion.title') }}</span>

    <div v-if="loading" class="suggestion-loading">
      <van-loading size="14" />
    </div>

    <div v-else-if="insufficient" class="suggestion-insufficient">
      {{ t('wish.suggestion.insufficient') }}
    </div>

    <template v-else>
      <div class="suggestion-chips">
        <button
          class="chip"
          type="button"
          @click="emit('select', rate!.suggested_7d)"
        >
          {{ t('wish.suggestion.days7') }} ({{ rate!.suggested_7d }}⭐)
        </button>
        <button
          class="chip"
          type="button"
          @click="emit('select', rate!.suggested_14d)"
        >
          {{ t('wish.suggestion.days14') }} ({{ rate!.suggested_14d }}⭐)
        </button>
        <button
          class="chip"
          type="button"
          @click="emit('select', rate!.suggested_30d)"
        >
          {{ t('wish.suggestion.days30') }} ({{ rate!.suggested_30d }}⭐)
        </button>
      </div>
      <span class="suggestion-basis">{{ t('wish.suggestion.basis') }}</span>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { getChildEarningRate, type ChildEarningRate } from '@/api/children'

const props = defineProps<{
  childId: string
}>()

const emit = defineEmits<{
  select: [value: number]
}>()

const { t } = useI18n()

const loading = ref(true)
const rate = ref<ChildEarningRate | null>(null)

const insufficient = computed(() => !rate.value || rate.value.data_days < 3)

onMounted(async () => {
  try {
    rate.value = await getChildEarningRate(props.childId)
  } catch {
    rate.value = null
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.suggestion-wrap {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.suggestion-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.suggestion-loading {
  display: flex;
  align-items: center;
  min-height: 32px;
}

.suggestion-insufficient {
  font-size: 12px;
  color: var(--text-tertiary);
  padding: 4px 0;
}

.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip {
  padding: 5px 10px;
  border: 1px solid var(--separator);
  border-radius: 4px;
  background: var(--bg-secondary);
  color: var(--van-primary-color);
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
  min-height: 44px;
  display: flex;
  align-items: center;
}

.chip:active {
  background: rgba(var(--theme-primary-rgb), 0.06);
}

.suggestion-basis {
  font-size: 11px;
  color: var(--text-tertiary);
}
</style>
