/**
 * useMessageGroups.ts unit tests — DeerFlow message grouping parity
 *
 * Covers:
 * - computed reactivity when messages ref changes
 * - deduplication integration
 * - getCurrentProcessingGroup helper
 * - getMessageStats helper
 * - empty messages handling
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { ref, nextTick } from 'vue'
import {
  useMessageGroups,
  getCurrentProcessingGroup,
  getMessageStats,
} from '@/composables/ai-chat/useMessageGroups'
import type { ChatMessage, MessageGroup } from '@/types/ai-chat/message-group'

// Mock deduplicateMessages
vi.mock('@/utils/ai-chat/message-identity', () => ({
  deduplicateMessages: (messages: ChatMessage[]) => {
    // Simple dedup by id - removes duplicates
    const seen = new Set<string>()
    return messages.filter((m) => {
      if (m.id && seen.has(m.id)) return false
      if (m.id) seen.add(m.id)
      return true
    })
  },
}))

// Mock getMessageGroups
vi.mock('@/utils/ai-chat/messageGroups', () => ({
  getMessageGroups: (messages: ChatMessage[]): MessageGroup[] => {
    // Simplified grouping for testing
    const groups: MessageGroup[] = []

    for (const msg of messages) {
      if (msg.type === 'human') {
        groups.push({
          type: 'human',
          messages: [msg],
          id: msg.id,
        })
      } else if (msg.type === 'ai') {
        if (msg.tool_calls && msg.tool_calls.length > 0) {
          groups.push({
            type: 'assistant:processing',
            messages: [msg],
            id: msg.id,
          })
        } else if (msg.tool_call_id) {
          // Tool result message - would merge with processing in real impl
          groups.push({
            type: 'assistant:processing',
            messages: [msg],
            id: msg.id,
          })
        } else {
          groups.push({
            type: 'assistant',
            messages: [msg],
            id: msg.id,
          })
        }
      }
    }

    return groups
  },
}))

describe('useMessageGroups', () => {
  describe('computed reactivity', () => {
    it('returns empty array for empty messages', () => {
      const messages = ref<ChatMessage[]>([])
      const groups = useMessageGroups(messages)

      expect(groups.value.length).toBe(0)
    })

    it('updates when messages ref changes', async () => {
      const messages = ref<ChatMessage[]>([])
      const groups = useMessageGroups(messages)

      expect(groups.value.length).toBe(0)

      messages.value = [
        { id: 'msg-1', type: 'human', role: 'user', content: 'Hello', displayTime: '', phase: 'done' },
      ]
      await nextTick()

      expect(groups.value.length).toBe(1)
      expect(groups.value[0].type).toBe('human')
    })

    it('reacts to message additions', async () => {
      const messages = ref<ChatMessage[]>([
        { id: 'msg-1', type: 'human', role: 'user', content: 'Hello', displayTime: '', phase: 'done' },
      ])
      const groups = useMessageGroups(messages)

      expect(groups.value.length).toBe(1)

      messages.value = [
        ...messages.value,
        { id: 'msg-2', type: 'ai', role: 'assistant', content: 'Hi!', displayTime: '', phase: 'done' },
      ]
      await nextTick()

      expect(groups.value.length).toBe(2)
    })
  })

  describe('deduplication integration', () => {
    it('removes duplicate messages by id', async () => {
      const messages = ref<ChatMessage[]>([
        { id: 'msg-1', type: 'human', role: 'user', content: 'Hello', displayTime: '', phase: 'done' },
        { id: 'msg-1', type: 'human', role: 'user', content: 'Hello', displayTime: '', phase: 'done' }, // Duplicate
      ])
      const groups = useMessageGroups(messages)

      await nextTick()

      // Dedup should remove duplicate
      expect(groups.value.length).toBe(1)
    })
  })
})

describe('getCurrentProcessingGroup', () => {
  it('returns null when not loading', () => {
    const groups: MessageGroup[] = [
      { type: 'assistant:processing', messages: [], id: 'proc-1' },
    ]

    const result = getCurrentProcessingGroup(groups, false)

    expect(result).toBeNull()
  })

  it('returns null when no processing groups exist', () => {
    const groups: MessageGroup[] = [
      { type: 'human', messages: [], id: 'human-1' },
      { type: 'assistant', messages: [], id: 'ai-1' },
    ]

    const result = getCurrentProcessingGroup(groups, true)

    expect(result).toBeNull()
  })

  it('returns last processing group when loading', () => {
    const groups: MessageGroup[] = [
      { type: 'assistant:processing', messages: [], id: 'proc-1' },
      { type: 'human', messages: [], id: 'human-1' },
      { type: 'assistant:processing', messages: [], id: 'proc-2' },
    ]

    const result = getCurrentProcessingGroup(groups, true)

    expect(result).not.toBeNull()
    expect(result?.id).toBe('proc-2')
  })
})

describe('getMessageStats', () => {
  it('returns zero counts for empty groups', () => {
    const result = getMessageStats([])

    expect(result).toEqual({
      humanCount: 0,
      assistantCount: 0,
      toolCount: 0,
      total: 0,
    })
  })

  it('counts human and assistant groups', () => {
    const groups: MessageGroup[] = [
      { type: 'human', messages: [], id: 'h1' },
      { type: 'assistant', messages: [], id: 'a1' },
      { type: 'human', messages: [], id: 'h2' },
    ]

    const result = getMessageStats(groups)

    expect(result.humanCount).toBe(2)
    expect(result.assistantCount).toBe(1)
    expect(result.total).toBe(3)
  })

  it('counts assistant subtypes as assistant', () => {
    const groups: MessageGroup[] = [
      { type: 'assistant:processing', messages: [], id: 'p1' },
      { type: 'assistant:clarification', messages: [], id: 'c1' },
    ]

    const result = getMessageStats(groups)

    expect(result.assistantCount).toBe(2)
    expect(result.total).toBe(2)
  })

  it('counts tool messages in processing groups', () => {
    const groups: MessageGroup[] = [
      {
        type: 'assistant:processing',
        messages: [
          { id: 't1', type: 'tool', role: 'assistant', content: 'tool result', displayTime: '', phase: 'done', tool_call_id: 'tc1' },
        ],
        id: 'p1',
      },
    ]

    const result = getMessageStats(groups)

    expect(result.toolCount).toBe(1)
  })
})