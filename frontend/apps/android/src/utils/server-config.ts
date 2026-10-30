/**
 * Server URL persistence and validation for the Numina Android shell.
 *
 * Uses Capacitor Preferences (backed by SharedPreferences on Android)
 * to store the user's self-hosted server URL.
 */
import { Preferences } from '@capacitor/preferences'

const SERVER_URL_KEY = 'numina_server_url'
const ADVANCED_MODE_KEY = 'numina_advanced_mode'

/** Strip trailing slashes so every stored or compared URL has one canonical form. */
export function normalizeServerUrl(url: string): string {
  return url.replace(/\/+$/, '')
}

/** Read the saved server URL (trimmed, no trailing slash). */
export async function getServerUrl(): Promise<string | null> {
  const { value } = await Preferences.get({ key: SERVER_URL_KEY })
  return value ? normalizeServerUrl(value) : null
}

/** Persist the server URL. */
export async function setServerUrl(url: string): Promise<void> {
  await Preferences.set({
    key: SERVER_URL_KEY,
    value: normalizeServerUrl(url),
  })
}

/** Clear the saved server URL (for re-configuration). */
export async function clearServerUrl(): Promise<void> {
  await Preferences.remove({ key: SERVER_URL_KEY })
}

/** Whether "advanced mode" (allows LAN HTTP) is enabled. */
export async function isAdvancedMode(): Promise<boolean> {
  const { value } = await Preferences.get({ key: ADVANCED_MODE_KEY })
  return value === 'true'
}

/** Toggle advanced mode. */
export async function setAdvancedMode(enabled: boolean): Promise<void> {
  await Preferences.set({
    key: ADVANCED_MODE_KEY,
    value: String(enabled),
  })
}

/** Validate that the server URL is reachable by calling /api/health. */
export async function validateServer(url: string): Promise<boolean> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 8000)
  try {
    const resp = await fetch(`${url}/api/health`, {
      signal: controller.signal,
      // Include credentials so cookies from a prior session count as proof of life
      credentials: 'include',
    })
    return resp.ok
  } catch {
    return false
  } finally {
    clearTimeout(timeout)
  }
}

/**
 * Classify a server URL for UX messaging.
 * - 'https': secure, full-featured
 * - 'http-lan': private network, works but not recommended for production
 * - 'http-public': cleartext on a public domain — dangerous
 * - 'localhost': dev-only
 */
export function classifyUrl(raw: string): 'https' | 'http-lan' | 'http-public' | 'localhost' | 'invalid' {
  let parsed: URL
  try {
    parsed = new URL(raw)
  } catch {
    return 'invalid'
  }

  if (parsed.protocol === 'https:') return 'https'
  if (parsed.protocol !== 'http:') return 'invalid'

  const host = parsed.hostname.toLowerCase()
  // WHATWG URL keeps the brackets on IPv6 literals, so "[::1]" is the form to match.
  if (host === 'localhost' || host === '127.0.0.1' || host === '[::1]') return 'localhost'
  if (
    host.startsWith('192.168.') ||
    host.startsWith('10.') ||
    host.endsWith('.local') ||
    host.endsWith('.lan') ||
    /^172\.(1[6-9]|2\d|3[01])\./.test(host)
  ) {
    return 'http-lan'
  }
  return 'http-public'
}
