import { describe, it, expect } from 'vitest'
import {
  buildTokenDebugStep,
  buildTokenDebugSteps,
  accumulateUsage,
  formatTokenCount,
} from '@/utils/ai-chat/token-usage-steps'
import {
  getTokenUsageViewPreset,
  tokenUsagePreferencesFromPreset,
} from '@/composables/ai-chat/useTokenUsagePrefs'
import type { ChatMessage } from '@/types/ai-chat/message-group'

// Stub i18n: return the key (with params interpolated for debugging)
function makeT() {
  return (key: string, params?: Record<string, unknown>) => {
    if (!params) return key
    let result = key
    for (const [k, v] of Object.entries(params)) {
      result = result.replace(`{${k}}`, String(v))
    }
    return result
  }
}

function makeAIMessage(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: 'msg-1',
    type: 'ai',
    role: 'assistant',
    content: 'Hello',
    displayTime: '12:00',
    ...overrides,
  }
}

describe('token-usage-steps', () => {
  const t = makeT()

  describe('buildTokenDebugStep', () => {
    it('returns null for non-AI messages', () => {
      const msg = makeAIMessage({ type: 'human' })
      expect(buildTokenDebugStep(msg, t)).toBeNull()
    })

    it('labels as final answer when message has content and no tool calls', () => {
      const msg = makeAIMessage({ content: 'final answer text' })
      const step = buildTokenDebugStep(msg, t)
      expect(step).not.toBeNull()
      expect(step!.label).toBe('aiChat.tokenUsageFinalAnswer')
      expect(step!.secondaryLabels).toEqual([])
      expect(step!.sharedAttribution).toBe(false)
    })

    it('labels as thinking when message has no content and no tool calls', () => {
      const msg = makeAIMessage({ content: '' })
      const step = buildTokenDebugStep(msg, t)
      expect(step!.label).toBe('aiChat.tokenUsageThinking')
    })

    it('labels with single tool call action', () => {
      const msg = makeAIMessage({
        content: '',
        tool_calls: [{
          id: 'tc-1',
          name: 'get_assets',
          args: {},
          status: 'success',
        }],
      })
      const step = buildTokenDebugStep(msg, t)
      // explainToolCallKey('get_assets') returns { key: 'tool.action.get_asset' }
      expect(step!.label).toBe('tool.action.get_asset')
      expect(step!.secondaryLabels).toEqual([])
      expect(step!.sharedAttribution).toBe(false)
    })

    it('labels as step total with secondary labels for multiple tool calls', () => {
      const msg = makeAIMessage({
        content: '',
        tool_calls: [
          { id: 'tc-1', name: 'get_assets', args: {}, status: 'success' },
          { id: 'tc-2', name: 'get_liabilities', args: {}, status: 'success' },
        ],
      })
      const step = buildTokenDebugStep(msg, t)
      expect(step!.label).toBe('aiChat.tokenUsageStepTotal')
      expect(step!.secondaryLabels).toEqual(['tool.action.get_asset', 'tool.action.get_liability'])
      expect(step!.sharedAttribution).toBe(true)
    })

    it('extracts usage metadata', () => {
      const msg = makeAIMessage({
        usageMetadata: { inputTokens: 100, outputTokens: 50 },
      })
      const step = buildTokenDebugStep(msg, t)
      expect(step!.usage).toEqual({
        inputTokens: 100,
        outputTokens: 50,
        totalTokens: 150,
      })
    })

    it('returns null usage when message has no usageMetadata', () => {
      const msg = makeAIMessage()
      const step = buildTokenDebugStep(msg, t)
      expect(step!.usage).toBeNull()
    })

    it('skips tool calls with empty name', () => {
      const msg = makeAIMessage({
        content: '',
        tool_calls: [
          { id: 'tc-1', name: '', args: {}, status: 'pending' },
          { id: 'tc-2', name: 'get_assets', args: {}, status: 'success' },
        ],
      })
      const step = buildTokenDebugStep(msg, t)
      // Only the named tool call counts -> not shared
      expect(step!.label).toBe('tool.action.get_asset')
      expect(step!.sharedAttribution).toBe(false)
    })
  })

  describe('buildTokenDebugSteps', () => {
    it('produces one step per AI message', () => {
      const messages: ChatMessage[] = [
        makeAIMessage({ id: 'msg-1', usageMetadata: { inputTokens: 10, outputTokens: 5 } }),
        { id: 'human-1', type: 'human', role: 'user', content: 'hi', displayTime: '12:00' },
        makeAIMessage({ id: 'msg-2', usageMetadata: { inputTokens: 20, outputTokens: 10 } }),
      ]
      const steps = buildTokenDebugSteps(messages, t)
      expect(steps).toHaveLength(2)
      expect(steps[0].messageId).toBe('msg-1')
      expect(steps[1].messageId).toBe('msg-2')
    })

    it('skips AI messages without usageMetadata is NOT the case - steps still built', () => {
      // buildTokenDebugStep does not filter by usage; it always builds a step
      // for AI messages (usage is null but the label is still useful)
      const messages: ChatMessage[] = [
        makeAIMessage({ id: 'msg-1' }), // no usageMetadata
      ]
      const steps = buildTokenDebugSteps(messages, t)
      expect(steps).toHaveLength(1)
      expect(steps[0].usage).toBeNull()
    })
  })

  describe('accumulateUsage', () => {
    it('returns null for empty messages', () => {
      expect(accumulateUsage([])).toBeNull()
    })

    it('returns null when no AI messages have usage', () => {
      const messages: ChatMessage[] = [
        makeAIMessage({ id: 'msg-1' }), // no usageMetadata
      ]
      expect(accumulateUsage(messages)).toBeNull()
    })

    it('accumulates across AI messages', () => {
      const messages: ChatMessage[] = [
        makeAIMessage({ id: 'msg-1', usageMetadata: { inputTokens: 100, outputTokens: 50 } }),
        { id: 'human-1', type: 'human', role: 'user', content: 'hi', displayTime: '12:00' },
        makeAIMessage({ id: 'msg-2', usageMetadata: { inputTokens: 200, outputTokens: 100 } }),
      ]
      const result = accumulateUsage(messages)
      expect(result).toEqual({
        inputTokens: 300,
        outputTokens: 150,
        totalTokens: 450,
      })
    })

    it('deduplicates by message id', () => {
      const messages: ChatMessage[] = [
        makeAIMessage({ id: 'msg-1', usageMetadata: { inputTokens: 100, outputTokens: 50 } }),
        makeAIMessage({ id: 'msg-1', usageMetadata: { inputTokens: 100, outputTokens: 50 } }),
      ]
      const result = accumulateUsage(messages)
      expect(result).toEqual({
        inputTokens: 100,
        outputTokens: 50,
        totalTokens: 150,
      })
    })
  })

  describe('formatTokenCount', () => {
    it('formats small numbers with locale separators', () => {
      expect(formatTokenCount(0)).toBe('0')
      expect(formatTokenCount(1234)).toBe('1,234')
    })

    it('formats large numbers as K', () => {
      expect(formatTokenCount(10000)).toBe('10.0K')
      expect(formatTokenCount(12345)).toBe('12.3K')
    })

    it('does not use K for numbers below 10000', () => {
      expect(formatTokenCount(9999)).toBe('9,999')
    })
  })

  describe('preset <-> preferences conversion', () => {
    it('off preset maps to headerTotal=false, inlineMode=off', () => {
      const prefs = tokenUsagePreferencesFromPreset('off')
      expect(prefs).toEqual({ headerTotal: false, inlineMode: 'off' })
      expect(getTokenUsageViewPreset(prefs)).toBe('off')
    })

    it('summary preset maps to headerTotal=true, inlineMode=off', () => {
      const prefs = tokenUsagePreferencesFromPreset('summary')
      expect(prefs).toEqual({ headerTotal: true, inlineMode: 'off' })
      expect(getTokenUsageViewPreset(prefs)).toBe('summary')
    })

    it('per_turn preset maps to headerTotal=true, inlineMode=per_turn', () => {
      const prefs = tokenUsagePreferencesFromPreset('per_turn')
      expect(prefs).toEqual({ headerTotal: true, inlineMode: 'per_turn' })
      expect(getTokenUsageViewPreset(prefs)).toBe('per_turn')
    })

    it('debug preset maps to headerTotal=true, inlineMode=step_debug', () => {
      const prefs = tokenUsagePreferencesFromPreset('debug')
      expect(prefs).toEqual({ headerTotal: true, inlineMode: 'step_debug' })
      expect(getTokenUsageViewPreset(prefs)).toBe('debug')
    })
  })
})
