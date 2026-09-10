import { ref, onMounted } from 'vue'

const DISMISS_KEY = 'pwa_install_dismissed_at'
const DISMISS_DAYS = 7

export function useInstallPrompt() {
  const canInstall = ref(false)
  let deferredPrompt: BeforeInstallPromptEvent | null = null

  function isDismissedRecently(): boolean {
    const dismissed = localStorage.getItem(DISMISS_KEY)
    if (!dismissed) return false
    const dismissedAt = new Date(dismissed).getTime()
    return Date.now() - dismissedAt < DISMISS_DAYS * 24 * 60 * 60 * 1000
  }

  async function promptInstall(): Promise<boolean> {
    if (!deferredPrompt) return false
    await deferredPrompt.prompt()
    const { outcome } = await deferredPrompt.userChoice
    deferredPrompt = null
    canInstall.value = false
    if (outcome === 'dismissed') {
      localStorage.setItem(DISMISS_KEY, new Date().toISOString())
    }
    return outcome === 'accepted'
  }

  function dismissInstall() {
    localStorage.setItem(DISMISS_KEY, new Date().toISOString())
    canInstall.value = false
  }

  onMounted(() => {
    if (window.matchMedia('(display-mode: standalone)').matches) return
    if (/iPad|iPhone|iPod/.test(navigator.userAgent)) return
    if (isDismissedRecently()) return

    const handler = (e: BeforeInstallPromptEvent) => {
      e.preventDefault()
      deferredPrompt = e
      canInstall.value = true
    }
    window.addEventListener('beforeinstallprompt', handler)
  })

  return { canInstall, promptInstall, dismissInstall }
}
