import { ref, onMounted, onUnmounted } from 'vue'

const isOnline = ref(navigator.onLine)

function handleOnline() {
  isOnline.value = true
}

function handleOffline() {
  isOnline.value = false
}

export function useNetwork() {
  onMounted(() => {
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)
  })

  onUnmounted(() => {
    window.removeEventListener('online', handleOnline)
    window.removeEventListener('offline', handleOffline)
  })

  return { isOnline }
}
