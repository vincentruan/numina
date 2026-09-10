import { registerSW } from 'virtual:pwa-register'
import { showToast } from 'vant'

const updateSW = registerSW({
  immediate: true,
  onRegistered(r) {
    if (!r) return
    setInterval(() => { r.update() }, 60 * 60 * 1000)
  },
  onNeedRefresh() {
    showToast({
      message: 'New version available',
      duration: 5000,
      forbidClick: true,
    })
    setTimeout(() => {
      updateSW()
    }, 3000)
  },
})
