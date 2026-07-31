<template>
  <div class="modern-template">
    <div class="modern-header">
      <h1 class="modern-title">{{ title }}</h1>
    </div>
    <div class="modern-body">
      <p v-for="(paragraph, idx) in bodyParagraphs" :key="idx">{{ paragraph }}</p>
    </div>
    <div class="modern-signatures">
      <div v-for="(member, idx) in members" :key="idx" class="signature-line">
        <div class="signature-label">{{ member.name }}</div>
        <div class="signature-underline">
          <img
            v-if="signatures[idx]?.data"
            :src="signatures[idx].data!"
            :alt="signatures[idx].name"
            class="signature-image"
          />
          <span v-else-if="signatures[idx]?.data === null" class="tap-consented">✓ {{ t('manifesto.tapConsented') }}</span>
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
.modern-template {
  width: 100%;
}

.modern-header {
  background: var(--color-primary, var(--van-primary-color, #1989fa));
  padding: 1.5rem;
  border-radius: 8px 8px 0 0;
}

.modern-title {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-weight: bold;
  font-size: 1.4rem;
  color: #fff;
  margin: 0;
  text-align: center;
}

.modern-body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  line-height: 1.6;
  color: var(--text-primary, #0a0a0a);
  padding: 1.5rem;
}

.modern-body p {
  margin-bottom: 1em;
}

.modern-signatures {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  padding: 1.5rem;
  border-top: 1px solid var(--color-border, #dcdfe6);
}

.signature-line {
  flex: 1;
  min-width: 100px;
}

.signature-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
  margin-bottom: 4px;
}

.signature-underline {
  border-bottom: 1px solid var(--color-ink, #0a0a0a);
  min-height: 48px;
  position: relative;
  display: flex;
  align-items: flex-end;
}

.signature-image {
  max-width: 120px;
  max-height: 48px;
}

.tap-consented {
  color: var(--color-success, #07c160);
  font-size: 20px;
  font-weight: bold;
}
</style>
