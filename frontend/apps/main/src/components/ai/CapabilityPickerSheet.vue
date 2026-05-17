<template>
  <van-popup
    v-model:show="visible"
    round
    position="bottom"
    :style="{ paddingBottom: 'env(safe-area-inset-bottom)' }"
  >
    <div class="cap-sheet">
      <div class="cap-sheet__header">
        <span class="cap-sheet__title">{{ t('aiConfig.selectCapabilities') }}</span>
        <van-icon name="cross" size="18" class="cap-sheet__close" @click="visible = false" />
      </div>

      <div class="cap-sheet__note">{{ t('aiConfig.capabilityNote') }}</div>

      <div class="cap-sheet__list">
        <button
          v-for="cap in capabilities"
          :key="cap.key"
          class="cap-item"
          :class="{ 'cap-item--active': modelValue.includes(cap.key), 'cap-item--disabled': cap.disabled }"
          :disabled="cap.disabled"
          @click="toggle(cap.key)"
        >
          <div class="cap-item__icon" :class="`cap-item__icon--${cap.key}`">
            <svg v-if="cap.key === 'text_generation'" width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="4" y="6" width="20" height="3" rx="1.5" fill="currentColor" />
              <rect x="4" y="12" width="16" height="3" rx="1.5" fill="currentColor" opacity="0.7" />
              <rect x="4" y="18" width="12" height="3" rx="1.5" fill="currentColor" opacity="0.4" />
            </svg>
            <svg v-else-if="cap.key === 'deep_thinking'" width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="14" cy="12" r="7" stroke="currentColor" stroke-width="2" />
              <path d="M10.5 12C10.5 10.067 12.067 8.5 14 8.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
              <circle cx="14" cy="12" r="2" fill="currentColor" />
              <rect x="11" y="20" width="6" height="2" rx="1" fill="currentColor" />
              <rect x="12.5" y="22" width="3" height="2" rx="1" fill="currentColor" />
            </svg>
            <svg v-else width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M4 14C4 14 7.5 7 14 7C20.5 7 24 14 24 14C24 14 20.5 21 14 21C7.5 21 4 14 4 14Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round" />
              <circle cx="14" cy="14" r="3.5" stroke="currentColor" stroke-width="2" />
              <circle cx="14" cy="14" r="1.5" fill="currentColor" />
            </svg>
          </div>
          <div class="cap-item__text">
            <span class="cap-item__label">{{ cap.label }}</span>
            <span class="cap-item__subtitle">{{ cap.subtitle }}</span>
          </div>
          <div class="cap-item__check">
            <svg v-if="modelValue.includes(cap.key)" width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="10" fill="currentColor" />
              <path d="M5.5 10.5L8.5 13.5L14.5 7" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <svg v-else width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="9" stroke="currentColor" stroke-width="1.5" />
            </svg>
          </div>
        </button>
      </div>

      <div class="cap-sheet__actions">
        <van-button block type="primary" @click="visible = false">
          {{ t('common.confirm') }}
        </van-button>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  show: boolean
  modelValue: string[]
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'update:modelValue': [value: string[]]
}>()

const visible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

interface Capability {
  key: string
  label: string
  subtitle: string
  disabled: boolean
}

const capabilities = computed<Capability[]>(() => [
  {
    key: 'text_generation',
    label: t('aiConfig.capabilityTextDesc'),
    subtitle: t('aiConfig.capabilityTextSubtitle'),
    disabled: props.modelValue.includes('deep_thinking'),
  },
  {
    key: 'deep_thinking',
    label: t('aiConfig.capabilityThinkingDesc'),
    subtitle: t('aiConfig.capabilityThinkingSubtitle'),
    disabled: false,
  },
  {
    key: 'vision_understanding',
    label: t('aiConfig.capabilityVisionDesc'),
    subtitle: t('aiConfig.capabilityVisionSubtitle'),
    disabled: false,
  },
])

function toggle(key: string) {
  const current = [...props.modelValue]
  const idx = current.indexOf(key)

  if (key === 'deep_thinking') {
    if (idx === -1) {
      // enabling thinking also enables text
      const next = [...new Set([...current, 'deep_thinking', 'text_generation'])]
      emit('update:modelValue', next)
    } else {
      emit('update:modelValue', current.filter((k) => k !== 'deep_thinking'))
    }
    return
  }

  if (key === 'text_generation' && current.includes('deep_thinking')) {
    // text_generation is locked when thinking is on
    return
  }

  if (idx === -1) {
    emit('update:modelValue', [...current, key])
  } else {
    emit('update:modelValue', current.filter((k) => k !== key))
  }
}
</script>

<style scoped>
.cap-sheet {
  padding: 20px 16px;
  padding-bottom: 8px;
}

.cap-sheet__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.cap-sheet__title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

.cap-sheet__close {
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
}

.cap-sheet__note {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 16px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
}

.cap-sheet__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

.cap-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1.5px solid var(--border-light);
  background: var(--bg-card);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  text-align: left;
  width: 100%;
}

.cap-item--active {
  border-color: var(--van-primary-color);
  background: color-mix(in srgb, var(--van-primary-color) 6%, var(--bg-card));
}

.cap-item--disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.cap-item__icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.cap-item__icon--text_generation {
  background: color-mix(in srgb, #4f8ef7 15%, transparent);
  color: #4f8ef7;
}

.cap-item__icon--deep_thinking {
  background: color-mix(in srgb, #9b59f7 15%, transparent);
  color: #9b59f7;
}

.cap-item__icon--vision_understanding {
  background: color-mix(in srgb, #2ec4b6 15%, transparent);
  color: #2ec4b6;
}

.cap-item__text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.cap-item__label {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  letter-spacing: -0.2px;
}

.cap-item__subtitle {
  font-size: 12px;
  color: var(--text-secondary);
}

.cap-item__check {
  flex-shrink: 0;
  color: var(--van-primary-color);
}

.cap-item:not(.cap-item--active) .cap-item__check {
  color: var(--border-light);
}

.cap-sheet__actions {
  padding-bottom: 8px;
}
</style>
