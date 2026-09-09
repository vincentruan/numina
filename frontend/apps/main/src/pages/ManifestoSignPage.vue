<template>
  <CeremonyRoom @close="router.back()">
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

        <!-- Already signed -->
        <div v-else-if="currentUserState?.status === 'signed'" class="sign-status-badge">
          <van-icon name="checked" color="var(--color-success, #19ad4d)" />
          <span>{{ t('manifesto.action.mySigned') }}</span>
        </div>

        <!-- Already confirmed (child) -->
        <div v-else-if="currentUserState?.status === 'confirmed'" class="sign-status-badge">
          <van-icon name="checked" color="var(--color-success, #19ad4d)" />
          <span>{{ t('manifesto.action.myConfirmed') }}</span>
        </div>

        <!-- Already rejected -->
        <div v-else-if="currentUserState?.status === 'rejected'" class="sign-status-badge sign-status-badge--rejected">
          <van-icon name="close" color="var(--color-error, #ee0a24)" />
          <span>{{ t('manifesto.action.myRejected') }}</span>
        </div>

        <!-- Expired -->
        <div v-else-if="flowState === 'expired'" class="sign-status-badge">
          <van-icon name="clock-o" color="var(--text-secondary, #616161)" />
          <span>{{ t('manifesto.flow.deadlineExpired') }}</span>
        </div>
      </div>

      <!-- 3. Flow chart (bottom, fixed height) -->
      <div class="sign-flow-area">
        <ManifestoFlowViewer
          :flow-state="flowState"
          :current-round="currentRound"
          :member-states="memberStates"
          :deadline-info="deadlineInfo"
          :signing-progress="signingProgress"
          :creator-name="creatorName"
          :change-type="changeType"
          :has-rejection="hasRejection"
          :next-version-number="nextVersionNumber"
        />
      </div>
    </template>
  </CeremonyRoom>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import ManifestoViewer from '@/components/manifesto/ManifestoViewer.vue'
import CeremonyRoom from '@/components/manifesto/CeremonyRoom.vue'
import { useCeremonyRoom } from '@/composables/useCeremonyRoom'
import SignaturePad from '@/components/manifesto/SignaturePad.vue'
import ManifestoFlowViewer from '@/components/manifesto/flow/ManifestoFlowViewer.vue'
import { useFamilyStore } from '@/stores/family'
import { useAuth } from '@/composables/useAuth'
import * as manifestoApi from '@/api/manifesto'
import { useManifestoFlow } from '@/composables/useManifestoFlow'
import type { Manifesto } from '@/types/manifesto'

const { t } = useI18n()
const router = useRouter()
const familyStore = useFamilyStore()
const { currentUser } = useAuth()
useCeremonyRoom(() => router.back())

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

const members = computed(() =>
  familyStore.members.map(m => ({ name: m.display_name, role: m.role })),
)

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

import { onBeforeUnmount } from 'vue'

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
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  border-top: 1px solid var(--card-bg, #f5f5ff);
  border-bottom: 1px solid var(--card-bg, #f5f5ff);
  background: var(--bg-primary, #fff);
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

.sign-status-badge {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px;
  font-size: 15px;
  font-weight: 500;
  color: var(--color-success, #19ad4d);
  border-radius: 10px;
  background: rgba(25, 173, 77, 0.06);
}

.sign-status-badge--rejected {
  color: var(--color-error, #ee0a24);
  background: rgba(238, 10, 36, 0.06);
}

.sign-flow-area {
  padding: 16px;
}
</style>
