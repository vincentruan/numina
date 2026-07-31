<template>
  <div class="manifesto-signing-page">
    <van-nav-bar
      :title="t('manifesto.sign')"
      left-arrow
      @click-left="router.back()"
    />

    <div class="signing-scroll-area">
      <div v-if="loading" class="signing-loading">
        <van-loading type="spinner" />
      </div>

      <template v-else-if="manifesto">
        <div class="signing-ceremony-card">
          <div class="signing-icon">📜</div>
          <h1 class="signing-title">{{ manifesto.title }}</h1>
          <div class="signing-body">{{ manifesto.body }}</div>
        </div>

        <div v-if="signed" class="signing-success-card">
          <div class="success-icon">✅</div>
          <p class="success-title">{{ t('manifesto.signSuccess') }}</p>
          <p class="success-badge">{{ t('manifesto.guardian') }}</p>
        </div>

        <template v-else>
          <!-- Age < 5: simple tap-to-consent -->
          <div v-if="ageGroup === 'simple'" class="signing-simple-branch">
            <button class="btn-consent-big" @click="onTapConsent">
              {{ t('manifesto.tapConsent') }}
            </button>
            <button
              class="btn-toggle-handwriting"
              @click="showHandwriting = !showHandwriting"
            >
              {{ showHandwriting ? t('manifesto.hideHandwriting') : t('manifesto.handwriting') }}
            </button>
            <ChildSignaturePad
              v-if="showHandwriting"
              ref="signaturePadRef"
              :width="280"
              :height="120"
              :stroke-width="3"
              @draw="onSignatureDraw"
            />
            <button
              v-if="showHandwriting"
              class="btn-stamp"
              :disabled="signatureEmpty"
              @click="onStampHandwriting"
            >
              {{ t('manifesto.stamp') }}
            </button>
          </div>

          <!-- Age >= 5: handwriting required -->
          <div v-else class="signing-handwriting-branch">
            <p class="signing-hint">{{ t('manifesto.signHint') }}</p>
            <ChildSignaturePad
              ref="signaturePadRef"
              :width="280"
              :height="140"
              @draw="onSignatureDraw"
            />
            <button
              class="btn-stamp"
              :disabled="signatureEmpty || submitting"
              @click="onStampHandwriting"
            >
              {{ submitting ? t('common.loading') : t('manifesto.stamp') }}
            </button>
          </div>
        </template>
      </template>

      <div v-else class="signing-empty">
        <EmptyState :illustration="noTasksSvg" :text="t('manifesto.notFound')" />
      </div>
    </div>

    <!-- Simple signing success celebration overlay -->
    <Teleport to="body">
      <Transition name="celebration-fade">
        <div
          v-if="celebrating"
          class="manifesto-celebration-overlay"
          role="dialog"
          aria-modal="true"
          :aria-label="t('manifesto.signSuccess')"
          @click.self="dismissCelebration"
        >
          <div class="manifesto-celebration-card">
            <div class="celebration-badge-icon">🛡️</div>
            <h2 class="celebration-title">{{ t('manifesto.signSuccess') }}</h2>
            <p class="celebration-badge-label">{{ t('manifesto.guardian') }}</p>
            <button class="celebration-confirm" @click="dismissCelebration">
              {{ t('celebration.confirmButton') }}
            </button>
          </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ManifestoSigning' })
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useManifestoSign } from '@/composables/useManifestoSign'
import ChildSignaturePad from '@/components/manifesto/ChildSignaturePad.vue'
import EmptyState from '@/components/EmptyState.vue'
import noTasksSvgRaw from '@/assets/empty-states/no-tasks.svg?raw'

const noTasksSvg = noTasksSvgRaw

const { t } = useI18n()
const router = useRouter()

const {
  manifesto,
  loading,
  signed,
  celebrating,
  ageGroup,
  init,
  sign,
  dismissCelebration,
} = useManifestoSign()

const signaturePadRef = ref<InstanceType<typeof ChildSignaturePad> | null>(null)
const signatureEmpty = ref(true)
const showHandwriting = ref(false)
const submitting = ref(false)

function onSignatureDraw() {
  signatureEmpty.value = false
}

async function onTapConsent() {
  try {
    await showConfirmDialog({
      title: t('manifesto.tapConsent'),
      message: t('manifesto.confirmConsent'),
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
    })
    await doSign(null)
  } catch {
    // User cancelled — no-op
  }
}

async function onStampHandwriting() {
  const dataUrl = signaturePadRef.value?.toDataURL() ?? ''
  if (!dataUrl) return
  await doSign(dataUrl)
}

async function doSign(signatureData: string | null) {
  submitting.value = true
  try {
    await sign(signatureData)
    showSuccessToast(t('manifesto.signSuccess'))
  } catch {
    showFailToast(t('toast.submitFailed'))
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await init()
})
</script>

