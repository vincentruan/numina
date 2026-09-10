import { registerSW } from 'virtual:pwa-register'
import { showToast } from 'vant'

// Register the service worker with prompt-based updates.
// The SW checks for updates on page load; when a new version is found,
// the 'needRefresh' callback fires and we can prompt the user.
const updateSW = registerSW({
  immediate: true,
  onRegistered(r) {
    if (!r) return
    // Periodically check for updates every 60 minutes
    setInterval(() => { r.update() }, 60 * 60 * 1000)
  },
  onNeedRefresh() {
    // New SW available — prompt user to refresh
    showToast({
      message: 'New version available',
      duration: 5000,
      forbidClick: true,
    })
    // Auto-update after a short delay
    setTimeout(() => {
      updateSW()
    }, 3000)
  },
})
