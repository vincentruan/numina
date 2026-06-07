import { showLoadingToast, closeToast } from 'vant'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

let loadingCount = 0

/**
 * Show a loading toast with reference counting.
 *
 * NOTE: closeToast() closes ALL toasts, not just the loading toast.
 * This is a Vant API limitation. If other toasts (success/error) are shown
 * during loading, they will be closed when hideLoading() is called.
 * For scenarios requiring concurrent toasts, consider using a dedicated
 * loading overlay instead of the toast system.
 */
export function showLoading(message?: string): void {
  loadingCount++
  if (loadingCount === 1) {
    showLoadingToast({ message: message ?? t('common.loading'), forbidClick: true, duration: 0 })
  }
}

/**
 * Hide the loading toast when refcount reaches zero.
 * Safe to call without prior showLoading() (no-op when count is already 0).
 */
export function hideLoading(): void {
  loadingCount = Math.max(0, loadingCount - 1)
  if (loadingCount === 0) {
    closeToast()
  }
}
