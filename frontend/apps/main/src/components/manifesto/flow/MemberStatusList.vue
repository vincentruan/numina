<template>
  <div class="member-status-list">
    <div
      v-for="member in members"
      :key="member.userId"
      class="member-status-item"
      :class="{
        'member-status-item--me': member.isCurrentUser,
        'member-status-item--pending': member.status === 'pending_sign' || member.status === 'pending_confirm',
      }"
    >
      <span class="member-status-item__name">
        {{ member.displayName }}
        <van-tag v-if="member.isCurrentUser" type="primary" class="member-status-item__me-tag">
          {{ t('manifesto.flow.me') }}
        </van-tag>
      </span>
      <van-tag
        :type="tagType(member.status)"
        size="medium"
        plain
        class="member-status-item__tag"
      >
        {{ statusLabel(member.status, member.role) }}
      </van-tag>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { FlowMemberState, MemberSigningStatus } from '@/types/manifesto'

defineProps<{
  members: FlowMemberState[]
}>()

const { t } = useI18n()

function tagType(status: MemberSigningStatus): 'success' | 'danger' | 'warning' | 'default' {
  switch (status) {
    case 'signed':
    case 'confirmed':
      return 'success'
    case 'rejected':
      return 'danger'
    case 'expired':
      return 'warning'
    default:
      return 'default'
  }
}

function statusLabel(status: MemberSigningStatus, role: string): string {
  const isChild = role === 'child'
  switch (status) {
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
</script>

<style scoped>
.member-status-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.member-status-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 13px;
  gap: 8px;
}

.member-status-item--me {
  background: rgba(100, 108, 255, 0.08);
}

.member-status-item--pending.member-status-item--me {
  background: rgba(100, 108, 255, 0.12);
  font-weight: 500;
}

.member-status-item__name {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-primary, #0a0a0a);
  min-width: 0;
  flex: 1;
}

.member-status-item__me-tag {
  flex-shrink: 0;
}

.member-status-item__tag {
  flex-shrink: 0;
}
</style>
