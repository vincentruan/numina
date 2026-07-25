const COOKIE_NAME = 'numina_device_id'
const LS_KEY = 'numina_device_id'

export function readDeviceId(): string | null {
  const match = document.cookie.match(/(?:^|; )numina_device_id=([^;]+)/)
  if (match) return decodeURIComponent(match[1])
  try {
    return localStorage.getItem(LS_KEY)
  } catch {
    return null
  }
}

export function writeDeviceId(deviceId: string): void {
  const maxAge = 90 * 24 * 3600
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(deviceId)}; path=/; max-age=${maxAge}; samesite=lax`
  try {
    localStorage.setItem(LS_KEY, deviceId)
  } catch {
    // localStorage unavailable (private mode, quota exceeded) — cookie is primary
  }
}

export function clearDeviceId(): void {
  document.cookie = `${COOKIE_NAME}=; path=/; max-age=0`
  try {
    localStorage.removeItem(LS_KEY)
  } catch {
    // ignore
  }
}
