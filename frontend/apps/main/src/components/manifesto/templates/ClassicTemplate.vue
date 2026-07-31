<template>
  <div class="classic-template">
    <div class="certificate-border">
      <h1 class="certificate-title">{{ title }}</h1>
      <div class="certificate-body">
        <p v-for="(paragraph, idx) in bodyParagraphs" :key="idx">{{ paragraph }}</p>
      </div>
      <div class="signature-grid">
        <div v-for="(member, idx) in members" :key="idx" class="signature-cell">
          <div class="signature-name">{{ member.name }}</div>
          <div class="signature-role">{{ member.role }}</div>
          <div class="signature-content">
            <img
              v-if="signatures[idx]?.data"
              :src="signatures[idx].data!"
              :alt="signatures[idx].name"
              class="signature-image"
            />
            <span v-else-if="signatures[idx] && signatures[idx].data === null" class="signature-consented">
              ✓ {{ t('manifesto.tapConsented') }}
            </span>
            <span v-else class="signature-pending">{{ t('manifesto.pending') }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

interface SignatureInfo {
  name: string
  data: string | null
}

interface MemberInfo {
  name: string
  role: string
}

const props = defineProps<{
  title: string
  body: string
  signatures: SignatureInfo[]
  members: MemberInfo[]
}>()

const bodyParagraphs = computed(() => {
  return props.body.split('\n\n').filter(p => p.trim())
})
</script>

<style scoped>
.classic-template {
  width: 100%;
}

.certificate-border {
  border: 3px double var(--color-ink, #0a0a0a);
  padding: 2rem;
  border-radius: 4px;
}

.certificate-title {
  text-align: center;
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--text-primary, #0a0a0a);
  margin-bottom: 1.5rem;
}

.certificate-body {
  font-family: 'Noto Serif SC', 'Times New Roman', serif;
  line-height: 1.8;
  color: var(--text-primary, #0a0a0a);
  margin-bottom: 2rem;
}

.certificate-body p {
  margin-bottom: 1em;
  text-indent: 2em;
}

.signature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  margin-top: 1.5rem;
}

.signature-cell {
  text-align: center;
  padding: 0.5rem;
}

.signature-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary, #0a0a0a);
}

.signature-role {
  font-size: 12px;
  color: var(--text-secondary, #616161);
  margin-bottom: 0.5rem;
}

.signature-content {
  min-height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.signature-image {
  max-width: 120px;
  max-height: 48px;
}

.signature-pending {
  color: var(--text-secondary, #616161);
  font-size: 13px;
}

.signature-consented {
  color: var(--color-success, #1a7a4a);
  font-size: 13px;
  font-weight: 500;
}
</style>
