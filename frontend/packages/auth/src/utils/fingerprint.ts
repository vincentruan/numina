/**
 * DEPRECATED: This module is no longer used by the device trust flow.
 *
 * Device identity now uses a server-issued UUID stored in cookie + localStorage.
 * See deviceIdentity.ts for the new approach.
 *
 * This file is retained for potential future risk-control use.
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
