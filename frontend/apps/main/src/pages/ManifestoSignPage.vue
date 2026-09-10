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

    <template v-else-if="manifesto?.current_version">
      <!-- 1. Manifesto content (full, scrollable) -->
      <div class="sign-content-area">
        <ManifestoViewer
          :template-id="templateId"
          :title="manifesto.current_version!.title"
          :body="manifesto.current_version!.body"
          :signatures="signatures"
          :members="members"
        />
      </div>

      <!-- 2. Action area (signature pad + buttons) -->
      <div v-if="showActionArea" class="sign-action-area">
        <!-- Adult: pending sign → SignaturePad + buttons -->
        <template v-if="currentUserState?.status === 'pending_sign'">
          <p class="sign-hint">{{ t('manifesto.confirmSign') }}</p>
          <SignaturePad ref="sigPadRef" :height="120" @draw="onSignatureDraw" />
          <van-button
            type="primary"
            block
            :loading="signing"
            :disabled="sigPadEmpty || !gatesPassed"
            @click="onConfirmSign"
          >
            {{ t('manifesto.action.confirmSign') }}
          </van-button>
          <van-button
            v-if="canReject"
            plain
            type="danger"
            block
            :loading="rejecting"
            :disabled="!gatesPassed"
            @click="onReject"
          >
            {{ t('manifesto.reject.btn') }}
          </van-button>
          <div v-if="!gatesPassed" class="sign-gate-hint">
            <van-icon name="info-o" />
            <span>{{ t('manifesto.waitTimer') }}</span>
          </div>
        </template>

        <!-- Child: pending confirm → confirm button only -->
        <template v-else-if="currentUserState?.status === 'pending_confirm'">
          <p class="sign-hint">{{ t('manifesto.action.confirmConsent') }}</p>
          <van-button
            type="primary"
            block
            :loading="signing"
            @click="onConfirmConsent"
          >
            {{ t('manifesto.action.confirmConsent') }}
          </van-button>
        </template>
      </div>

      <!-- 3. Flow chart (collapsible) -->
      <div class="sign-flow-area">
        <van-collapse v-model="flowExpanded">
          <van-collapse-item :title="t('manifesto.signSection.flowTitle')" name="flow">
            <SigningTimeline
              :flow-state="flowState"
              :current-round="currentRound"
              :member-states="memberStates"
              :deadline-info="deadlineInfo"
              :signing-progress="signingProgress"
              :creator-name="creatorName"
              :change-type="changeType"
              :has-rejection="hasRejection"
              :next-version-number="nextVersionNumber"
              :created-at="manifesto.created_at"
              :effective-date="manifesto.current_version?.signed_at ?? undefined"
            />
          </van-collapse-item>
        </van-collapse>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import ManifestoViewer from '@/components/manifesto/ManifestoViewer.vue'
import SignaturePad from '@/components/manifesto/SignaturePad.vue'
import SigningTimeline from '@/components/manifesto/SigningTimeline.vue'
import { useFamilyStore } from '@/stores/family'
import { useAuth } from '@/composables/useAuth'
import * as manifestoApi from '@/api/manifesto'
import { useManifestoFlow } from '@/composables/useManifestoFlow'
import type { Manifesto, FlowMemberState } from '@/types/manifesto'

defineOptions({ name: 'ManifestoSign' })

const { t, locale } = useI18n()
const router = useRouter()
const familyStore = useFamilyStore()
const { currentUser } = useAuth()

const loading = ref(true)
const signing = ref(false)
const rejecting = ref(false)
const manifesto = ref<Manifesto | null>(null)
const sigPadRef = ref<InstanceType<typeof SignaturePad> | null>(null)
const sigPadEmpty = ref(true)

const gatesPassed = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

const templateId = computed(() => manifesto.value?.current_version?.template_id ?? 'modern')

const currentUserId = computed(() => currentUser.value?.id ?? null)

const {
  flowState,
  memberStates,
  currentRound,
  signingProgress,
  deadlineInfo,
  currentUserState,
  canSign,
  canReject,
  creatorName,
  hasRejection,
  nextVersionNumber,
} = useManifestoFlow(manifesto, computed(() => familyStore.members), currentUserId)

const changeType = computed(() => manifesto.value?.current_version?.change_type ?? 'initial')

