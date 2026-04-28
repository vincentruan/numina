import { computed } from 'vue'
import { useSettingsStore } from '@/stores/settings'

export function usePrivacy() {
  const settingsStore = useSettingsStore()

  const isHidden = computed(() => settingsStore.privacyHidden)

  function toggle() {
    settingsStore.togglePrivacy()
  }

  function formatAmount(value: number | null | undefined, prefix = '¥'): string {
    if (value === null || value === undefined) return `${prefix}--`
    if (settingsStore.privacyHidden) return '****'
    return `${prefix}${value.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  return { isHidden, toggle, formatAmount }
}
