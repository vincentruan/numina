import { ref } from 'vue'

/**
 * Token usage view preferences - DeerFlow parity.
 *
 * 参考: deer-flow-reference/frontend/src/core/messages/usage-model.ts
 *
 * DeerFlow exposes 4 presets that control what token UI is visible:
 *   off      - hide both header total and inline per-turn display
 *   summary  - header total only (no per-turn)
 *   per_turn - header total + per-turn summary under each assistant reply
 *   debug    - header total + per-step attribution cards (which tool/thinking
 *              consumed tokens for each AI message)
 *
 * `headerTotal` controls the header pill; `inlineMode` controls per-message
 * rendering. The two compose into a preset, and the preset is what the user
 * picks from the header dropdown.
 */
export type TokenUsageInlineMode = 'off' | 'per_turn' | 'step_debug'

export interface TokenUsagePreferences {
  headerTotal: boolean
  inlineMode: TokenUsageInlineMode
}

export type TokenUsageViewPreset = 'off' | 'summary' | 'per_turn' | 'debug'

const STORAGE_KEY = 'numina:token-usage-preset'

const VALID_PRESETS: TokenUsageViewPreset[] = ['off', 'summary', 'per_turn', 'debug']

function readStoredPreset(): TokenUsageViewPreset {
  if (typeof window === 'undefined') return 'per_turn'
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (raw && VALID_PRESETS.includes(raw as TokenUsageViewPreset)) {
      return raw as TokenUsageViewPreset
    }
  } catch {
    // localStorage may be unavailable (private mode, etc.) - fall back to default
  }
  return 'per_turn'
}

/**
 * Resolve a preset from the two boolean/enum preferences.
 * Mirrors getTokenUsageViewPreset() in DeerFlow usage-model.ts.
 */
export function getTokenUsageViewPreset(
  prefs: TokenUsagePreferences,
): TokenUsageViewPreset {
  if (!prefs.headerTotal && prefs.inlineMode === 'off') return 'off'
  if (prefs.headerTotal && prefs.inlineMode === 'off') return 'summary'
  if (prefs.inlineMode === 'step_debug') return 'debug'
  return 'per_turn'
}

/**
 * Resolve preferences from a user-selected preset.
 * Mirrors tokenUsagePreferencesFromPreset() in DeerFlow usage-model.ts.
 */
export function tokenUsagePreferencesFromPreset(
  preset: TokenUsageViewPreset,
): TokenUsagePreferences {
  switch (preset) {
    case 'off': return { headerTotal: false, inlineMode: 'off' }
    case 'summary': return { headerTotal: true, inlineMode: 'off' }
    case 'debug': return { headerTotal: true, inlineMode: 'step_debug' }
    case 'per_turn':
    default: return { headerTotal: true, inlineMode: 'per_turn' }
  }
}

/**
 * Persistent preset selection shared across sessions.
 *
 * Default is 'per_turn' (header total + per-turn summary) which matches the
 * pre-existing Numina behavior - both the header pill and the inline per-message
 * line were always visible. This preserves that UX unless the user changes it.
 *
 * Uses raw localStorage (no @vueuse dependency). The preset is a module-level
 * singleton so the header dropdown and the inline renderers stay in sync
 * without prop-drilling a setter back up from every message.
 */
export function useTokenUsagePrefs() {
  const preset = ref<TokenUsageViewPreset>(readStoredPreset())
  const preferences = ref<TokenUsagePreferences>(
    tokenUsagePreferencesFromPreset(preset.value),
  )

  function setPreset(next: TokenUsageViewPreset) {
    preset.value = next
    preferences.value = tokenUsagePreferencesFromPreset(next)
    try {
      window.localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Storage full or unavailable - preferences still apply for this session
    }
  }

  return {
    preset,
    preferences,
    setPreset,
  }
}
