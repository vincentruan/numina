/**
 * useTenantAiResources.ts unit tests — DeerFlow model/capability parity
 *
 * 参考: frontend/src/components/workspace/input-box.tsx INPUT_MODE_CONFIGS + getResolvedMode
 */
import { describe, it, expect } from 'vitest'
import {
  INPUT_MODE_CONFIGS,
  getResolvedMode,
  type InputMode,
} from '@/composables/ai-chat/useTenantAiResources'

describe('INPUT_MODE_CONFIGS', () => {
  const modes: InputMode[] = ['flash', 'thinking', 'pro', 'ultra']

  it('has all four modes defined', () => {
    expect(Object.keys(INPUT_MODE_CONFIGS)).toEqual(modes)
  })

  it('flash mode has minimal reasoning_effort and no thinking', () => {
    const config = INPUT_MODE_CONFIGS.flash
    expect(config.thinking_enabled).toBe(false)
    expect(config.is_plan_mode).toBe(false)
    expect(config.subagent_enabled).toBe(false)
    expect(config.reasoning_effort).toBe('minimal')
    expect(config.icon).toBe('lucide:zap')
    expect(config.label).toBe('闪电')
  })

  it('thinking mode has low reasoning_effort and thinking enabled', () => {
    const config = INPUT_MODE_CONFIGS.thinking
    expect(config.thinking_enabled).toBe(true)
    expect(config.is_plan_mode).toBe(false)
    expect(config.subagent_enabled).toBe(false)
    expect(config.reasoning_effort).toBe('low')
    expect(config.icon).toBe('lucide:lightbulb')
    expect(config.label).toBe('思考')
  })

  it('pro mode has medium reasoning_effort and plan mode', () => {
    const config = INPUT_MODE_CONFIGS.pro
    expect(config.thinking_enabled).toBe(true)
    expect(config.is_plan_mode).toBe(true)
    expect(config.subagent_enabled).toBe(false)
    expect(config.reasoning_effort).toBe('medium')
    expect(config.icon).toBe('lucide:graduation-cap')
    expect(config.label).toBe('专业')
  })

  it('ultra mode has high reasoning_effort and all capabilities', () => {
    const config = INPUT_MODE_CONFIGS.ultra
    expect(config.thinking_enabled).toBe(true)
    expect(config.is_plan_mode).toBe(true)
    expect(config.subagent_enabled).toBe(true)
    expect(config.reasoning_effort).toBe('high')
    expect(config.icon).toBe('lucide:rocket')
    expect(config.label).toBe('旗舰')
  })

  it('each mode config has required fields', () => {
    for (const mode of modes) {
      const config = INPUT_MODE_CONFIGS[mode]
      expect(config.mode).toBe(mode)
      expect(typeof config.icon).toBe('string')
      expect(typeof config.label).toBe('string')
      expect(typeof config.description).toBe('string')
    }
  })
})

describe('getResolvedMode', () => {
  it('returns flash when supportsThinking=false and requestedMode is non-flash', () => {
    // DeerFlow degradation: non-thinking model → flash
    expect(getResolvedMode('thinking', false, true)).toBe('flash')
    expect(getResolvedMode('pro', false, true)).toBe('flash')
    expect(getResolvedMode('ultra', false, true)).toBe('flash')
  })

  it('returns flash when supportsThinking=false and requestedMode undefined', () => {
    expect(getResolvedMode(undefined, false, true)).toBe('flash')
  })

  it('returns pro when supportsThinking=true and requestedMode undefined', () => {
    // DeerFlow default: thinking-capable model → pro
    expect(getResolvedMode(undefined, true, false)).toBe('pro')
    expect(getResolvedMode(undefined, true, true)).toBe('pro')
  })

  it('returns pro when ultra requested but supportsSubagent=false', () => {
    // DeerFlow degradation: ultra w/o subagent → pro
    expect(getResolvedMode('ultra', true, false)).toBe('pro')
  })

  it('returns ultra when supportsThinking=true and supportsSubagent=true', () => {
    expect(getResolvedMode('ultra', true, true)).toBe('ultra')
  })

  it('returns requested mode when capabilities support it', () => {
    expect(getResolvedMode('flash', true, true)).toBe('flash')
    expect(getResolvedMode('flash', false, false)).toBe('flash') // flash always allowed
    expect(getResolvedMode('thinking', true, false)).toBe('thinking')
    expect(getResolvedMode('thinking', true, true)).toBe('thinking')
    expect(getResolvedMode('pro', true, false)).toBe('pro')
    expect(getResolvedMode('pro', true, true)).toBe('pro')
  })

  it('preserves flash mode even when supportsThinking=false', () => {
    // Flash is always available — core DeerFlow invariant
    expect(getResolvedMode('flash', false, false)).toBe('flash')
  })

  it('does not upgrade mode when requested is lower', () => {
    // If user explicitly requests flash, stay flash even if capable
    expect(getResolvedMode('flash', true, true)).toBe('flash')
  })
})