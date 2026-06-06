import { showLoadingToast, closeToast } from 'vant'

let loadingCount = 0

export function showLoading(message = '加载中...'): void {
  loadingCount++
  if (loadingCount === 1) {
    showLoadingToast({ message, forbidClick: true, duration: 0 })
  }
}

export function hideLoading(): void {
  loadingCount = Math.max(0, loadingCount - 1)
  if (loadingCount === 0) {
    closeToast()
  }
}
