<template>
  <div
    v-if="manifesto && manifesto.signed"
    class="manifesto-summary-card"
    role="button"
    tabindex="0"
    :aria-label="t('manifesto.ourManifesto')"
    @click="$emit('open')"
    @keydown.enter="$emit('open')"
    @keydown.space.prevent="$emit('open')"
  >
    <div class="manifesto-summary-head">
      <span class="manifesto-summary-icon">📜</span>
      <p class="manifesto-summary-title">{{ t('manifesto.ourManifesto') }}</p>
      <van-icon name="arrow" size="14" color="var(--color-muted-soft)" />
    </div>
    <p class="manifesto-summary-excerpt">{{ manifesto.title }}</p>
    <p class="manifesto-summary-signers">
      {{ signerText }}
    </p>
    <AnniversaryDisplay :signed-at="manifesto.signed_at ?? null" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AnniversaryDisplay from './AnniversaryDisplay.vue'
import type { ChildManifestoData } from '@/api/manifesto'

const props = defineProps<{
  manifesto: ChildManifestoData | null
}>()

defineEmits<{
  open: []
}>()

const { t } = useI18n()

const signerText = computed<string>(() => {
  if (!props.manifesto || props.manifesto.signer_names.length === 0) return ''
  const names = props.manifesto.signer_names
  // Chinese: "爸爸、妈妈、小宝 共同约定"
  // English: "Dad, Mom, Xiaobao — co-created"
  const joined = names.join('、')
  return `${joined} ${t('manifesto.coCreated')}`
})
</script>

<style scoped>
.manifesto-summary-card {
  background: var(--color-surface-card, #ffffff);
  border-radius: var(--radius-lg, 16px);
  padding: 16px;
  border: 1px solid var(--color-hairline, #e5e2d6);
  display: flex;
  flex-direction: column;
  gap: 8px;
  cursor: pointer;
  transition: transform 0.15s;
}

.manifesto-summary-card:active {
  transform: scale(0.98);
}

.manifesto-summary-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.manifesto-summary-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.manifesto-summary-title {
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-muted, #6b6b6b);
  margin: 0;
  flex: 1;
}

.manifesto-summary-excerpt {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink, #0a0a0a);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
}

.manifesto-summary-signers {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body, #3d3d3d);
  margin: 0;
  line-height: 1.4;
}
</style>
