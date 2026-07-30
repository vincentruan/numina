import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// vi.hoisted runs before vi.mock factories (both are hoisted, but vi.hoisted
// is hoisted *first*), so we can safely reference these in the mock factories.
const { showNotifyMock, familyState, authState } = vi.hoisted(() => ({
  showNotifyMock: vi.fn(),
  familyState: {
    members: [] as Array<{ id: string }>,
    family: null as { custom_title?: string; name: string } | null,
  },
  authState: {
    user: null as { id: string } | null,
  },
}))

vi.mock('vant', () => ({
  showNotify: showNotifyMock,
}))

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (!params) return key
      // Interpolate any {placeholder} tokens; if none, append params as :key=val
      const interpolated = key.replace(/\{(\w+)\}/g, (_, k) => String(params[k] ?? `{${k}}`))
      if (interpolated === key) {
        // No placeholder found — append params as a debug suffix so tests can
        // assert the composable passed the correct payload.
        const suffix = Object.entries(params).map(([k, v]) => `${k}=${String(v)}`).join(',')
        return `${key}:${suffix}`
      }
      return interpolated
    },
  }),
}))

vi.mock('@/stores/family', () => ({
  useFamilyStore: () => ({
    members: familyState.members,
    family: familyState.family,
  }),
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    user: authState.user,
  }),
}))

import { useMemberNotify } from '../useMemberNotify'

const STORAGE_KEY = 'numina:family_snapshot:u1'

describe('useMemberNotify', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.removeItem(STORAGE_KEY)
    familyState.members = []
    familyState.family = null
    authState.user = null
  })

  afterEach(() => {
    localStorage.removeItem(STORAGE_KEY)
  })

  describe('notifyConfigChange', () => {
    it('calls showNotify with primary type and default i18n message', () => {
      const { notifyConfigChange } = useMemberNotify()
      notifyConfigChange()
      expect(showNotifyMock).toHaveBeenCalledWith({
        type: 'primary',
        message: 'notify.configChanged',
        duration: 3000,
      })
    })

    it('uses a custom message when provided', () => {
      const { notifyConfigChange } = useMemberNotify()
      notifyConfigChange('自定义消息')
      expect(showNotifyMock).toHaveBeenCalledWith({
        type: 'primary',
        message: '自定义消息',
        duration: 3000,
      })
    })

    it('auto-dismisses after 3000ms (duration field)', () => {
      const { notifyConfigChange } = useMemberNotify()
      notifyConfigChange()
      const call = showNotifyMock.mock.calls[0][0]
      expect(call.duration).toBe(3000)
    })
  })

  describe('notifyFamilyEvent', () => {
    it('fires memberDeactivated with interpolated name', () => {
      const { notifyFamilyEvent } = useMemberNotify()
      notifyFamilyEvent('memberDeactivated', { name: '小明' })
      expect(showNotifyMock).toHaveBeenCalledWith({
        type: 'primary',
        message: 'notify.memberDeactivated:name=小明',
        duration: 3000,
      })
    })

    it('fires memberJoined without name', () => {
      const { notifyFamilyEvent } = useMemberNotify()
      notifyFamilyEvent('memberJoined')
      expect(showNotifyMock).toHaveBeenCalledWith({
        type: 'primary',
        message: 'notify.memberJoined',
        duration: 3000,
      })
    })
  })

  describe('multiple notifications do not stack', () => {
    it('each call replaces the previous notify (no queue in showNotify)', () => {
      const { notifyConfigChange } = useMemberNotify()
      notifyConfigChange('first')
      notifyConfigChange('second')
      // showNotify is called twice; Vant internally replaces the previous one.
      expect(showNotifyMock).toHaveBeenCalledTimes(2)
      expect(showNotifyMock.mock.calls[1][0].message).toBe('second')
    })
  })

  describe('checkFamilyChanges (passive page-entry check)', () => {
    it('returns false and does not notify when no user is logged in', () => {
      authState.user = null
      familyState.family = { name: 'Test' }
      const { checkFamilyChanges } = useMemberNotify()
      expect(checkFamilyChanges()).toBe(false)
      expect(showNotifyMock).not.toHaveBeenCalled()
    })

    it('returns false and does not notify when no family is loaded', () => {
      authState.user = { id: 'u1' }
      familyState.family = null
      const { checkFamilyChanges } = useMemberNotify()
      expect(checkFamilyChanges()).toBe(false)
      expect(showNotifyMock).not.toHaveBeenCalled()
    })

    it('on first visit (no snapshot), baselines silently without notifying', () => {
      authState.user = { id: 'u1' }
      familyState.family = { name: 'Test', custom_title: 'My Family' }
      familyState.members = [{ id: 'm1' }, { id: 'm2' }]
      const { checkFamilyChanges } = useMemberNotify()
      expect(checkFamilyChanges()).toBe(false)
      expect(showNotifyMock).not.toHaveBeenCalled()
      // Snapshot should be persisted.
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY)!)
      expect(stored.memberCount).toBe(2)
      expect(stored.familyTitle).toBe('My Family')
    })

    it('returns false when snapshot matches current state', () => {
      authState.user = { id: 'u1' }
      familyState.family = { name: 'Test' }
      familyState.members = [{ id: 'm1' }]
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        memberCount: 1,
        memberIds: ['m1'],
        familyTitle: 'Test',
      }))
      const { checkFamilyChanges } = useMemberNotify()
      expect(checkFamilyChanges()).toBe(false)
      expect(showNotifyMock).not.toHaveBeenCalled()
    })

    it('notifies and updates snapshot when member count differs', () => {
      authState.user = { id: 'u1' }
      familyState.family = { name: 'Test' }
      familyState.members = [{ id: 'm1' }, { id: 'm2' }]
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        memberCount: 1,
        memberIds: ['m1'],
        familyTitle: 'Test',
      }))
      const { checkFamilyChanges } = useMemberNotify()
      expect(checkFamilyChanges()).toBe(true)
      expect(showNotifyMock).toHaveBeenCalledWith({
        type: 'primary',
        message: 'notify.configChanged',
        duration: 3000,
      })
      // Snapshot is refreshed.
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY)!)
      expect(stored.memberCount).toBe(2)
    })

    it('notifies when family title differs', () => {
      authState.user = { id: 'u1' }
      familyState.family = { name: 'Test', custom_title: 'New Title' }
      familyState.members = []
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        memberCount: 0,
        memberIds: [],
        familyTitle: 'Old Title',
      }))
      const { checkFamilyChanges } = useMemberNotify()
      expect(checkFamilyChanges()).toBe(true)
      expect(showNotifyMock).toHaveBeenCalledTimes(1)
    })
  })

  describe('markFamilySnapshot', () => {
    it('persists current family state to localStorage', () => {
      authState.user = { id: 'u1' }
      familyState.family = { name: 'Fam', custom_title: 'T' }
      familyState.members = [{ id: 'a' }, { id: 'b' }]
      const { markFamilySnapshot } = useMemberNotify()
      markFamilySnapshot()
      const stored = JSON.parse(localStorage.getItem(STORAGE_KEY)!)
      expect(stored.memberCount).toBe(2)
      expect(stored.familyTitle).toBe('T')
      expect(stored.memberIds).toEqual(['a', 'b'])
    })
  })
})
