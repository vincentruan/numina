<template>
  <div class="manifesto-sign-page">
    <van-nav-bar
      :title="t('manifesto.signPage')"
      left-arrow
      @click-left="router.back()"
    />

    <div v-if="loading" class="sign-loading">
      <van-loading type="spinner" />
    </div>

    <template v-else-if="manifesto">
      <div ref="scrollContainer" class="sign-scroll-area">
        <ManifestoViewer
          :template-id="templateId"
          :title="manifesto.current_version!.title"
          :body="manifesto.current_version!.body"
          :signatures="signatures"
          :members="members"
        />
        <div ref="scrollSentinel" class="sign-sentinel" />
      </div>

      <div v-if="gatesPassed" class="sign-action-area">
        <p class="sign-hint">{{ t('manifesto.confirmSign') }}</p>
        <SignaturePad ref="sigPadRef" :width="sigWidth" :height="120" @draw="onSignatureDraw" />
        <van-button
          type="primary"
          block
          :loading="signing"
          :disabled="sigPadEmpty"
          @click="onConfirmSign"
        >
          {{ t('manifesto.confirmSignBtn') }}
        </van-button>
      </div>

      <div v-else class="sign-gate-hint">
        <van-icon name="info-o" />
        <span>{{ t('manifesto.waitTimer') }}</span>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import ManifestoViewer from '@/components/manifesto/ManifestoViewer.vue'
import SignaturePad from '@/components/manifesto/SignaturePad.vue'
import { useFamilyStore } from '@/stores/family'
import * as manifestoApi from '@/api/manifesto'
import type { Manifesto } from '@/types/manifesto'

const { t } = useI18n()
const router = useRouter()
const familyStore = useFamilyStore()

const loading = ref(true)
const signing = ref(false)
const manifesto = ref<Manifesto | null>(null)
const sigPadRef = ref<InstanceType<typeof SignaturePad> | null>(null)
const sigPadEmpty = ref(true)
const sigWidth = ref(300)

const hasScrolledToBottom = ref(false)
const hasWaitedLongEnough = ref(false)

const scrollContainer = ref<HTMLElement | null>(null)
const scrollSentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null
let timer: ReturnType<typeof setTimeout> | null = null
let safetyTimer: ReturnType<typeof setTimeout> | null = null

const gatesPassed = computed(() => hasScrolledToBottom.value && hasWaitedLongEnough.value)

const templateId = computed(() => manifesto.value?.current_version?.template_id ?? 'modern')

const signatures = computed(() =>
  familyStore.members.map(m => ({ name: m.display_name, data: null })),
)

const members = computed(() =>
  familyStore.members.map(m => ({ name: m.display_name, role: m.role })),
)

onMounted(async () => {
  // Measure available width for signature pad
  sigWidth.value = Math.min(window.innerWidth - 48, 400)

  // Fetch family members for display
  if (familyStore.members.length === 0) {
    try {
      await familyStore.fetchFamily()
    } catch {
      // non-critical
    }
  }

  // Fetch current manifesto
  try {
    const res = await manifestoApi.getCurrentManifesto()
    manifesto.value = res.data
  } catch {
    showFailToast(t('manifesto.signFailed'))
    router.back()
    return
  } finally {
    loading.value = false
  }

  // Wait for DOM to update so scrollSentinel ref is populated
  await nextTick()

  // Start 3-second timer gate
  timer = setTimeout(() => {
    hasWaitedLongEnough.value = true
  }, 3000)

  // Safety backstop: 5-second timeout to auto-enable scroll gate
  safetyTimer = setTimeout(() => {
    hasScrolledToBottom.value = true
  }, 5000)

  // Set up IntersectionObserver on scroll sentinel
  if (scrollSentinel.value) {
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            hasScrolledToBottom.value = true
            observer?.disconnect()
          }
        }
      },
      { root: scrollContainer.value, threshold: 0.1 },
    )
    observer.observe(scrollSentinel.value)
  }
})

onBeforeUnmount(() => {
  observer?.disconnect()
  if (timer) clearTimeout(timer)
  if (safetyTimer) clearTimeout(safetyTimer)
})

function onSignatureDraw() {
  sigPadEmpty.value = sigPadRef.value?.isEmpty() ?? true
}

async function onConfirmSign() {
  if (!sigPadRef.value || sigPadRef.value.isEmpty()) return
  signing.value = true
  try {
    const sigData = sigPadRef.value.toDataURL()
    await manifestoApi.signManifesto(sigData)
    showSuccessToast(t('manifesto.signSuccess'))
    router.back()
  } catch {
    showFailToast(t('manifesto.signFailed'))
  } finally {
    signing.value = false
  }
}
</script>

<style scoped>
.manifesto-sign-page {
  min-height: 100vh;
  background: var(--bg-primary, #fff);
  display: flex;
  flex-direction: column;
}

.sign-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.sign-scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.sign-sentinel {
  height: 1px;
  width: 100%;
}

.sign-action-area {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-top: 1px solid var(--card-bg, #f5f5ff);
}

.sign-hint {
  font-size: 14px;
  color: var(--text-secondary, #616161);
  margin: 0;
  text-align: center;
}

.sign-gate-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  font-size: 14px;
  color: var(--text-secondary, #616161);
}
</style>
