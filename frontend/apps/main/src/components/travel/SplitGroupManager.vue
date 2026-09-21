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
            <div v-if="isExpired" class="code-expired">
              <van-tag type="danger">{{ t('travel.splitGroup.codeExpired') }}</van-tag>
            </div>
            <div v-else-if="splitGroup.expires_at" class="code-expires">
              <van-tag type="primary" plain>
                {{ t('travel.splitGroup.codeExpiresAt', { date: formatExpiryDate(splitGroup.expires_at) }) }}
              </van-tag>
            </div>
            <div class="code-actions">
              <van-button size="small" type="primary" plain @click="copyInviteCode">
                {{ t('travel.splitGroup.copyCode') }}
              </van-button>
              <van-button size="small" plain @click="handleRegenerateCode">
                {{ t('travel.splitGroup.regenerateCode') }}
              </van-button>
            </div>
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
                  <div class="participant-actions">
                    <van-button
                      size="mini"
                      plain
                      type="primary"
                      @click="resendLink(participant)"
                    >
                      {{ t('travel.splitGroup.resendLink') }}
                    </van-button>
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
              </div>
            </template>
          </van-cell>
        </van-cell-group>

        <!-- Co-organizers section -->
        <van-cell-group inset class="co-organizer-section">
          <van-cell :title="t('travel.splitGroup.coOrganizers')" :label="t('travel.splitGroup.maxCoOrganizers')">
            <template #extra>
              <van-button size="small" type="primary" plain @click="showAddCoOrganizer = true">
                {{ t('travel.splitGroup.addCoOrganizer') }}
              </van-button>
            </template>
          </van-cell>
          <div v-if="coOrganizers.length === 0" class="empty-hint">
            {{ t('travel.splitGroup.noCoOrganizers') }}
          </div>
          <div v-else class="co-organizer-list">
            <div
              v-for="co in coOrganizers"
              :key="co.user_id"
              class="co-organizer-item"
            >
              <span class="co-organizer-name">{{ co.display_name }}</span>
              <van-button
                size="mini"
                plain
                type="danger"
                @click="handleRemoveCoOrganizer(co.user_id)"
              >
                {{ t('travel.splitGroup.removeCoOrganizer') }}
              </van-button>
            </div>
          </div>
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

        <!-- Add Co-organizer Picker -->
        <van-popup v-model:show="showAddCoOrganizer" position="bottom" round destroy-on-close>
          <van-picker
            :title="t('travel.splitGroup.selectMember')"
            :columns="availableMemberColumns"
            @confirm="onCoOrganizerConfirm"
            @cancel="showAddCoOrganizer = false"
          />
        </van-popup>
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
import { getMembers } from '@/api/family'
import {
  createSplitGroup,
  simplifyDebts,
  removeParticipant,
  regenerateInviteCode,
  addCoOrganizer,
  removeCoOrganizer,
} from '@/api/travel'
import type { SplitParticipant } from '@/types/travel'

const props = defineProps<{
  tripId: string
}>()

const { t, locale } = useI18n()
const router = useRouter()
const store = useTravelStore()

const loading = ref(true)
const generating = ref(false)
const showAddCoOrganizer = ref(false)

interface FamilyMember {
  id: string
  display_name: string
}

interface CoOrganizer {
  user_id: string
  display_name: string
}

const familyMembers = ref<FamilyMember[]>([])
const coOrganizers = ref<CoOrganizer[]>([])

const splitGroup = computed(() => store.splitGroup)
const hasSettlements = computed(() => store.settlements.length > 0)

const isExpired = computed(() => {
  if (!splitGroup.value?.expires_at) return false
  return new Date() > new Date(splitGroup.value.expires_at)
})

const availableMemberColumns = computed(() => {
  const existingIds = new Set(coOrganizers.value.map(c => c.user_id))
  return familyMembers.value
    .filter(m => !existingIds.has(m.id))
    .map(m => ({ text: m.display_name, value: m.id }))
})

function formatExpiryDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString(locale.value, { year: 'numeric', month: 'short', day: 'numeric' })
}

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

async function resendLink(_participant: SplitParticipant) {
  if (!splitGroup.value) return
  const link = `${window.location.origin}/travel/shared/${splitGroup.value.invite_code}`
  try {
    await navigator.clipboard.writeText(link)
    showSuccessToast(t('travel.splitGroup.copied'))
  } catch {
    showFailToast(t('travel.splitGroup.copyFailed'))
  }
}

async function handleRegenerateCode() {
  try {
    await showConfirmDialog({
      title: t('travel.splitGroup.regenerateCode'),
      message: t('travel.splitGroup.regenerateConfirm'),
    })
    const res = await regenerateInviteCode(props.tripId)
    store.splitGroup = res.data
    showSuccessToast(t('common.success'))
  } catch {
    // user cancelled or error
  }
}

async function handleRemoveParticipant(participantId: string) {
  try {
    await showConfirmDialog({
      title: t('travel.splitGroup.removeParticipant'),
      message: t('travel.splitGroup.removeConfirm'),
    })
    await removeParticipant(props.tripId, participantId)
    await store.fetchSplitGroup(props.tripId)
    showSuccessToast(t('common.success'))
  } catch {
    // user cancelled or error
  }
}

async function onCoOrganizerConfirm({ selectedOptions }: { selectedOptions: Array<{ value?: string }> }) {
  showAddCoOrganizer.value = false
  const userId = selectedOptions[0]?.value
  if (!userId) return
  try {
    await addCoOrganizer(props.tripId, userId)
    await fetchCoOrganizers()
    showSuccessToast(t('common.success'))
  } catch {
    showFailToast(t('common.failed'))
  }
}

async function handleRemoveCoOrganizer(userId: string) {
  try {
    await removeCoOrganizer(props.tripId, userId)
    await fetchCoOrganizers()
    showSuccessToast(t('common.success'))
  } catch {
    showFailToast(t('common.failed'))
  }
}

async function fetchCoOrganizers() {
  try {
    const { getSplitGroup: fetchGroup } = await import('@/api/travel')
    const groupRes = await fetchGroup(props.tripId)
    // TODO: Replace with dedicated GET /trips/{id}/co-organizers endpoint.
    // Currently deriving from participants with family_id set — a heuristic,
    // not the actual trip_co_organizers table data. Works for display but
    // won't distinguish co-organizers from regular family-member participants.
    const members = familyMembers.value
    const participantFamilyIds = new Set(
      (groupRes.data.participants || [])
        .filter(p => p.family_id)
        .map(p => p.family_id!),
    )
    coOrganizers.value = members
      .filter(m => participantFamilyIds.has(m.id))
      .map(m => ({ user_id: m.id, display_name: m.display_name }))
  } catch {
    // ignore — co-organizer display is non-critical
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
    // Fetch family members for co-organizer selection
    const membersRes = await getMembers()
    familyMembers.value = (membersRes.data || []).map((m) => ({
      id: String(m.id),
      display_name: m.display_name,
    }))
    await fetchCoOrganizers()
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
.co-organizer-section,
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
  margin-bottom: 8px;
  font-family: monospace;
}
.code-expired,
.code-expires {
  margin-bottom: 12px;
}
.code-actions {
  display: flex;
  gap: 8px;
  justify-content: center;
  margin-top: 8px;
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
.participant-actions {
  display: flex;
  gap: 4px;
}
.co-organizer-list {
  padding: 8px 16px;
}
.co-organizer-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color, #ebedf0);
}
.co-organizer-item:last-child {
  border-bottom: none;
}
.co-organizer-name {
  font-size: 14px;
  color: var(--text-primary);
}
.empty-hint {
  padding: 12px 16px;
  font-size: 13px;
  color: var(--text-secondary);
}
</style>
