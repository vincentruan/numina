import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useSlashCommands } from '../useSlashCommands'

// Mock vue-i18n: return the key so assertions can verify which key was used.
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

describe('useSlashCommands', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('exposes /goal and /compact from the local static registry', () => {
    const { commands } = useSlashCommands()
    const names = commands.value.map((c) => c.name)
    expect(names).toContain('/goal')
    expect(names).toContain('/compact')
    // Descriptions flow through i18n (no hard-coded strings).
    const goal = commands.value.find((c) => c.name === '/goal')!
    expect(goal.description).toBe('aiChat.slashGoalDesc')
    const compact = commands.value.find((c) => c.name === '/compact')!
    expect(compact.description).toBe('aiChat.slashCompactDesc')
  })

  it('does NOT source from useCapabilityStore (only the two static commands)', () => {
    const { commands } = useSlashCommands()
    expect(commands.value).toHaveLength(2)
  })

  it('empty query returns all commands', () => {
    const { filteredCommands, query } = useSlashCommands()
    query.value = ''
    expect(filteredCommands.value).toHaveLength(2)
  })

  it('/g filters to /goal only', () => {
    const { filteredCommands, query } = useSlashCommands()
    query.value = '/g'
    expect(filteredCommands.value).toHaveLength(1)
    expect(filteredCommands.value[0].name).toBe('/goal')
  })

  it('/c filters to /compact only', () => {
    const { filteredCommands, query } = useSlashCommands()
    query.value = '/c'
    expect(filteredCommands.value).toHaveLength(1)
    expect(filteredCommands.value[0].name).toBe('/compact')
  })

  it('/xyz matches nothing → empty list', () => {
    const { filteredCommands, query } = useSlashCommands()
    query.value = '/xyz'
    expect(filteredCommands.value).toHaveLength(0)
  })

  it('filtering is case-insensitive', () => {
    const { filteredCommands, query } = useSlashCommands()
    query.value = '/GOAL'
    expect(filteredCommands.value).toHaveLength(1)
    expect(filteredCommands.value[0].name).toBe('/goal')
  })

  it('/goal.apply fills the textarea prefix and returns false (not fully handled)', () => {
    const { commands } = useSlashCommands()
    const goal = commands.value.find((c) => c.name === '/goal')!
    let value = ''
    const handled = goal.apply({
      value: value.trim(),
      setValue: (next: string) => {
        value = next
      },
    })
    expect(handled).toBe(false)
    expect(value).toBe('/goal ')
  })

  it('/goal.apply does not overwrite an existing /goal prefix', () => {
    const { commands } = useSlashCommands()
    const goal = commands.value.find((c) => c.name === '/goal')!
    let value = '/goal 分析资产'
    const handled = goal.apply({
      value: value.trim(),
      setValue: (next: string) => {
        value = next
      },
    })
    expect(handled).toBe(false)
    expect(value).toBe('/goal 分析资产')
  })

  it('/compact.apply returns true (fully handled — triggers its own flow)', () => {
    const { commands } = useSlashCommands()
    const compact = commands.value.find((c) => c.name === '/compact')!
    const handled = compact.apply({ value: '/compact', setValue: () => {} })
    expect(handled).toBe(true)
  })
})