const showActionArea = computed(() => {
  const state = flowState.value
  const userState = currentUserState.value
  if (!userState) return false
  if (state === 'signing' || state === 'expired') return true
  return false
})

/** Auto-collapse flow when all signed / effective; expand when pending or rejected. */
const flowExpanded = ref<string[]>([])

watch(
  () => flowState.value,
  (state) => {
    if (state === 'effective' || state === 'draft') {
      flowExpanded.value = []
    } else {
      flowExpanded.value = ['flow']
    }
  },
  { immediate: true },
)

function formatSignDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString(locale.value, { year: 'numeric', month: 'long', day: 'numeric' })
}

const signatures = computed(() => {
  if (!manifesto.value) return []
  const sigMap = new Map(
    manifesto.value.signatures.map(s => [s.user_id, s.signature_data ?? null]),
  )
  return familyStore.members.map(m => ({
    name: m.display_name,
    data: sigMap.has(m.id) ? sigMap.get(m.id) : undefined,
  }))
})

const members = computed(() => {
  const m = manifesto.value
  if (!m) return familyStore.members.map(mem => ({
    name: mem.display_name,
    role: mem.role,
  }))
  const sigMap = new Map(m.signatures.map(s => [s.user_id, s]))
  const rejMap = new Map((m.rejections ?? []).map(r => [r.user_id, r]))
  return familyStore.members.map(mem => {
    const sig = sigMap.get(mem.id)
    const rej = rejMap.get(mem.id)
    let signingStatus: FlowMemberState['status']
    if (rej) {
      signingStatus = 'rejected'
    } else if (sig) {
      signingStatus = mem.role === 'child' ? 'confirmed' : 'signed'
    } else {
      signingStatus = mem.role === 'child' ? 'pending_confirm' : 'pending_sign'
    }
    return {
      name: mem.display_name,
      role: mem.role,
      signingStatus,
      signedDate: sig?.signed_at ? formatSignDate(sig.signed_at) : (rej?.created_at ? formatSignDate(rej.created_at) : undefined),
    }
  })
})

onMounted(async () => {
  if (familyStore.members.length === 0) {
    try {
      await familyStore.fetchFamily()
    } catch {
      // non-critical
    }
  }

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

  // Simple timer gate: enable buttons after 3 seconds
  if (canSign.value && currentUserState.value?.status === 'pending_sign') {
    timer = setTimeout(() => {
      gatesPassed.value = true
    }, 3000)
  } else {
    gatesPassed.value = true
  }
})

onBeforeUnmount(() => {
  if (timer) clearTimeout(timer)
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
    await refreshManifesto()
  } catch {
    showFailToast(t('manifesto.signFailed'))
  } finally {
    signing.value = false
  }
}

async function onConfirmConsent() {
  signing.value = true
  try {
    await manifestoApi.signManifesto(null)
    showSuccessToast(t('manifesto.signSuccess'))
    await refreshManifesto()
  } catch {
    showFailToast(t('manifesto.signFailed'))
  } finally {
    signing.value = false
  }
}

async function onReject() {
  try {
    await showConfirmDialog({
      title: t('manifesto.reject.confirmTitle'),
      message: t('manifesto.reject.confirmMessage'),
    })
    rejecting.value = true
    await manifestoApi.rejectManifesto()
    showSuccessToast(t('manifesto.reject.success'))
    await refreshManifesto()
  } catch {
    if (rejecting.value) {
      showFailToast(t('manifesto.reject.failed'))
    }
  } finally {
    rejecting.value = false
  }
}

async function refreshManifesto() {
  try {
    const res = await manifestoApi.getCurrentManifesto()
    manifesto.value = res.data
  } catch {
    // Ignore refresh errors
  }
}
</script>

<style scoped>
.manifesto-sign-page {
  min-height: 100vh;
  background: var(--bg-primary, #ffffff);
}

.sign-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

.sign-content-area {
  padding: 16px;
}

.sign-action-area {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sign-flow-area {
  padding: 0 16px 16px;
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
  padding: 8px 16px;
  font-size: 13px;
  color: var(--text-secondary, #616161);
  background: rgba(100, 108, 255, 0.04);
  border-radius: 8px;
}
</style>
