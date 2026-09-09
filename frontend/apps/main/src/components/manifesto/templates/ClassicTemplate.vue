<template>
  <div class="classic-template">
    <div class="certificate-border">
      <!-- Wax seal: appears when all members have signed -->
      <WaxSeal v-if="isEffective" :family-name="familyName" class="wax-seal-position" />

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
          <div class="signature-name-row">
            <van-icon
              :name="statusIcon(member.signingStatus)"
              :color="statusColor(member.signingStatus)"
              size="14"
              class="signature-status-icon"
            />
            <span class="signature-name">{{ member.name }}</span>
          </div>
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
          <div v-if="member.signedDate" class="signature-date">{{ member.signedDate }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFamilyStore } from '@/stores/family'
import WaxSeal from '../WaxSeal.vue'

const { t } = useI18n()
const familyStore = useFamilyStore()

interface SignatureInfo {
  name: string
  data: string | null | undefined
}

interface MemberInfo {
  name: string
  role: string
  signingStatus?: 'signed' | 'confirmed' | 'pending_sign' | 'pending_confirm' | 'rejected' | 'expired'
  signedDate?: string
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

const isEffective = computed(() => {
  const adults = props.members.filter(m => m.role !== 'child')
  return adults.length > 0
    && adults.every(m => m.signingStatus === 'signed' || m.signingStatus === 'confirmed')
})

const familyName = computed(() => familyStore.family?.name ?? '')

function statusIcon(status?: string): string {
  switch (status) {
    case 'signed':
    case 'confirmed':
      return 'success'
    case 'rejected':
      return 'close'
    default:
      return 'clock-o'
  }
}

function statusColor(status?: string): string {
  switch (status) {
    case 'signed':
    case 'confirmed':
      return 'var(--color-success, #07c160)'
    case 'rejected':
      return 'var(--color-error, #ee0a24)'
    default:
      return 'var(--text-secondary, #c8c9cc)'
  }
}
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

/* ── Wax seal: bottom-right of signature area ── */
.wax-seal-position {
  position: absolute;
  bottom: 1.5rem;
  right: 1.5rem;
  z-index: 2;
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
  margin-bottom: 4.5rem; /* reserve space for wax seal */
}

.signature-cell {
  text-align: center;
  padding: 0.5rem;
}

.signature-name-row {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 0.5rem;
}

.signature-status-icon {
  flex-shrink: 0;
}

.signature-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary, #0a0a0a);
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

.signature-date {
  font-size: 11px;
  color: var(--text-secondary, #616161);
  margin-top: 4px;
}
</style>
