<template>
  <div class="signing-timeline">
    <!-- Created node -->
    <div class="timeline-node timeline-node--created">
      <div class="timeline-node__indicator">
        <span class="timeline-node__dot timeline-node__dot--gold" />
        <span v-if="!isLastNode('created')" class="timeline-node__line" />
      </div>
      <div class="timeline-node__content">
        <div class="timeline-node__label">
          {{ t('manifesto.flow.versionLabel', { n: currentRound }) }}
          · {{ changeTypeLabel }}
        </div>
        <div class="timeline-node__sub">
          {{ creatorName }} {{ t('manifesto.flow.created') }}
          <span v-if="createdAt" class="timeline-node__date">{{ formatDate(createdAt) }}</span>
        </div>
      </div>
    </div>

    <!-- Signing node (active round) -->
    <div
      v-if="showSigningNode"
      class="timeline-node timeline-node--signing"
      :class="{ 'timeline-node--active': flowState === 'signing' }"
    >
      <div class="timeline-node__indicator">
        <span
          class="timeline-node__dot"
          :class="flowState === 'signing' ? 'timeline-node__dot--pulse' : 'timeline-node__dot--gold'"
        />
        <span v-if="!isLastNode('signing')" class="timeline-node__line" />
      </div>
      <div class="timeline-node__content">
        <div class="timeline-node__label">
          {{ t('manifesto.flow.signing', { n: currentRound }) }}
          <span class="timeline-node__progress">
            ({{ t('manifesto.flow.progress', { signed: signingProgress.signed, total: signingProgress.total }) }})
          </span>
        </div>

        <!-- Deadline info -->
        <div v-if="deadlineInfo.remaining || deadlineInfo.expired" class="timeline-node__deadline">
          <van-icon name="clock-o" size="12" />
          <span v-if="deadlineInfo.expired">{{ t('manifesto.flow.deadlineExpired') }}</span>
          <span v-else>{{ t('manifesto.flow.deadlineRemaining', { time: deadlineInfo.remaining }) }}</span>
        </div>

        <!-- Embedded member status list -->
        <div class="timeline-members">
          <div
            v-for="member in memberStates"
            :key="member.userId"
            class="timeline-member"
            :class="memberClass(member)"
          >
            <span class="timeline-member__icon">{{ memberStatusIcon(member.status) }}</span>
            <span class="timeline-member__name">
              {{ member.displayName }}
              <van-tag
                v-if="member.isCurrentUser"
                type="primary"
                size="mini"
                class="timeline-member__me-tag"
              >
                {{ t('manifesto.flow.me') }}
              </van-tag>
            </span>
            <span class="timeline-member__status">{{ memberStatusLabel(member) }}</span>
            <span v-if="memberDateText(member)" class="timeline-member__date">
              {{ memberDateText(member) }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Rejected node -->
    <div v-if="hasRejection" class="timeline-node timeline-node--rejected">
      <div class="timeline-node__indicator">
        <span class="timeline-node__dot timeline-node__dot--red" />
        <span class="timeline-node__line" />
      </div>
      <div class="timeline-node__content">
        <div class="timeline-node__label timeline-node__label--danger">
          {{ t('manifesto.flow.rejected') }}
        </div>
        <div
          v-for="rej in rejectionList"
          :key="rej.userId"
          class="timeline-node__sub"
        >
          {{ rej.displayName }}
          <span v-if="rej.rejectionReason" class="timeline-node__reason">「{{ rej.rejectionReason }}」</span>
        </div>
      </div>
    </div>

    <!-- Version update bridge -->
    <div v-if="hasRejection" class="timeline-node timeline-node--version-bridge">
      <div class="timeline-node__indicator">
        <span class="timeline-node__dot timeline-node__dot--small" />
        <span class="timeline-node__line timeline-node__line--dashed" />
      </div>
      <div class="timeline-node__content timeline-node__content--muted">
        {{ t('manifesto.flow.versionUpdate') }}
        ({{ t('manifesto.flow.versionLabel', { n: currentRound }) }}
        → {{ t('manifesto.flow.versionLabel', { n: nextVersionNumber }) }})
      </div>
    </div>

    <!-- Effective node -->
    <div v-if="flowState === 'effective'" class="timeline-node timeline-node--effective">
      <div class="timeline-node__indicator">
        <span class="timeline-node__dot timeline-node__dot--green" />
      </div>
      <div class="timeline-node__content">
        <div class="timeline-node__label timeline-node__label--success">
          {{ t('manifesto.flow.effective') }}
        </div>
        <div v-if="effectiveDate" class="timeline-node__sub">
          {{ formatDate(effectiveDate) }}
        </div>
      </div>
    </div>

    <!-- Pending / Expired terminal -->
    <div
      v-if="flowState === 'expired' || (flowState === 'signing' && !hasRejection)"
      class="timeline-node timeline-node--pending"
    >
      <div class="timeline-node__indicator">
        <span class="timeline-node__dot timeline-node__dot--hollow" />
      </div>
      <div class="timeline-node__content timeline-node__content--muted">
        {{ flowState === 'expired' ? t('manifesto.flow.deadlineExpired') : t('manifesto.flow.pendingEffective') }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type {
  FlowState,
  FlowMemberState,
  FlowDeadlineInfo,
  FlowSigningProgress,
  MemberSigningStatus,
} from '@/types/manifesto'

defineOptions({ name: 'SigningTimeline' })

const props = defineProps<{
  flowState: FlowState
  currentRound: number
  memberStates: FlowMemberState[]
  deadlineInfo: FlowDeadlineInfo
  signingProgress: FlowSigningProgress
  creatorName?: string
  changeType?: string
  hasRejection?: boolean
  nextVersionNumber?: number
  createdAt?: string
  effectiveDate?: string
}>()

const { t, locale } = useI18n()

const showSigningNode = computed(() => {
  return props.flowState === 'signing' || props.flowState === 'rejected' || props.flowState === 'expired'
})

/** Ordered list of visible node keys for connector-line logic. */
const visibleNodes = computed(() => {
  const nodes: string[] = ['created']
  if (showSigningNode.value) nodes.push('signing')
  if (props.hasRejection) {
    nodes.push('rejected', 'version-bridge')
  }
  if (props.flowState === 'effective') nodes.push('effective')
  if (props.flowState === 'expired' || (props.flowState === 'signing' && !props.hasRejection)) {
    nodes.push('pending')
  }
  return nodes
})

function isLastNode(key: string): boolean {
  return visibleNodes.value[visibleNodes.value.length - 1] === key
}

const changeTypeLabel = computed(() => {
  const map: Record<string, string> = {
    initial: t('manifesto.flow.changeTypeInitial'),
    minor: t('manifesto.flow.changeTypeMinor'),
    major: t('manifesto.flow.changeTypeMajor'),
  }
  return map[props.changeType ?? 'initial'] ?? t('manifesto.flow.changeTypeInitial')
})

const rejectionList = computed(() => {
  return props.memberStates.filter(m => m.status === 'rejected')
})

function memberStatusIcon(status: MemberSigningStatus): string {
  switch (status) {
    case 'signed':
    case 'confirmed':
      return '✓'
    case 'rejected':
      return '✗'
    case 'expired':
      return '⏰'
    default:
      return '○'
  }
}

function memberClass(member: FlowMemberState): Record<string, boolean> {
  return {
    'timeline-member--signed': member.status === 'signed' || member.status === 'confirmed',
    'timeline-member--rejected': member.status === 'rejected',
    'timeline-member--pending': member.status === 'pending_sign' || member.status === 'pending_confirm',
    'timeline-member--me': member.isCurrentUser,
    'timeline-member--expired': member.status === 'expired',
  }
}

function memberStatusLabel(member: FlowMemberState): string {
  const isChild = member.role === 'child'
  switch (member.status) {
    case 'signed':
      return t('manifesto.memberStatus.signed')
    case 'confirmed':
      return t('manifesto.memberStatus.confirmed')
    case 'pending_sign':
      return isChild ? t('manifesto.memberStatus.pendingConfirm') : t('manifesto.memberStatus.pendingSign')
    case 'pending_confirm':
      return t('manifesto.memberStatus.pendingConfirm')
    case 'rejected':
      return t('manifesto.memberStatus.rejected')
    case 'expired':
      return t('manifesto.memberStatus.expired')
    default:
      return ''
  }
}

function memberDateText(member: FlowMemberState): string {
  if (member.status === 'signed' || member.status === 'confirmed') {
    return member.signedAt ? formatShortDate(member.signedAt) : ''
  }
  if (member.status === 'rejected') {
    return member.rejectedAt ? formatShortDate(member.rejectedAt) : ''
  }
  return ''
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString(locale.value, { year: 'numeric', month: 'long', day: 'numeric' })
}

function formatShortDate(dateStr: string): string {
  const d = new Date(dateStr)
  return d.toLocaleDateString(locale.value, { month: 'short', day: 'numeric' })
}
</script>

<style scoped>
.signing-timeline {
  display: flex;
  flex-direction: column;
  padding: 4px 0;
}

/* ── Node layout ── */
.timeline-node {
  display: flex;
  gap: 12px;
  position: relative;
}

.timeline-node__indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 20px;
  padding-top: 4px;
}

.timeline-node__dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
  z-index: 1;
}

