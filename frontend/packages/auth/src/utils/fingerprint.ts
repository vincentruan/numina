/**
 * Browser fingerprint utility for device trust detection.
 *
 * Uses FingerprintJS open-source library for stable device identification.
 * Falls back to localStorage-persisted UUID if FingerprintJS is unavailable.
 */

import FingerprintJS from '@fingerprintjs/fingerprintjs'

/**
 * Generate a stable device fingerprint using FingerprintJS.
 * Returns a visitor identifier that persists across browser updates.
 *
 * FingerprintJS achieves 60-80% accuracy by combining multiple browser
 * characteristics (canvas, WebGL, fonts, etc.) while respecting privacy.
 *
 * Falls back to a localStorage-persisted UUID if the library fails to load.
 */
export async function getDeviceFingerprint(): Promise<string> {
  try {
    // Check for existing localStorage fallback first (backward compatibility)
    const storedFallback = localStorage.getItem('_numina_fp_fallback')
    if (storedFallback) {
      return storedFallback
    }

    // Initialize FingerprintJS agent
    const fp = await FingerprintJS.load()

    // Get the visitor identifier
    const result = await fp.get()

    // Store in localStorage for stability across sessions
    localStorage.setItem('_numina_fp_fallback', result.visitorId)

    return result.visitorId
  } catch {
    // Fallback: generate a random UUID and persist it
    const stored = localStorage.getItem('_numina_fp_fallback')
    if (stored) return stored
    const fallback = crypto.randomUUID().replace(/-/g, '')
    localStorage.setItem('_numina_fp_fallback', fallback)
    return fallback
  }
}
