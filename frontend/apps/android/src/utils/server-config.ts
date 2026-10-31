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
    // No credentials: the shell runs from Capacitor's https://localhost origin,
    // which is not in any default CORS_ORIGINS list, so a credentialed cross-
    // origin fetch would be blocked and always report "Cannot reach server".
    // A reachability probe does not need the user's session — an OK status is
    // enough, and a 401 (anonymous) also proves the server is up.
    const resp = await fetch(`${url}/api/health`, { signal: controller.signal })
    return resp.ok || resp.status === 401
  } catch {
    return false
  } finally {
    clearTimeout(timeout)
  }
}

/**
 * Classify a server URL for UX messaging.
 * - 'https': secure, full-featured
 * - 'http-lan': private network (RFC-1918, loopback, .local/.lan suffix)
 * - 'http-public': cleartext on a public domain — blocked
 * - 'localhost': dev-only
 *
 * IP checks are numeric so a public hostname whose label happens to start with
 * "10." or "192.168." is not misclassified as LAN.
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
  if (host === 'localhost' || host === '127.0.0.1' || host === '[::1]') return 'localhost'
  if (isPrivateIpv4(host)) return 'http-lan'
  if (host.endsWith('.local') || host.endsWith('.lan')) return 'http-lan'
  return 'http-public'
}

/** True only when {@code host} is an IPv4 literal in the loopback or RFC-1918 range. */
function isPrivateIpv4(host: string): boolean {
  const match = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(host)
  if (!match) return false
  const a = Number(match[1]), b = Number(match[2])
  if (a > 255 || b > 255 || Number(match[3]) > 255 || Number(match[4]) > 255) return false
  if (a === 10) return true
  if (a === 172 && b >= 16 && b <= 31) return true
  if (a === 192 && b === 168) return true
  if (a === 127) return true
  return false
}