.timeline-node__line {
  width: 2px;
  flex: 1;
  min-height: 16px;
  margin: 4px 0;
  background: var(--text-secondary, #c0c0c0);
  opacity: 0.4;
}

.timeline-node__line--dashed {
  background: none;
  border-left: 2px dashed var(--text-secondary, #c0c0c0);
  width: 0;
  opacity: 0.3;
}

.timeline-node__content {
  flex: 1;
  padding-bottom: 20px;
  min-width: 0;
}

.timeline-node__content--muted {
  color: var(--text-secondary, #616161);
  font-size: 13px;
}

/* ── Label styles ── */
.timeline-node__label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #0a0a0a);
  line-height: 1.4;
}

.timeline-node__label--success {
  color: var(--van-success-color, #07c160);
}

.timeline-node__label--danger {
  color: var(--van-danger-color, #ee0a24);
}

.timeline-node__progress {
  font-weight: 400;
  font-size: 13px;
  color: var(--text-secondary, #616161);
}

.timeline-node__sub {
  font-size: 13px;
  color: var(--text-secondary, #616161);
  margin-top: 2px;
  line-height: 1.4;
}

.timeline-node__date {
  margin-left: 4px;
}

.timeline-node__reason {
  color: var(--van-danger-color, #ee0a24);
  font-style: italic;
}

/* ── Deadline ── */
.timeline-node__deadline {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary, #616161);
  margin-top: 6px;
  padding: 4px 8px;
  background: color-mix(in srgb, var(--van-warning-color, #ff976a) 8%, transparent);
  border-radius: 6px;
  width: fit-content;
}

/* ── Dot variants ── */
.timeline-node__dot--gold {
  background: #c9a84c;
}

.timeline-node__dot--red {
  background: var(--van-danger-color, #ee0a24);
}

.timeline-node__dot--green {
  background: var(--van-success-color, #07c160);
}

.timeline-node__dot--hollow {
  background: transparent;
  border: 2px solid var(--text-secondary, #c0c0c0);
}

.timeline-node__dot--small {
  width: 8px;
  height: 8px;
  background: var(--text-secondary, #c0c0c0);
}

.timeline-node__dot--pulse {
  background: #c9a84c;
  animation: timeline-pulse 2s ease-in-out infinite;
}

@keyframes timeline-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(201, 168, 76, 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(201, 168, 76, 0); }
}

/* ── Active signing node highlight ── */
.timeline-node--active .timeline-node__content {
  background: color-mix(in srgb, #c9a84c 4%, transparent);
  border-radius: 8px;
  padding: 12px;
  margin: -4px -8px 16px;
}

/* ── Embedded member list ── */
.timeline-members {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.timeline-member {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  font-size: 13px;
  transition: background-color 0.2s;
}

.timeline-member--me {
  background: color-mix(in srgb, var(--van-primary-color, #646cff) 8%, transparent);
}

.timeline-member--me.timeline-member--pending {
  background: color-mix(in srgb, var(--van-primary-color, #646cff) 12%, transparent);
  font-weight: 500;
}

.timeline-member__icon {
  width: 18px;
  text-align: center;
  font-size: 12px;
  flex-shrink: 0;
}

.timeline-member--signed .timeline-member__icon {
  color: var(--van-success-color, #07c160);
}

.timeline-member--rejected .timeline-member__icon {
  color: var(--van-danger-color, #ee0a24);
}

.timeline-member--pending .timeline-member__icon {
  color: var(--text-secondary, #999);
}

.timeline-member__name {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-primary, #0a0a0a);
  flex: 1;
  min-width: 0;
}

.timeline-member__me-tag {
  flex-shrink: 0;
}

.timeline-member__status {
  font-size: 12px;
  color: var(--text-secondary, #616161);
  flex-shrink: 0;
}

.timeline-member--signed .timeline-member__status {
  color: var(--van-success-color, #07c160);
}

.timeline-member--rejected .timeline-member__status {
  color: var(--van-danger-color, #ee0a24);
}

.timeline-member__date {
  font-size: 11px;
  color: var(--text-secondary, #999);
  flex-shrink: 0;
}

/* ── Version bridge ── */
.timeline-node--version-bridge .timeline-node__content {
  padding-bottom: 12px;
}

/* ── Reduced motion ── */
@media (prefers-reduced-motion: reduce) {
  .timeline-node__dot--pulse {
    animation: none;
  }
}

/* ── Dark mode adjustments ── */
:global([data-theme="dark"]) .timeline-node__dot--gold {
  background: #d4b86a;
}

:global([data-theme="dark"]) .timeline-node__dot--pulse {
  background: #d4b86a;
  animation-name: timeline-pulse-dark;
}

@keyframes timeline-pulse-dark {
  0%, 100% { box-shadow: 0 0 0 0 rgba(212, 184, 106, 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(212, 184, 106, 0); }
}
</style>