<style scoped>
.manifesto-signing-page {
  min-height: 100vh;
  background: var(--color-canvas, #fffaf0);
}

.signing-scroll-area {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.signing-loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}

.signing-ceremony-card {
  background: var(--color-surface-card, #ffffff);
  border-radius: var(--radius-lg, 16px);
  padding: 24px 20px;
  border: 1px solid var(--color-hairline, #e5e2d6);
  text-align: center;
}

.signing-icon {
  font-size: 40px;
  margin-bottom: 12px;
}

.signing-title {
  font-family: Inter, sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-ink, #0a0a0a);
  margin: 0 0 16px;
  line-height: 1.3;
}

.signing-body {
  font-family: Inter, sans-serif;
  font-size: 16px;
  line-height: 1.7;
  color: var(--color-body, #3d3d3d);
  white-space: pre-wrap;
  text-align: left;
}

.signing-success-card {
  background: var(--color-surface-card, #ffffff);
  border-radius: var(--radius-lg, 16px);
  padding: 24px;
  border: 1px solid var(--color-hairline, #e5e2d6);
  text-align: center;
}

.success-icon {
  font-size: 48px;
  margin-bottom: 8px;
}

.success-title {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-ink, #0a0a0a);
  margin: 0 0 6px;
}

.success-badge {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-brand-ochre, #c8963c);
  font-weight: 600;
  margin: 0;
}

.signing-simple-branch,
.signing-handwriting-branch {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  padding: 8px 0;
}

.signing-hint {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-muted, #6b6b6b);
  margin: 0;
  text-align: center;
}

.btn-consent-big {
  width: 100%;
  max-width: 320px;
  background: var(--color-primary, #0a0a0a);
  color: var(--color-on-dark, #ffffff);
  border: none;
  border-radius: var(--radius-md, 12px);
  padding: 18px;
  font-family: Inter, sans-serif;
  font-size: 20px;
  font-weight: 700;
  cursor: pointer;
  min-height: 56px;
  transition: transform 0.1s;
}

.btn-consent-big:active {
  transform: scale(0.96);
}

.btn-toggle-handwriting {
  background: transparent;
  color: var(--color-brand-ochre, #c8963c);
  border: 1px dashed var(--color-brand-ochre, #c8963c);
  border-radius: var(--radius-pill, 999px);
  padding: 8px 18px;
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
}

.btn-stamp {
  width: 100%;
  max-width: 320px;
  background: var(--color-brand-ochre, #c8963c);
  color: var(--color-on-dark, #ffffff);
  border: none;
  border-radius: var(--radius-md, 12px);
  padding: 14px;
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  min-height: 48px;
  transition: transform 0.1s, opacity 0.15s;
}

.btn-stamp:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.btn-stamp:active:not(:disabled) {
  transform: scale(0.96);
}

.signing-empty {
  padding: 40px 0;
}

/* Celebration overlay */
.manifesto-celebration-overlay {
  position: fixed;
  inset: 0;
  background: rgba(10, 10, 10, 0.55);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  z-index: 999;
}

.manifesto-celebration-card {
  background: var(--color-surface-card, #ffffff);
  border-radius: var(--radius-lg, 20px);
  padding: 32px 24px;
  max-width: 320px;
  width: 100%;
  text-align: center;
  box-shadow: 0 16px 48px rgba(10, 10, 10, 0.25);
  animation: celebration-pop 400ms cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.celebration-badge-icon {
  font-size: 64px;
  margin-bottom: 12px;
  animation: badge-bounce 800ms ease-out;
}

.celebration-title {
  font-family: Inter, sans-serif;
  font-size: 20px;
  font-weight: 700;
  color: var(--color-ink, #0a0a0a);
  margin: 0 0 6px;
}

.celebration-badge-label {
  font-family: Inter, sans-serif;
  font-size: 14px;
  color: var(--color-brand-ochre, #c8963c);
  font-weight: 600;
  margin: 0 0 20px;
}

.celebration-confirm {
  width: 100%;
  background: var(--color-primary, #0a0a0a);
  color: var(--color-on-dark, #ffffff);
  border: none;
  border-radius: var(--radius-md, 12px);
  padding: 14px;
  font-family: Inter, sans-serif;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  min-height: 44px;
}

.celebration-confirm:active {
  transform: scale(0.96);
}

.celebration-fade-enter-active,
.celebration-fade-leave-active {
  transition: opacity 200ms ease-out;
}

.celebration-fade-enter-from,
.celebration-fade-leave-to {
  opacity: 0;
}

@keyframes celebration-pop {
  0% {
    transform: scale(0.6);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes badge-bounce {
  0%, 100% { transform: translateY(0); }
  30% { transform: translateY(-12px); }
  60% { transform: translateY(-4px); }
}

@media (prefers-reduced-motion: reduce) {
  .manifesto-celebration-card,
  .celebration-badge-icon {
    animation: none;
  }
}
</style>
