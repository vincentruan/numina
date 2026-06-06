const COOKIE_NAME = 'numina_device_id'

export function readDeviceId(): string | null {
  const match = document.cookie.match(/(?:^|; )numina_device_id=([^;]+)/)
  return match ? decodeURIComponent(match[1]) : null
}

export function writeDeviceId(deviceId: string): void {
  const maxAge = 90 * 24 * 3600
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(deviceId)}; path=/; max-age=${maxAge}; samesite=lax`
}

export function clearDeviceId(): void {
  document.cookie = `${COOKIE_NAME}=; path=/; max-age=0`
}
