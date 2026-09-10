import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useNetwork } from './useNetwork'

const CACHE_NAMES = ['api-dashboard', 'api-assets', 'api-liabilities']

export function useOfflineCache() {
  const { isOnline } = useNetwork()
  const lastCachedAt = ref<Date | null>(null)
  const staleness = ref('')

  async function checkCacheAge() {
    if (isOnline.value) {
      lastCachedAt.value = null
      staleness.value = ''
      return
    }
    for (const name of CACHE_NAMES) {
      try {
        const cache = await caches.open(name)
        const keys = await cache.keys()
        if (keys.length > 0) {
          const response = await cache.match(keys[0])
          const dateHeader = response?.headers.get('date')
          if (dateHeader) {
            const cachedDate = new Date(dateHeader)
            lastCachedAt.value = cachedDate
            const minutes = Math.floor((Date.now() - cachedDate.getTime()) / 60000)
            if (minutes < 60) {
              staleness.value = `${minutes}m`
            } else {
              staleness.value = `${Math.floor(minutes / 60)}h`
            }
            return
          }
        }
      } catch {
        // Cache API not available
      }
    }
  }

  const showStaleness = computed(() => !isOnline.value && staleness.value !== '')

  let intervalId: ReturnType<typeof setInterval> | null = null

  onMounted(() => {
    checkCacheAge()
    intervalId = setInterval(checkCacheAge, 60000)
  })

  onUnmounted(() => {
    if (intervalId) clearInterval(intervalId)
  })

  return { isOnline, showStaleness, staleness, lastCachedAt }
}
