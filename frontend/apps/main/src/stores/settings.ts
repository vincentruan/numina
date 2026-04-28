import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

type Theme = 'light' | 'dark' | 'system'

const PRIVACY_KEY = 'numina_privacy_hidden'

export const useSettingsStore = defineStore('settings', () => {
  const theme = ref<Theme>((localStorage.getItem('theme') as Theme) || 'system')
  const privacyHidden = ref(localStorage.getItem(PRIVACY_KEY) === 'true')

  watch(theme, (val) => {
    localStorage.setItem('theme', val)
  })

  function setTheme(val: Theme) {
    theme.value = val
  }

  function togglePrivacy() {
    privacyHidden.value = !privacyHidden.value
    localStorage.setItem(PRIVACY_KEY, String(privacyHidden.value))
  }

  return { theme, setTheme, privacyHidden, togglePrivacy }
})
