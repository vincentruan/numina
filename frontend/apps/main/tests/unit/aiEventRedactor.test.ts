import { describe, it, expect } from 'vitest'
import {
  redactSensitiveFields,
  redactSensitiveArray,
  redactDeep,
  SENSITIVE_KEYS,
  SENSITIVE_KEY_WHITELIST,
  REDACTED_MARKER,
  MAX_DEPTH,
} from '@/utils/aiEventRedactor'

describe('redactSensitiveFields', () => {
  it('returns non-sensitive args unchanged', () => {
    const args = { family_id: '123', asset_type: 'stock', limit: 10 }
    const result = redactSensitiveFields(args)
    expect(result).toEqual(args)
  })

  it('redacts api_key field', () => {
    const args = { api_key: 'sk-secret123', query: 'SELECT *' }
    const result = redactSensitiveFields(args) as any
    expect(result.api_key).toBe(REDACTED_MARKER)
    expect(result.query).toBe('SELECT *')
  })

  it('redacts password field', () => {
    const args = { password: 'my-password', username: 'admin' }
    const result = redactSensitiveFields(args) as any
    expect(result.password).toBe(REDACTED_MARKER)
    expect(result.username).toBe('admin')
  })

  it('redacts nested secret field', () => {
    const args = {
      config: {
        secret: 'hidden-value',
        endpoint: 'https://api.example.com',
      },
      action: 'fetch',
    }
    const result = redactSensitiveFields(args) as any
    expect(result.config.secret).toBe(REDACTED_MARKER)
    expect(result.config.endpoint).toBe('https://api.example.com')
    expect(result.action).toBe('fetch')
  })

  it('redacts nested token field', () => {
    const args = {
      auth: {
        token: 'bearer-xyz',
        expires_in: 3600,
      },
    }
    const result = redactSensitiveFields(args) as any
    expect(result.auth.token).toBe(REDACTED_MARKER)
    expect(result.auth.expires_in).toBe(3600)
  })

  it('does not redact keyboard (whitelist)', () => {
    const args = { keyboard: 'mechanical', layout: 'qwerty' }
    const result = redactSensitiveFields(args)
    expect(result.keyboard).toBe('mechanical')
    expect(result.layout).toBe('qwerty')
  })

  it('does not redact passenger (whitelist)', () => {
    const args = { passenger: 'John Doe', flight: 'UA123' }
    const result = redactSensitiveFields(args)
    expect(result.passenger).toBe('John Doe')
  })

  it('matches case-insensitively', () => {
    const args = { API_KEY: 'secret', api_key: 'also-secret' }
    const result = redactSensitiveFields(args)
    expect(result.API_KEY).toBe(REDACTED_MARKER)
    expect(result.api_key).toBe(REDACTED_MARKER)
  })

  it('truncates deep nesting at MAX_DEPTH', () => {
    // depth=0: root, depth=1: l1, ... depth=5: l5, depth=6: l6 (truncated)
    const args = { l1: { l2: { l3: { l4: { l5: { l6: { secret: 'deep' } } } } } } }
    const result = redactSensitiveFields(args) as any
    // l5 contains l6, which gets truncated at depth=6
    expect(result.l1.l2.l3.l4.l5.l6).toEqual({ _truncated: '...' })
  })

  it('returns empty object unchanged', () => {
    const args = {}
    const result = redactSensitiveFields(args)
    expect(result).toEqual({})
  })

  it('redacts multiple sensitive fields', () => {
    const args = {
      api_key: 'key1',
      password: 'pass1',
      token: 'tok1',
      secret: 'sec1',
      data: 'public',
    }
    const result = redactSensitiveFields(args) as any
    expect(result.api_key).toBe(REDACTED_MARKER)
    expect(result.password).toBe(REDACTED_MARKER)
    expect(result.token).toBe(REDACTED_MARKER)
    expect(result.secret).toBe(REDACTED_MARKER)
    expect(result.data).toBe('public')
  })
})

describe('redactSensitiveArray', () => {
  it('redacts each object in array', () => {
    const arr = [
      { api_key: 'key1', name: 'tool1' },
      { password: 'pass2', name: 'tool2' },
    ]
    const result = redactSensitiveArray(arr) as any
    expect(result[0].api_key).toBe(REDACTED_MARKER)
    expect(result[0].name).toBe('tool1')
    expect(result[1].password).toBe(REDACTED_MARKER)
    expect(result[1].name).toBe('tool2')
  })

  it('preserves non-object items', () => {
    const arr = ['string', 123, null]
    const result = redactSensitiveArray(arr)
    expect(result).toEqual(['string', 123, null])
  })

  it('returns empty array unchanged', () => {
    expect(redactSensitiveArray([])).toEqual([])
  })
})

describe('redactDeep', () => {
  it('redacts object', () => {
    const value = { api_key: 'secret' }
    const result = redactDeep(value)
    expect(result).toEqual({ api_key: REDACTED_MARKER })
  })

  it('redacts array of objects', () => {
    const value = [{ api_key: 's1' }, { token: 't1' }]
    const result = redactDeep(value) as any
    expect(result[0].api_key).toBe(REDACTED_MARKER)
    expect(result[1].token).toBe(REDACTED_MARKER)
  })

  it('preserves primitives', () => {
    expect(redactDeep('string')).toBe('string')
    expect(redactDeep(123)).toBe(123)
    expect(redactDeep(null)).toBe(null)
    expect(redactDeep(undefined)).toBe(undefined)
  })

  it('handles nested structures', () => {
    const value = {
      config: { credentials: { username: 'user', password: 'pass' } },
      items: [{ api_key: 'k1' }],
    }
    const result = redactDeep(value) as any
    expect(result.config.credentials).toBe(REDACTED_MARKER)
    expect((result.items as any[])[0].api_key).toBe(REDACTED_MARKER)
  })
})

describe('constants', () => {
  it('SENSITIVE_KEYS contains expected keys', () => {
    expect(SENSITIVE_KEYS.has('api_key')).toBe(true)
    expect(SENSITIVE_KEYS.has('password')).toBe(true)
    expect(SENSITIVE_KEYS.has('token')).toBe(true)
    expect(SENSITIVE_KEYS.has('secret')).toBe(true)
    expect(SENSITIVE_KEYS.has('credential')).toBe(true)
    expect(SENSITIVE_KEYS.has('private')).toBe(true)
  })

  it('SENSITIVE_KEY_WHITELIST contains keyboard', () => {
    expect(SENSITIVE_KEY_WHITELIST.has('keyboard')).toBe(true)
  })

  it('SENSITIVE_KEY_WHITELIST contains passenger', () => {
    expect(SENSITIVE_KEY_WHITELIST.has('passenger')).toBe(true)
  })

  it('REDACTED_MARKER is correct', () => {
    expect(REDACTED_MARKER).toBe('***REDACTED***')
  })

  it('MAX_DEPTH is 5', () => {
    expect(MAX_DEPTH).toBe(5)
  })

  it('key exact match: redacts standalone key but not keyboard', () => {
    // 'key' is in SENSITIVE_KEYS
    expect(SENSITIVE_KEYS.has('key')).toBe(true)
    // 'keyboard' is in whitelist
    expect(SENSITIVE_KEY_WHITELIST.has('keyboard')).toBe(true)
    // Verify behavior
    const args = { key: 'secret', keyboard: 'device' }
    const result = redactSensitiveFields(args) as any
    expect(result.key).toBe(REDACTED_MARKER)
    expect(result.keyboard).toBe('device')
  })
})