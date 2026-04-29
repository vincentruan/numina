/**
 * Browser fingerprint utility for device trust detection.
 *
 * Generates a stable SHA-256 fingerprint from browser/device characteristics.
 * Used to identify trusted devices without storing sensitive data.
 *
 * Note: This is a lightweight, privacy-respecting fingerprint — it uses only
 * publicly available browser properties and does NOT use canvas, audio, or
 * other invasive techniques.
 */

/**
 * Collect stable browser/device characteristics for fingerprinting.
 * These values are stable across sessions for the same browser/device.
 */
function collectComponents(): string {
  const components = [
    navigator.userAgent,
    navigator.language,
    `${screen.width}x${screen.height}x${screen.colorDepth}`,
    Intl.DateTimeFormat().resolvedOptions().timeZone,
    String(navigator.hardwareConcurrency ?? ''),
    String(navigator.maxTouchPoints ?? ''),
    navigator.platform ?? '',
  ]
  return components.join('|')
}

/**
 * Generate a SHA-256 fingerprint hash from browser characteristics.
 * Returns a 64-character hex string.
 *
 * Falls back to a random UUID if Web Crypto API is unavailable.
 */
export async function getDeviceFingerprint(): Promise<string> {
  try {
    const raw = collectComponents()
    const encoded = new TextEncoder().encode(raw)
    const hashBuffer = await crypto.subtle.digest('SHA-256', encoded)
    const hashArray = Array.from(new Uint8Array(hashBuffer))
    return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('')
  } catch {
    // Fallback: generate a random ID and persist it
    const stored = localStorage.getItem('_numina_fp_fallback')
    if (stored) return stored
    const fallback = crypto.randomUUID().replace(/-/g, '')
    localStorage.setItem('_numina_fp_fallback', fallback)
    return fallback
  }
}
