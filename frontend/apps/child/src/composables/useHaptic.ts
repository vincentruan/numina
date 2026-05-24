/**
 * 触觉反馈封装。
 * iOS Safari 没有 navigator.vibrate → 静默 no-op；任何抛错也吞掉。
 */

export function tryVibrate(pattern: number | number[]): boolean {
  if (typeof navigator === 'undefined') return false
  if (typeof navigator.vibrate !== 'function') return false
  try {
    return navigator.vibrate(pattern)
  } catch {
    return false
  }
}

export function useHaptic() {
  return {
    vibrate: tryVibrate,
  }
}
