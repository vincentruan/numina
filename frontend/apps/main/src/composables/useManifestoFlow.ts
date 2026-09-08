import { computed, type Ref } from 'vue'
import type {
  Manifesto,
  FlowState,
  FlowMemberState,
  FlowDeadlineInfo,
  FlowSigningProgress,
  MemberSigningStatus,
} from '@/types/manifesto'
import type { User } from '@/types'

export function useManifestoFlow(
  manifesto: Ref<Manifesto | null>,
  members: Ref<User[]>,
  currentUserId: Ref<string | null>,
) {
  const flowState = computed<FlowState>(() => {
    const m = manifesto.value
    if (!m) return 'draft'
    if (m.status === 'draft') return 'draft'

    // Has rejections → rejected
    if (m.rejections && m.rejections.length > 0) return 'rejected'

    // All adult members signed/confirmed → effective
    const adultMembers = members.value.filter(mem => mem.role !== 'child')
    if (adultMembers.length > 0) {
      const allSigned = adultMembers.every(mem =>
        m.signatures.some(sig => sig.user_id === mem.id),
      )
      if (allSigned) return 'effective'
    }

    // Deadline passed and not all signed → expired
    if (m.signing_deadline) {
      const deadline = new Date(m.signing_deadline).getTime()
      if (deadline < Date.now()) return 'expired'
    }

    return 'signing'
  })

  const memberStates = computed<FlowMemberState[]>(() => {
    const m = manifesto.value
    if (!m) return []

    const sigMap = new Map(m.signatures.map(s => [s.user_id, s]))
    const rejMap = new Map((m.rejections ?? []).map(r => [r.user_id, r]))
    const isExpired = flowState.value === 'expired'

    return members.value.map(mem => {
      const sig = sigMap.get(mem.id)
      const rej = rejMap.get(mem.id)
      const isChild = mem.role === 'child'
      const isCurrentUser = currentUserId.value !== null && mem.id === currentUserId.value

      let status: MemberSigningStatus
      if (rej) {
        status = 'rejected'
      } else if (sig) {
        // null signature_data = tap-to-consent (child confirmation)
        status = isChild ? 'confirmed' : 'signed'
      } else if (isExpired) {
        status = 'expired'
      } else {
        status = isChild ? 'pending_confirm' : 'pending_sign'
      }

      return {
        userId: mem.id,
        displayName: mem.display_name,
        role: mem.role,
        status,
        isCurrentUser,
        signatureData: sig?.signature_data,
        rejectionReason: rej?.reason,
      }
    })
  })

  const currentRound = computed<number>(() => {
    return manifesto.value?.current_version?.version_number ?? 1
  })

  const signingProgress = computed<FlowSigningProgress>(() => {
    const m = manifesto.value
    if (!m) return { signed: 0, total: 0 }
    const adultMembers = members.value.filter(mem => mem.role !== 'child')
    const signedCount = adultMembers.filter(mem =>
      m.signatures.some(sig => sig.user_id === mem.id),
    ).length
    return { signed: signedCount, total: adultMembers.length }
  })

  const deadlineInfo = computed<FlowDeadlineInfo>(() => {
    const m = manifesto.value
    if (!m?.signing_deadline) return { expired: false, remaining: null }

    const deadline = new Date(m.signing_deadline).getTime()
    const now = Date.now()
    if (deadline <= now) return { expired: true, remaining: null }

    const diff = deadline - now
    const days = Math.floor(diff / (1000 * 60 * 60 * 24))
    const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60))

    let remaining: string
    if (days > 0) {
      remaining = `${days}d ${hours}h`
    } else {
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60))
      remaining = `${hours}h ${minutes}m`
    }

    return { expired: false, remaining }
  })

  const currentUserState = computed<FlowMemberState | null>(() => {
    return memberStates.value.find(ms => ms.isCurrentUser) ?? null
  })

  const canSign = computed<boolean>(() => {
    const state = currentUserState.value
    if (!state) return false
    if (flowState.value !== 'signing') return false
    if (state.status !== 'pending_sign' && state.status !== 'pending_confirm') return false
    if (deadlineInfo.value.expired) return false
    return true
  })

  const canReject = computed<boolean>(() => {
    const state = currentUserState.value
    if (!state) return false
    if (flowState.value !== 'signing') return false
    if (state.status !== 'pending_sign' && state.status !== 'pending_confirm') return false
    if (deadlineInfo.value.expired) return false
    // Only adults can reject
    if (state.role === 'child') return false
    return true
  })

  return {
    flowState,
    memberStates,
    currentRound,
    signingProgress,
    deadlineInfo,
    currentUserState,
    canSign,
    canReject,
  }
}
