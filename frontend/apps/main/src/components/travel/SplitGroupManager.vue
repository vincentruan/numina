<template>
  <div class="split-group-manager">
    <van-loading v-if="loading" class="component-loading" />

    <template v-else>
      <!-- No split group yet -->
      <div v-if="!splitGroup" class="empty-state">
        <van-button type="primary" block round @click="handleCreateGroup">
          {{ t('travel.splitGroup.createGroup') }}
        </van-button>
      </div>

      <!-- Split group exists -->
      <template v-else>
        <!-- Invite code section -->
        <van-cell-group inset class="invite-section">
          <div class="invite-code-display">
            <div class="code-label">{{ t('travel.splitGroup.inviteCode') }}</div>
            <div class="code-value">{{ splitGroup.invite_code }}</div>
            <van-button size="small" type="primary" plain @click="copyInviteCode">
              {{ t('travel.splitGroup.copyCode') }}
            </van-button>
          </div>
          <van-button type="primary" block round @click="copyInviteLink">
            {{ t('travel.splitGroup.copyLink') }}
          </van-button>
        </van-cell-group>

        <!-- Participants section -->
        <van-cell-group inset class="participants-section">
          <van-cell :title="t('travel.splitGroup.participants')">
            <template #label>
              <div class="participant-list">
                <div
                  v-for="participant in splitGroup.participants"
                  :key="participant.id"
                  class="participant-item"
                >
                  <span class="participant-name">{{ participant.name }}</span>
                  <van-button
                    size="mini"
                    plain
                    type="danger"
                    @click="handleRemoveParticipant(participant.id)"
                  >
                    {{ t('travel.splitGroup.removeParticipant') }}
                  </van-button>
                </div>
              </div>
            </template>
          </van-cell>
        </van-cell-group>

        <!-- Settlement section -->
        <van-cell-group inset class="settlement-section">
          <van-button
            v-if="!hasSettlements"
            type="primary"
            block
            round
            :loading="generating"
            :disabled="generating"
            @click="handleGenerateSettlement"
          >
            {{ generating ? t('travel.splitGroup.generating') : t('travel.splitGroup.generateSettlement') }}
          </van-button>
          <van-button
            v-else
            type="primary"
            block
            round
            @click="navigateToSettlement"
          >
            {{ t('travel.splitGroup.viewSettlement') }}
          </van-button>
        </van-cell-group>
      </template>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import { useTravelStore } from '@/stores/travel'
import {
  createSplitGroup,
  simplifyDebts,
} from '@/api/travel'

const props = defineProps<{
  tripId: string
}>()

const { t } = useI18n()
const router = useRouter()
const store = useTravelStore()

const loading = ref(true)
const generating = ref(false)

const splitGroup = computed(() => store.splitGroup)
const hasSettlements = computed(() => store.settlements.length > 0)

async function handleCreateGroup() {
  try {
    await createSplitGroup(props.tripId)
    await store.fetchSplitGroup(props.tripId)
    showSuccessToast(t('common.success'))
  } catch {
    showFailToast(t('common.failed'))
  }
}

async function copyInviteCode() {
  if (!splitGroup.value) return
  try {
    await navigator.clipboard.writeText(splitGroup.value.invite_code)
    showSuccessToast(t('travel.splitGroup.copied'))
  } catch {
    showFailToast(t('travel.splitGroup.copyFailed'))
  }
}

async function copyInviteLink() {
  if (!splitGroup.value) return
  const link = `${window.location.origin}/travel/shared/${splitGroup.value.invite_code}`
  try {
    await navigator.clipboard.writeText(link)
    showSuccessToast(t('travel.splitGroup.copied'))
  } catch {
    showFailToast(t('travel.splitGroup.copyFailed'))
  }
}

async function handleRemoveParticipant(participantId: string) {
  try {
    await showConfirmDialog({
      title: t('travel.splitGroup.removeParticipant'),
      message: t('travel.splitGroup.removeConfirm'),
    })
    // TODO: Implement remove participant API
    await store.fetchSplitGroup(props.tripId)
    showSuccessToast(t('common.success'))
  } catch {
    // user cancelled
  }
}

async function handleGenerateSettlement() {
  generating.value = true
  try {
    await simplifyDebts(props.tripId)
    await store.fetchSettlements(props.tripId)
    showSuccessToast(t('common.success'))
  } catch {
    showFailToast(t('common.failed'))
  } finally {
    generating.value = false
  }
}

function navigateToSettlement() {
  router.push(`/travel/${props.tripId}/settlement`)
}

onMounted(async () => {
  try {
    await Promise.all([
      store.fetchSplitGroup(props.tripId),
      store.fetchSettlements(props.tripId),
    ])
  } catch {
    // ignore - might not have group yet
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.split-group-manager {
  padding: 12px 0;
}
.component-loading {
  display: flex;
  justify-content: center;
  padding: 40px 0;
}
.empty-state {
  padding: 20px 12px;
}
.invite-section,
.participants-section,
.settlement-section {
  margin: 12px;
}
.invite-code-display {
  padding: 16px 0;
  text-align: center;
}
.code-label {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 8px;
}
.code-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 2px;
  margin-bottom: 16px;
  font-family: monospace;
}
.participant-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 8px 0;
}
.participant-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color, #ebedf0);
}
.participant-item:last-child {
  border-bottom: none;
}
.participant-name {
  font-size: 14px;
  color: var(--text-primary);
}
</style>
