/**
 * Device tier detection utility
 * Classifies devices as low/medium/high for animation performance scaling
 */

import type { DeviceTier } from '@/composables/starField.config'

export interface DeviceTierInfo {
  tier: DeviceTier
  isReducedMotion: boolean
  cpuCores: number
  isTouchDevice: boolean
  viewportWidth: number
  deviceMemory?: number
}

/**
 * Check if user prefers reduced motion
 */
function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/**
 * Get CPU core count (may be undefined in some browsers)
 */
function getCpuCores(): number {
  return navigator.hardwareConcurrency || 4 // Default to 4 if unavailable
}

/**
 * Check if device has touch capability
 */
function isTouchDevice(): boolean {
  return (
    'ontouchstart' in window ||
    navigator.maxTouchPoints > 0
  )
}

/**
 * Get device memory in GB (may be undefined in some browsers)
 */
function getDeviceMemory(): number | undefined {
  // @ts-expect-error - deviceMemory is not in standard Navigator type
  return navigator.deviceMemory
}

/**
 * Determine device tier based on capabilities
 *
 * Tier rules:
 * - LOW: reduced-motion preference OR cores <= 2 OR narrow screen (<400px) with touch
 * - MEDIUM: typical mobile or low-power PC (default)
 * - HIGH: newer mobile or mid-high PC (4+ cores, desktop without touch)
 */
export function getDeviceTier(): DeviceTierInfo {
  const reducedMotion = prefersReducedMotion()
  const cpuCores = getCpuCores()
  const touchDevice = isTouchDevice()
  const viewportWidth = window.innerWidth
  const memory = getDeviceMemory()

  // Reduced motion always forces low tier
  if (reducedMotion) {
    return {
      tier: 'low',
      isReducedMotion: true,
      cpuCores,
      isTouchDevice: touchDevice,
      viewportWidth,
      deviceMemory: memory,
    }
  }

  // Low CPU cores = low tier
  if (cpuCores <= 2) {
    return {
      tier: 'low',
      isReducedMotion: false,
      cpuCores,
      isTouchDevice: touchDevice,
      viewportWidth,
      deviceMemory: memory,
    }
  }

  // Narrow screen with touch = mobile device, likely needs medium tier
  if (viewportWidth < 400 && touchDevice) {
    return {
      tier: 'low',
      isReducedMotion: false,
      cpuCores,
      isTouchDevice: touchDevice,
      viewportWidth,
      deviceMemory: memory,
    }
  }

  // Low memory (if available) suggests low tier
  if (memory !== undefined && memory <= 2) {
    return {
      tier: 'low',
      isReducedMotion: false,
      cpuCores,
      isTouchDevice: touchDevice,
      viewportWidth,
      deviceMemory: memory,
    }
  }

  // High tier: 6+ cores on desktop (no touch), or 4+ cores on modern mobile
  if (
    (cpuCores >= 6 && !touchDevice) ||
    (cpuCores >= 4 && viewportWidth >= 768 && !touchDevice)
  ) {
    return {
      tier: 'high',
      isReducedMotion: false,
      cpuCores,
      isTouchDevice: touchDevice,
      viewportWidth,
      deviceMemory: memory,
    }
  }

  // Default to medium tier
  return {
    tier: 'medium',
    isReducedMotion: false,
    cpuCores,
    isTouchDevice: touchDevice,
    viewportWidth,
    deviceMemory: memory,
  }
}

/**
 * Get just the tier string (convenience function)
 */
export function getTier(): DeviceTier {
  return getDeviceTier().tier
}