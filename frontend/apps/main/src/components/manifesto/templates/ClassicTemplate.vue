<template>
  <div class="classic-template">
    <div class="certificate-border">
      <!-- Corner ornaments -->
      <span class="ornament ornament-tl"></span>
      <span class="ornament ornament-tr">☙</span>
      <span class="ornament ornament-bl">☙</span>
      <span class="ornament ornament-br"></span>

      <!-- Family crest emblem -->
      <div class="certificate-emblem">
        <div class="emblem-shield">⚜</div>
      </div>

      <h1 class="certificate-title">{{ title }}</h1>
      <div class="certificate-divider">
        <span class="divider-line" />
        <span class="divider-ornament">◆</span>
        <span class="divider-line" />
      </div>
      <div class="certificate-body">
        <p v-for="(paragraph, idx) in bodyParagraphs" :key="idx">
          <span v-if="bodyParagraphs.length > 1" class="paragraph-num">{{ idx + 1 }}</span>
          {{ paragraph }}
        </p>
      </div>
      <div class="certificate-divider signature-divider">
        <span class="divider-line" />
        <span class="divider-ornament">◆</span>
        <span class="divider-line" />
      </div>
      <div class="signature-grid">
        <div v-for="(member, idx) in members" :key="idx" class="signature-cell">
          <div class="signature-name">{{ member.name }}</div>
          <div class="signature-role">{{ member.role === 'owner' ? t('manifesto.ownerRole') : member.role === 'member' ? t('manifesto.memberRole') : t('manifesto.childRole') }}</div>
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
  data: string | null | undefined
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
  padding: 2rem 1.5rem;
  border-radius: 4px;
  position: relative;
  background: linear-gradient(180deg, rgba(253, 246, 227, 0.15) 0%, transparent 30%);
}

/* ── Corner ornaments ── */
.ornament {
  position: absolute;
  font-size: 20px;
  color: #c9a84c;
  line-height: 1;
  pointer-events: none;
}

.ornament-tl {
  top: 6px;
  left: 10px;
}

.ornament-tr {
  top: 6px;
  right: 10px;
  transform: scaleX(-1);
}

.ornament-bl {
  bottom: 6px;
  left: 10px;
  transform: scaleY(-1);
}

.ornament-br {
  bottom: 6px;
  right: 10px;
  transform: scale(-1, -1);
}

/* ─ Family emblem ── */
.certificate-emblem {
  display: flex;
  justify-content: center;
  margin-bottom: 0.5rem;
}

.emblem-shield {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 2px solid #c9a84c;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  color: #c9a84c;
  background: rgba(201, 168, 76, 0.08);
}

/* ── Title ── */
.certificate-title {
  text-align: center;
  font-family: 'Noto Serif SC', 'Times New Roman', serif;
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--text-primary, #0a0a0a);
  margin: 0 0 0.75rem;
  letter-spacing: 0.05em;
}

/* ── Divider ── */
.certificate-divider {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 auto 1.25rem;
  width: 60%;
}

.signature-divider {
  margin: 1.5rem auto;
}

.divider-line {
  flex: 1;
  height: 1px;
  background: #c9a84c;
  opacity: 0.5;
}

.divider-ornament {
  font-size: 10px;
  color: #c9a84c;
  flex-shrink: 0;
}

/* ── Body ── */
.certificate-body {
  font-family: 'Noto Serif SC', 'Times New Roman', serif;
  line-height: 1.8;
  color: var(--text-primary, #0a0a0a);
  margin-bottom: 0;
}

.certificate-body p {
  margin-bottom: 1em;
  text-indent: 2em;
  position: relative;
}

.paragraph-num {
  display: inline;
  font-weight: 700;
  color: #c9a84c;
  margin-right: 2px;
}

/* ── Signature grid ── */
.signature-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
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
