import { describe, it, expect } from 'vitest'
import { ref, computed } from 'vue'
import { useManifestoFlow } from '../useManifestoFlow'
import type { Manifesto } from '@/types/manifesto'
import type { User } from '@/types'

function makeUser(overrides: Partial<User> = {}): User {
  return {
    id: '1',
    family_id: '100',
    username: 'user1',
    display_name: 'User 1',
    avatar_color: '#000',
    role: 'owner',
    is_active: true,
    created_at: '2026-01-01T00:00:00Z',
    ...overrides,
  } as User
}

function makeManifesto(overrides: Partial<Manifesto> = {}): Manifesto {
  return {
    id: '1',
    family_id: '100',
    current_version_id: '10',
    status: 'active',
    signing_deadline: null,
    created_by: '1',
    created_at: '2026-01-01T00:00:00Z',
    current_version: {
      id: '10',
      version_number: 1,
      template_id: 'modern',
      title: 'Test',
      body: 'Body',
      change_type: 'initial',
      trackable_clause_indices: null,
      signed_at: null,
      created_by: '1',
      created_at: '2026-01-01T00:00:00Z',
    },
    signatures: [],
    rejections: [],
    ...overrides,
  }
}

describe('useManifestoFlow', () => {
  describe('flowState', () => {
    it('returns draft when status is draft', () => {
      const m = ref(makeManifesto({ status: 'draft' }))
      const members = ref<User[]>([makeUser()])
      const userId = ref<string | null>('1')
      const { flowState } = useManifestoFlow(m, members, userId)
      expect(flowState.value).toBe('draft')
    })

    it('returns rejected when rejections exist', () => {
      const m = ref(makeManifesto({
        rejections: [{ id: '1', user_id: '1', reason: 'no', created_at: '2026-01-01T00:00:00Z' }],
      }))
      const members = ref<User[]>([makeUser()])
      const userId = ref<string | null>('1')
      const { flowState } = useManifestoFlow(m, members, userId)
      expect(flowState.value).toBe('rejected')
    })

    it('returns effective when all adults signed', () => {
      const adults = [makeUser({ id: '1' }), makeUser({ id: '2', role: 'member' })]
      const m = ref(makeManifesto({
        signatures: [
          { id: '1', user_id: '1', signature_data: 'sig', signed_at: '2026-01-01T00:00:00Z' },
          { id: '2', user_id: '2', signature_data: 'sig', signed_at: '2026-01-01T00:00:00Z' },
        ],
      }))
      const members = ref<User[]>(adults)
      const userId = ref<string | null>('1')
      const { flowState } = useManifestoFlow(m, members, userId)
      expect(flowState.value).toBe('effective')
    })

    it('returns expired when deadline passed and not all signed', () => {
      const m = ref(makeManifesto({
        signing_deadline: '2020-01-01T00:00:00Z',
        signatures: [],
      }))
      const members = ref<User[]>([makeUser()])
      const userId = ref<string | null>('1')
      const { flowState } = useManifestoFlow(m, members, userId)
      expect(flowState.value).toBe('expired')
    })

    it('returns signing when active and some pending', () => {
      const m = ref(makeManifesto({
        signing_deadline: '2099-01-01T00:00:00Z',
        signatures: [],
      }))
      const members = ref<User[]>([makeUser()])
      const userId = ref<string | null>('1')
      const { flowState } = useManifestoFlow(m, members, userId)
      expect(flowState.value).toBe('signing')
    })

    it('returns null manifesto as draft', () => {
      const m = ref<Manifesto | null>(null)
      const members = ref<User[]>([])
      const userId = ref<string | null>(null)
      const { flowState } = useManifestoFlow(m, members, userId)
      expect(flowState.value).toBe('draft')
    })
  })

  describe('memberStates', () => {
    it('maps adult without signature to pending_sign', () => {
      const m = ref(makeManifesto())
      const members = ref<User[]>([makeUser({ id: '1', role: 'owner' })])
      const userId = ref<string | null>('1')
      const { memberStates } = useManifestoFlow(m, members, userId)
      expect(memberStates.value[0].status).toBe('pending_sign')
    })

    it('maps child without signature to pending_confirm', () => {
      const m = ref(makeManifesto())
      const members = ref<User[]>([makeUser({ id: '1', role: 'child' })])
      const userId = ref<string | null>('1')
      const { memberStates } = useManifestoFlow(m, members, userId)
      expect(memberStates.value[0].status).toBe('pending_confirm')
    })

    it('maps adult with signature_data to signed', () => {
      const m = ref(makeManifesto({
        signatures: [{ id: '1', user_id: '1', signature_data: 'data', signed_at: '2026-01-01T00:00:00Z' }],
      }))
      const members = ref<User[]>([makeUser({ id: '1' })])
      const userId = ref<string | null>('1')
      const { memberStates } = useManifestoFlow(m, members, userId)
      expect(memberStates.value[0].status).toBe('signed')
    })

    it('maps child with null signature_data to confirmed', () => {
      const m = ref(makeManifesto({
        signatures: [{ id: '1', user_id: '1', signature_data: null, signed_at: '2026-01-01T00:00:00Z' }],
      }))
      const members = ref<User[]>([makeUser({ id: '1', role: 'child' })])
      const userId = ref<string | null>('1')
      const { memberStates } = useManifestoFlow(m, members, userId)
      expect(memberStates.value[0].status).toBe('confirmed')
    })

    it('maps user with rejection to rejected', () => {
      const m = ref(makeManifesto({
        rejections: [{ id: '1', user_id: '1', reason: 'no', created_at: '2026-01-01T00:00:00Z' }],
      }))
      const members = ref<User[]>([makeUser({ id: '1' })])
      const userId = ref<string | null>('1')
      const { memberStates } = useManifestoFlow(m, members, userId)
      expect(memberStates.value[0].status).toBe('rejected')
    })

    it('flags current user with isCurrentUser', () => {
      const m = ref(makeManifesto())
      const members = ref<User[]>([
        makeUser({ id: '1' }),
        makeUser({ id: '2', role: 'member' }),
      ])
      const userId = ref<string | null>('2')
      const { memberStates } = useManifestoFlow(m, members, userId)
      expect(memberStates.value[0].isCurrentUser).toBe(false)
      expect(memberStates.value[1].isCurrentUser).toBe(true)
    })
  })

  describe('canSign / canReject', () => {
    it('canSign is true for pending adult in signing state', () => {
      const m = ref(makeManifesto({
        signing_deadline: '2099-01-01T00:00:00Z',
      }))
      const members = ref<User[]>([makeUser({ id: '1', role: 'owner' })])
      const userId = ref<string | null>('1')
      const { canSign } = useManifestoFlow(m, members, userId)
      expect(canSign.value).toBe(true)
    })

    it('canSign is false when expired', () => {
      const m = ref(makeManifesto({
        signing_deadline: '2020-01-01T00:00:00Z',
      }))
      const members = ref<User[]>([makeUser({ id: '1' })])
      const userId = ref<string | null>('1')
      const { canSign } = useManifestoFlow(m, members, userId)
      expect(canSign.value).toBe(false)
    })

    it('canReject is true for pending adult in signing state', () => {
      const m = ref(makeManifesto({
        signing_deadline: '2099-01-01T00:00:00Z',
      }))
      const members = ref<User[]>([makeUser({ id: '1', role: 'owner' })])
      const userId = ref<string | null>('1')
      const { canReject } = useManifestoFlow(m, members, userId)
      expect(canReject.value).toBe(true)
    })

    it('canReject is false for child role', () => {
      const m = ref(makeManifesto({
        signing_deadline: '2099-01-01T00:00:00Z',
      }))
      const members = ref<User[]>([makeUser({ id: '1', role: 'child' })])
      const userId = ref<string | null>('1')
      const { canReject } = useManifestoFlow(m, members, userId)
      expect(canReject.value).toBe(false)
    })

    it('canReject is false when not signing', () => {
      const m = ref(makeManifesto({ status: 'draft' }))
      const members = ref<User[]>([makeUser({ id: '1' })])
      const userId = ref<string | null>('1')
      const { canReject } = useManifestoFlow(m, members, userId)
      expect(canReject.value).toBe(false)
    })
  })

  describe('signingProgress', () => {
    it('counts only adult members', () => {
      const m = ref(makeManifesto({
        signatures: [
          { id: '1', user_id: '1', signature_data: 'sig', signed_at: '2026-01-01T00:00:00Z' },
          { id: '2', user_id: '3', signature_data: null, signed_at: '2026-01-01T00:00:00Z' },
        ],
      }))
      const members = ref<User[]>([
        makeUser({ id: '1', role: 'owner' }),
        makeUser({ id: '2', role: 'member' }),
        makeUser({ id: '3', role: 'child' }),
      ])
      const userId = ref<string | null>('1')
      const { signingProgress } = useManifestoFlow(m, members, userId)
      expect(signingProgress.value.signed).toBe(1) // only owner (adult) counted
      expect(signingProgress.value.total).toBe(2) // 2 adults
    })
  })

  describe('deadlineInfo', () => {
    it('returns expired when deadline passed', () => {
      const m = ref(makeManifesto({ signing_deadline: '2020-01-01T00:00:00Z' }))
      const members = ref<User[]>([])
      const userId = ref<string | null>(null)
      const { deadlineInfo } = useManifestoFlow(m, members, userId)
      expect(deadlineInfo.value.expired).toBe(true)
      expect(deadlineInfo.value.remaining).toBeNull()
    })

    it('returns remaining time when deadline is future', () => {
      const m = ref(makeManifesto({ signing_deadline: '2099-12-31T23:59:59Z' }))
      const members = ref<User[]>([])
      const userId = ref<string | null>(null)
      const { deadlineInfo } = useManifestoFlow(m, members, userId)
      expect(deadlineInfo.value.expired).toBe(false)
      expect(deadlineInfo.value.remaining).not.toBeNull()
    })

    it('returns not expired when no deadline', () => {
      const m = ref(makeManifesto({ signing_deadline: null }))
      const members = ref<User[]>([])
      const userId = ref<string | null>(null)
      const { deadlineInfo } = useManifestoFlow(m, members, userId)
      expect(deadlineInfo.value.expired).toBe(false)
    })
  })
})
