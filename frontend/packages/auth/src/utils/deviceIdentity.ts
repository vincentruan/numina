const COOKIE_NAME = 'numina_device_id'
const LS_KEY = '_numina_device_id'

export function readDeviceId(): string | null {
  // Cookie first
  const match = document.cookie.match(/(?:^|; )numina_device_id=([^;]+)/)
  if (match) {
    const value = decodeURIComponent(match[1])
    localStorage.setItem(LS_KEY, value)
    return value
  }
  // localStorage fallback
  return localStorage.getItem(LS_KEY)
}

export function writeDeviceId(deviceId: string): void {
  localStorage.setItem(LS_KEY, deviceId)
}

export function clearDeviceId(): void {
  localStorage.removeItem(LS_KEY)
  document.cookie = `${COOKIE_NAME}=; Path=/; Max-Age=0`
}
