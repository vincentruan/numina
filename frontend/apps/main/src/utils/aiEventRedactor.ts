/**
 * Sensitive field redaction for frontend defense-in-depth.
 *
 * This is a secondary protection layer. Backend (stream_events.py) redacts
 * before streaming. Frontend redaction here prevents accidental exposure
 * via DevTools/XSS or if backend redaction fails.
 */

// Sensitive field keys that must be redacted before display.
// Uses exact case-insensitive matching to avoid false positives.
const SENSITIVE_KEYS: ReadonlySet<string> = new Set([
  'api_key',
  'apikey',
  'key', // catch standalone "key" but not "keyboard" (exact match)
  'password',
  'pwd',
  'pass', // catch standalone "pass" but not "compass" (exact match)
  'token',
  'access_token',
  'auth_token',
  'secret',
  'secret_key',
  'credential',
  'credentials',
  'private_key',
  'private',
])

// Known-safe field names that should NOT be redacted even if they contain sensitive substrings.
const SENSITIVE_KEY_WHITELIST: ReadonlySet<string> = new Set([
  'keyboard',
  'keypress',
  'keybinding',
  'passenger',
  'compass',
  'passport', // travel document, not auth
  'bypass',
  'gateway',
])

const REDACTED_MARKER = '***REDACTED***'
const MAX_DEPTH = 5

/**
 * Redact sensitive fields from an object before displaying.
 *
 * @param obj - The object to redact (tool arguments, config, etc.)
 * @param depth - Current recursion depth (limit MAX_DEPTH to prevent infinite loops)
 * @returns A new object with sensitive values replaced by "***REDACTED***"
 */
export function redactSensitiveFields(
  obj: Record<string, unknown>,
  depth = 0,
): Record<string, unknown> {
  if (depth > MAX_DEPTH) {
    return { _truncated: '...' }
  }

  const result: Record<string, unknown> = {}

  for (const [key, value] of Object.entries(obj)) {
    const lowerKey = key.toLowerCase()

    // Check whitelist first (known-safe fields never redacted)
    if (SENSITIVE_KEY_WHITELIST.has(lowerKey)) {
      result[key] = value
      continue
    }

    // Check exact match against sensitive keys
    if (SENSITIVE_KEYS.has(lowerKey)) {
      result[key] = REDACTED_MARKER
      continue
    }

    // Recursively redact nested objects or arrays
    if (typeof value === 'object' && value !== null) {
      if (Array.isArray(value)) {
        result[key] = redactSensitiveArray(value, depth + 1)
      } else {
        result[key] = redactSensitiveFields(value as Record<string, unknown>, depth + 1)
      }
    } else {
      result[key] = value
    }
  }

  return result
}

/**
 * Redact sensitive fields from an array of objects.
 *
 * @param arr - The array to redact
 * @param depth - Current recursion depth
 * @returns A new array with each object redacted
 */
export function redactSensitiveArray(
  arr: unknown[],
  depth = 0,
): unknown[] {
  return arr.map((item) => {
    if (typeof item === 'object' && item !== null && !Array.isArray(item)) {
      return redactSensitiveFields(item as Record<string, unknown>, depth + 1)
    }
    return item
  })
}

/**
 * Deep redact any value (object, array, or primitive).
 *
 * @param value - Any value to potentially redact
 * @param depth - Current recursion depth
 * @returns Redacted value
 */
export function redactDeep(value: unknown, depth = 0): unknown {
  if (depth > MAX_DEPTH) {
    return { _truncated: '...' }
  }

  if (typeof value !== 'object' || value === null) {
    return value
  }

  if (Array.isArray(value)) {
    return redactSensitiveArray(value, depth)
  }

  return redactSensitiveFields(value as Record<string, unknown>, depth)
}

// Export constants for testing
export { SENSITIVE_KEYS, SENSITIVE_KEY_WHITELIST, REDACTED_MARKER, MAX_DEPTH }