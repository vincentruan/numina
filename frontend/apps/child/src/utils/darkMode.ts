import { ref, watchEffect } from 'vue'

type ThemeMode = 'light' | 'dark' | 'system'

function getStoredMode(): ThemeMode {
  const v = localStorage.getItem('theme-mode')
  if (v === 'light' || v === 'dark' || v === 'system') return v
  // Migrate legacy 'theme' key
  const legacy = localStorage.getItem('theme')
  if (legacy === 'dark') return 'dark'
  if (legacy === 'light') return 'light'
  return 'system'
}

function resolveIsDark(mode: ThemeMode): boolean {
  if (mode === 'dark') return true
  if (mode === 'light') return false
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

const themeMode = ref<ThemeMode>(typeof window !== 'undefined' ? getStoredMode() : 'system')
const isDark = ref(typeof window !== 'undefined' ? resolveIsDark(themeMode.value) : false)

if (typeof window !== 'undefined') {
  watchEffect(() => {
    isDark.value = resolveIsDark(themeMode.value)
    document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
    localStorage.setItem('theme-mode', themeMode.value)
  })

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (themeMode.value === 'system') {
      isDark.value = resolveIsDark('system')
      document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
    }
  })
}

export function useDarkMode() {
  function setMode(mode: ThemeMode) {
    themeMode.value = mode
  }
  function toggle() {
    themeMode.value = isDark.value ? 'light' : 'dark'
  }
  return { isDark, themeMode, setMode, toggle }
}
