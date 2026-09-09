<template>
  <div class="modern-template">
    <!-- Wax seal: appears when all members have signed -->
    <WaxSeal v-if="isEffective" :family-name="familyName" class="wax-seal-position" />

    <!-- Top accent bar -->
    <div class="modern-accent-bar">
      <span class="accent-dot" />
      <span class="accent-dot" />
      <span class="accent-dot" />
    </div>

    <FamilyCrest :members="members" :familyName="familyName" />

    <div class="modern-header">
      <h1 class="modern-title">{{ title }}</h1>
      <div class="modern-title-rule" />
    </div>
    <div class="modern-body">
      <p
        v-for="(paragraph, idx) in bodyParagraphs"
        :key="idx"
        data-reveal
        :style="{ '--reveal-index': idx }"
      >
        <span v-if="bodyParagraphs.length > 1" class="para-marker">0{{ idx + 1 }}</span>
        {{ paragraph }}
      </p>
    </div>
    <div class="modern-signatures">
      <div v-for="(member, idx) in members" :key="idx" class="signature-line">
        <div class="signature-name-row">
          <van-icon
            :name="statusIcon(member.signingStatus)"
            :color="statusColor(member.signingStatus)"
            size="16"
            class="signature-status-icon"
          />
          <span class="signature-label">{{ member.name }}</span>
        </div>
        <div class="signature-underline">
          <img
            v-if="signatures[idx]?.data"
            :src="signatures[idx].data!"
            :alt="signatures[idx].name"
            class="signature-image"
          />
          <span v-else-if="signatures[idx]?.data === null" class="tap-consented">✓ {{ t('manifesto.tapConsented') }}</span>
          <span v-else class="signature-pending">{{ t('manifesto.pending') }}</span>
        </div>
        <div v-if="member.signedDate" class="signature-date">{{ member.signedDate }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useFamilyStore } from '@/stores/family'
import WaxSeal from '../WaxSeal.vue'
import FamilyCrest from '../FamilyCrest.vue'

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
.modern-template {
  width: 100%;
  position: relative;
}

/* ── Wax seal: bottom-right of document ── */
.wax-seal-position {
  position: absolute;
  bottom: 1rem;
  right: 1rem;
  z-index: 2;
}

/* ── Top accent bar (3 dots) ── */
.modern-accent-bar {
  display: flex;
  gap: 6px;
  padding: 12px 0;
  justify-content: center;
}

.accent-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--van-primary-color, #1989fa);
  opacity: 0.6;
}

.accent-dot:nth-child(2) {
  opacity: 0.8;
}

.accent-dot:nth-child(3) {
  opacity: 1;
}

/* ─ Header ── */
.modern-header {
  padding: 0.5rem 0;
  margin-bottom: 1.5rem;
}

.modern-title {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  font-weight: 700;
  font-size: 1.3rem;
  color: var(--text-primary, #0a0a0a);
  margin: 0;
  text-align: center;
}

.modern-title-rule {
  width: 40px;
  height: 3px;
  background: var(--van-primary-color, #1989fa);
  border-radius: 2px;
  margin: 10px auto 0;
}

/* ── Body ── */
.modern-body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  line-height: 1.6;
  color: var(--text-primary, #0a0a0a);
  padding: 1.5rem;
  background: var(--card-bg, #fafafa);
  border-radius: 8px;
  border-left: 3px solid var(--van-primary-color, #1989fa);
}

.modern-body p {
  margin-bottom: 1em;
  position: relative;
  padding-left: 0;
}

.modern-body p:last-child {
  margin-bottom: 0;
}

.para-marker {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  color: var(--van-primary-color, #1989fa);
  margin-right: 6px;
  opacity: 0.7;
}

/* ── Signatures ── */
.modern-signatures {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  padding: 1.5rem;
  border-top: 1px solid var(--color-border, #dcdfe6);
  margin-bottom: 4rem; /* reserve space for wax seal */
}

.signature-line {
  flex: 1;
  min-width: 100px;
}

.signature-name-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.signature-status-icon {
  flex-shrink: 0;
}

.signature-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
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

.signature-pending {
  color: var(--text-secondary, #616161);
  font-size: 13px;
}

.signature-date {
  font-size: 11px;
  color: var(--text-secondary, #616161);
  margin-top: 4px;
}

/* ── Scroll reveal: structural entrance animations ── */
.accent-dot {
  opacity: 0;
  animation: sr-dot1-in 150ms ease-out 50ms forwards;
}
.accent-dot:nth-child(2) {
  animation-name: sr-dot2-in;
  animation-delay: 150ms;
}
.accent-dot:nth-child(3) {
  animation-name: sr-dot3-in;
  animation-delay: 250ms;
}

.modern-title {
  opacity: 0;
  animation: sr-modern-fade-in 350ms ease-out 350ms forwards;
}

.modern-title-rule {
  transform: scaleX(0);
  transform-origin: left;
  animation: sr-modern-rule-expand 300ms ease-out 500ms forwards;
}

@keyframes sr-dot1-in { to { opacity: 0.6; } }
@keyframes sr-dot2-in { to { opacity: 0.8; } }
@keyframes sr-dot3-in { to { opacity: 1; } }
@keyframes sr-modern-fade-in { to { opacity: 1; } }
@keyframes sr-modern-rule-expand { to { transform: scaleX(1); } }

@media (prefers-reduced-motion: reduce) {
  .accent-dot {
    animation: none !important;
  }
  .accent-dot:nth-child(1) { opacity: 0.6 !important; }
  .accent-dot:nth-child(2) { opacity: 0.8 !important; }
  .accent-dot:nth-child(3) { opacity: 1 !important; }
  .modern-title {
    opacity: 1 !important;
    animation: none !important;
  }
  .modern-title-rule {
    transform: none !important;
    animation: none !important;
  }
}
</style>
