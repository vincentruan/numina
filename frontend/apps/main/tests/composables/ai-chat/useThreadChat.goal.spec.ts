import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useThreadChat } from '@/composables/ai-chat/useThreadChat'

// Mock dependencies
vi.mock('vue-i18n', () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: 'zh-CN' } }),
}))

vi.mock('vant', () => ({
  showFailToast: vi.fn(),
  showSuccessToast: vi.fn(),
  showToast: vi.fn(),
}))

vi.mock('@/api/ai-chat', () => ({
  getClient: vi.fn(),
  createThread: vi.fn(),
  deleteThread: vi.fn(),
  compactThread: vi.fn(),
  getThreadGoal: vi.fn(),
  setThreadGoal: vi.fn(),
  clearThreadGoal: vi.fn(),
}))

vi.mock('@/api/sessions', () => ({
  submitMessageFeedback: vi.fn(),
  getSessionFeedback: vi.fn().mockResolvedValue({ data: { items: {} } }),
}))

vi.mock('@/stores/family', () => ({
  useFamilyStore: () => ({ family: { id: 'fam-1' } }),
}))

import {
  getThreadGoal,
  setThreadGoal,
  clearThreadGoal,
} from '@/api/ai-chat'
import { showFailToast, showSuccessToast, showToast } from 'vant'

describe('useThreadChat — U5 /goal (handleGoalCommand)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('set: PUTs the objective and returns true (caller starts the run)', async () => {
    const goal = {
      objective: '分析资产',
      status: 'active' as const,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      continuation_count: 0,
      max_continuations: 8,
      no_progress_count: 0,
      max_no_progress_continuations: 2,
    }
    vi.mocked(setThreadGoal).mockResolvedValue({ goal } as never)

    const chat = useThreadChat()
    const onGoalChange = vi.fn()
    const ok = await chat.handleGoalCommand(
      'thread-1',
      { kind: 'set', objective: '分析资产' },
      onGoalChange,
    )

    expect(ok).toBe(true)
    expect(setThreadGoal).toHaveBeenCalledWith('thread-1', { objective: '分析资产' })
    expect(onGoalChange).toHaveBeenCalledWith(goal)
    expect(showSuccessToast).toHaveBeenCalledWith('aiChat.goalSet')
  })

  it('status: GETs and toasts goalActive (objective) when a goal exists', async () => {
    const goal = {
      objective: '分析资产',
      status: 'active' as const,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      continuation_count: 0,
      max_continuations: 8,
      no_progress_count: 0,
      max_no_progress_continuations: 2,
    }
    vi.mocked(getThreadGoal).mockResolvedValue({ goal } as never)

    const chat = useThreadChat()
    const onGoalChange = vi.fn()
    const ok = await chat.handleGoalCommand('thread-1', { kind: 'status' }, onGoalChange)

    expect(ok).toBe(true)
    expect(getThreadGoal).toHaveBeenCalledWith('thread-1')
    expect(onGoalChange).toHaveBeenCalledWith(goal)
    expect(showToast).toHaveBeenCalledWith('aiChat.goalActive')
  })

  it('status: toasts goalNone when the server reports no goal', async () => {
    vi.mocked(getThreadGoal).mockResolvedValue({ goal: null } as never)

    const chat = useThreadChat()
    const onGoalChange = vi.fn()
    const ok = await chat.handleGoalCommand('thread-1', { kind: 'status' }, onGoalChange)

    expect(ok).toBe(true)
    expect(onGoalChange).toHaveBeenCalledWith(null)
    expect(showToast).toHaveBeenCalledWith('aiChat.goalNone')
  })

  it('clear: DELETEs and toasts goalCleared; never starts a run', async () => {
    vi.mocked(clearThreadGoal).mockResolvedValue({ goal: null } as never)

    const chat = useThreadChat()
    const onGoalChange = vi.fn()
    const ok = await chat.handleGoalCommand('thread-1', { kind: 'clear' }, onGoalChange)

    expect(ok).toBe(true)
    expect(clearThreadGoal).toHaveBeenCalledWith('thread-1')
    expect(onGoalChange).toHaveBeenCalledWith(null)
    expect(showSuccessToast).toHaveBeenCalledWith('aiChat.goalCleared')
  })

  it('error: PUT failure toasts goalFailed and returns false (no run)', async () => {
    vi.mocked(setThreadGoal).mockRejectedValue(new Error('boom') as never)

    const chat = useThreadChat()
    const onGoalChange = vi.fn()
    const ok = await chat.handleGoalCommand(
      'thread-1',
      { kind: 'set', objective: '分析资产' },
      onGoalChange,
    )

    expect(ok).toBe(false)
    expect(showFailToast).toHaveBeenCalledWith('boom')
    expect(onGoalChange).not.toHaveBeenCalled()
  })
})
