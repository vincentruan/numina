import { ref, watchEffect } from 'vue'

const isDark = ref(
  typeof window !== 'undefined' && (
    localStorage.getItem('theme') === 'dark' ||
    (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches)
  )
)

if (typeof window !== 'undefined') {
  watchEffect(() => {
    document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
    localStorage.setItem('theme', isDark.value ? 'dark' : 'light')
  })

  // Sync with OS preference changes
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
    if (!localStorage.getItem('theme')) {
      isDark.value = e.matches
    }
  })
}

export function useDarkMode() {
  function toggle() {
    isDark.value = !isDark.value
  }
  return { isDark, toggle }
}
