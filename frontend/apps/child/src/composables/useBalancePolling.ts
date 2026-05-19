/**
 * Balance polling composable.
 * Provides long polling for coin balance with Page Visibility API optimization.
 * Uses singleton pattern to share polling instance across multiple pages.
 */

import { onMounted, onUnmounted, ref, type Ref } from 'vue'
import { getCoinBalance } from '@/api/coins'

interface UseBalancePollingOptions {
  intervalMs?: number // Default: 60000 (1 minute)
  enabled?: boolean // Default: true
}

interface UseBalancePollingReturn {
  balance: Ref<number>
  isLoading: Ref<boolean>
  error: Ref<string | null>
  start: () => void
  stop: () => void
  refresh: () => Promise<void>
}

// Singleton state shared across all consumers
let _pollingInterval: ReturnType<typeof setInterval> | null = null
let _balanceRef: Ref<number> = ref(0)
let _isLoadingRef: Ref<boolean> = ref(false)
let _errorRef: Ref<string | null> = ref(null)
let _consumerCount = 0
let _lastFetchTime = 0

function _startPolling(intervalMs: number) {
  if (_pollingInterval) return // Already running

  const fetchBalance = async () => {
    // Skip fetch if recently fetched (debounce within 5s)
    const now = Date.now()
    if (now - _lastFetchTime < 5000) return

    _isLoadingRef.value = true
    try {
      const bal = await getCoinBalance()
      _balanceRef.value = bal
      _errorRef.value = null
      _lastFetchTime = now
    } catch (e) {
      _errorRef.value = 'Failed to fetch balance'
      // Silent retry on next interval
    } finally {
      _isLoadingRef.value = false
    }
  }

  // Initial fetch
  fetchBalance()

  // Start interval
  _pollingInterval = setInterval(fetchBalance, intervalMs)
}

function _stopPolling() {
  if (_pollingInterval) {
    clearInterval(_pollingInterval)
    _pollingInterval = null
  }
}

function _handleVisibilityChange(intervalMs: number) {
  if (document.visibilityState === 'hidden') {
    _stopPolling()
  } else if (_consumerCount > 0) {
    _startPolling(intervalMs)
  }
}

export function useBalancePolling(options?: UseBalancePollingOptions): UseBalancePollingReturn {
  const intervalMs = options?.intervalMs ?? 60000
  const enabled = options?.enabled ?? true

  const refresh = async () => {
    _isLoadingRef.value = true
    try {
      const bal = await getCoinBalance()
      _balanceRef.value = bal
      _errorRef.value = null
      _lastFetchTime = Date.now()
    } catch (e) {
      _errorRef.value = 'Failed to fetch balance'
    } finally {
      _isLoadingRef.value = false
    }
  }

  const start = () => {
    _consumerCount++
    if (_consumerCount === 1) {
      // First consumer: start polling and add visibility listener
      _startPolling(intervalMs)
      document.addEventListener('visibilitychange', () => _handleVisibilityChange(intervalMs))
    }
  }

  const stop = () => {
    _consumerCount--
    if (_consumerCount <= 0) {
      _consumerCount = 0
      // Last consumer: stop polling and remove visibility listener
      _stopPolling()
      document.removeEventListener('visibilitychange', () => _handleVisibilityChange(intervalMs))
    }
  }

  onMounted(() => {
    if (enabled) {
      start()
    }
  })

  onUnmounted(() => {
    stop()
  })

  return {
    balance: _balanceRef,
    isLoading: _isLoadingRef,
    error: _errorRef,
    start,
    stop,
    refresh,
  }
}