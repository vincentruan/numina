import { showNotify } from 'vant'
import { useI18n } from 'vue-i18n'
import { useFamilyStore } from '@/stores/family'
import { useAuthStore } from '@/stores/auth'

const STORAGE_KEY = 'numina:family_snapshot'

interface FamilySnapshot {
  memberCount: number
  memberIds: string[]
  familyTitle: string
}

function readSnapshot(): FamilySnapshot | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as FamilySnapshot) : null
  } catch {
    return null
  }
}

function writeSnapshot(snap: FamilySnapshot) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(snap))
  } catch {
    // Storage full / blocked — non-critical
  }
}

function currentSnapshot(familyStore: ReturnType<typeof useFamilyStore>): FamilySnapshot {
  return {
    memberCount: familyStore.members.length,
    memberIds: familyStore.members.map((m) => m.id).sort(),
    familyTitle: familyStore.family?.custom_title || familyStore.family?.name || '',
  }
}

function snapshotsEqual(a: FamilySnapshot, b: FamilySnapshot): boolean {
  return (
    a.memberCount === b.memberCount &&
    a.familyTitle === b.familyTitle &&
    a.memberIds.length === b.memberIds.length &&
    a.memberIds.every((id, i) => id === b.memberIds[i])
  )
}

export function useMemberNotify() {
  const { t } = useI18n()

  /**
   * Show a top-bar notification for a family config change.
   * Auto-dismisses after 3000ms; subsequent calls replace the previous one.
   */
  function notifyConfigChange(message?: string) {
    showNotify({
      type: 'primary',
      message: message ?? t('notify.configChanged'),
      duration: 3000,
    })
  }

  /**
   * Show a top-bar notification for a family event (member join, deactivation, etc.).
   */
  function notifyFamilyEvent(type: 'memberJoined' | 'memberDeactivated', payload?: { name?: string }) {
    const key = `notify.${type}` as const
    const message = payload?.name ? t(key, { name: payload.name }) : t(key)
    showNotify({ type: 'primary', message, duration: 3000 })
  }

  /**
   * Mark the current family state as "seen" so passive checks have a baseline.
   * Call after any owner action that mutates family state.
   */
  function markFamilySnapshot() {
    const familyStore = useFamilyStore()
    writeSnapshot(currentSnapshot(familyStore))
  }

  /**
   * Passive page-entry check: compare the current family state with the last
   * snapshot. If they differ, show `notifyConfigChange` and update the snapshot.
   * Returns true if a notification was fired.
   */
  function checkFamilyChanges(): boolean {
    const familyStore = useFamilyStore()
    const authStore = useAuthStore()

    // No family / not logged in — nothing to compare.
    if (!familyStore.family || !authStore.user) return false

    const prev = readSnapshot()
    const curr = currentSnapshot(familyStore)

    if (!prev) {
      // First visit — baseline only, no notification.
      writeSnapshot(curr)
      return false
    }

    if (snapshotsEqual(prev, curr)) return false

    // Something changed — notify and refresh the baseline.
    writeSnapshot(curr)
    notifyConfigChange()
    return true
  }

  return {
    notifyConfigChange,
    notifyFamilyEvent,
    markFamilySnapshot,
    checkFamilyChanges,
  }
}
