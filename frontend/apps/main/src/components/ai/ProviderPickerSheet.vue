<template>
  <van-popup
    v-model:show="visible"
    round
    position="bottom"
    :style="{ paddingBottom: 'env(safe-area-inset-bottom)' }"
  >
    <div class="provider-sheet">
      <div class="provider-sheet__header">
        <span class="provider-sheet__title">{{ t('aiConfig.aiProvider') }}</span>
        <van-icon name="cross" size="18" class="provider-sheet__close" @click="visible = false" />
      </div>

      <div class="provider-sheet__list">
        <button
          v-for="provider in providers"
          :key="provider.value"
          class="provider-item"
          :class="{ 'provider-item--active': modelValue === provider.value }"
          @click="select(provider.value)"
        >
          <div class="provider-item__icon" :class="`provider-item__icon--${provider.value}`">
            <!-- Anthropic logo -->
            <svg v-if="provider.value === 'anthropic'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M13.827 3.52h3.603L24 20h-3.603l-6.57-16.48zm-3.654 0H6.57L0 20h3.603l1.378-3.504h6.875L13.234 20h3.603l-6.664-16.48zm-1.32 9.99 2.244-5.716 2.244 5.717H8.853z" fill="currentColor" />
            </svg>
            <!-- OpenAI Responses API logo (green, with star badge) -->
            <svg v-else-if="provider.value === 'openai'" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365 2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z" fill="currentColor" />
            </svg>
            <!-- OpenAI Compatible logo (blue-gray, with plug badge) -->
            <svg v-else viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.997-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.141-.081 4.779-2.758a.795.795 0 0 0 .392-.681v-6.737l2.02 1.168a.071.071 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.494 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .78 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.676l5.815 3.355-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855-5.833-3.387L15.119 7.2a.076.076 0 0 1 .071 0l4.83 2.791a4.494 4.494 0 0 1-.676 8.105v-5.678a.79.79 0 0 0-.407-.667zm2.01-3.023-.141-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.061l4.83-2.787a4.5 4.5 0 0 1 6.68 4.66zm-12.64 4.135-2.02-1.164a.08.08 0 0 1-.038-.057V6.075a4.5 4.5 0 0 1 7.375-3.453l-.142.08L8.704 5.46a.795.795 0 0 0-.393.681zm1.097-2.365 2.602-1.5 2.607 1.5v2.999l-2.597 1.5-2.607-1.5z" fill="currentColor" opacity="0.85" />
              <!-- Compatibility indicator: plug icon overlay -->
              <circle cx="18" cy="6" r="4" fill="currentColor" opacity="0.15" />
              <path d="M17 5v2M18 4v4M19 5v2" stroke="currentColor" stroke-width="1" stroke-linecap="round" opacity="0.6" />
            </svg>
          </div>
          <div class="provider-item__text">
            <span class="provider-item__label">{{ provider.label }}</span>
            <span class="provider-item__subtitle">{{ provider.subtitle }}</span>
          </div>
          <div class="provider-item__check">
            <svg v-if="modelValue === provider.value" width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="10" fill="currentColor" />
              <path d="M5.5 10.5L8.5 13.5L14.5 7" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <svg v-else width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="9" stroke="currentColor" stroke-width="1.5" />
            </svg>
          </div>
        </button>
      </div>

      <div class="provider-sheet__actions">
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
  modelValue: string
}>()

const emit = defineEmits<{
  'update:show': [value: boolean]
  'update:modelValue': [value: string]
}>()

const visible = computed({
  get: () => props.show,
  set: (v) => emit('update:show', v),
})

interface ProviderOption {
  value: string
  label: string
  subtitle: string
}

const providers = computed<ProviderOption[]>(() => [
  {
    value: 'anthropic',
    label: t('aiConfig.providerAnthropic'),
    subtitle: '/v1/messages endpoint',
  },
  {
    value: 'openai',
    label: t('aiConfig.providerOpenAI'),
    subtitle: '/v1/responses endpoint',
  },
  {
    value: 'openai_compatible',
    label: t('aiConfig.providerOpenAICompatible'),
    subtitle: '/v1/chat/completions endpoint',
  },
])

function select(value: string) {
  emit('update:modelValue', value)
}
</script>

<style scoped>
.provider-sheet {
  padding: 20px 16px;
  padding-bottom: 8px;
}

.provider-sheet__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.provider-sheet__title {
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

.provider-sheet__close {
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
}

.provider-sheet__list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}

.provider-item {
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

.provider-item--active {
  border-color: var(--van-primary-color);
  background: color-mix(in srgb, var(--van-primary-color) 6%, var(--bg-card));
}

.provider-item__icon {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.provider-item__icon svg {
  width: 26px;
  height: 26px;
}

/* Anthropic: orange/amber */
.provider-item__icon--anthropic {
  background: color-mix(in srgb, #d97706 12%, transparent);
  color: #d97706;
}

[data-theme='dark'] .provider-item__icon--anthropic {
  background: rgba(217, 119, 6, 0.15);
  color: #fbbf24;
}

/* OpenAI (Responses API): green */
.provider-item__icon--openai {
  background: color-mix(in srgb, #10a37f 12%, transparent);
  color: #10a37f;
}

[data-theme='dark'] .provider-item__icon--openai {
  background: rgba(16, 163, 127, 0.15);
  color: #34d399;
}

/* OpenAI Compatible: blue-gray */
.provider-item__icon--openai_compatible {
  background: color-mix(in srgb, #64748b 12%, transparent);
  color: #64748b;
}

[data-theme='dark'] .provider-item__icon--openai_compatible {
  background: rgba(100, 116, 139, 0.15);
  color: #94a3b8;
}

.provider-item__text {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.provider-item__label {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
  letter-spacing: -0.2px;
}

.provider-item__subtitle {
  font-size: 12px;
  color: var(--text-secondary);
  font-family: monospace;
}

.provider-item__check {
  flex-shrink: 0;
  color: var(--van-primary-color);
}

.provider-item:not(.provider-item--active) .provider-item__check {
  color: var(--border-light);
}

.provider-sheet__actions {
  padding-bottom: 8px;
}
</style>