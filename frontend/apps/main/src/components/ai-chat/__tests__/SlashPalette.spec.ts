import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SlashPalette from '../SlashPalette.vue'
import type { SlashCommand } from '@/composables/ai-chat/useSlashCommands'

vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

function makeCommand(overrides: Partial<SlashCommand> = {}): SlashCommand {
  return {
    name: '/goal',
    description: 'aiChat.slashGoalDesc',
    insertText: '/goal ',
    apply: () => false,
    ...overrides,
  }
}

function mountPalette(props: Partial<InstanceType<typeof SlashPalette>['$props']> = {}) {
  return mount(SlashPalette, {
    props: {
      open: true,
      commands: [makeCommand({ name: '/goal' }), makeCommand({ name: '/compact', description: 'aiChat.slashCompactDesc' })],
      selectedIndex: 0,
      ...props,
    },
  })
}

describe('SlashPalette', () => {
  it('does not render when open=false', () => {
    const wrapper = mountPalette({ open: false })
    expect(wrapper.find('.slash-palette').exists()).toBe(false)
  })

  it('renders a button per command with name + description', () => {
    const wrapper = mountPalette()
    const items = wrapper.findAll('.slash-palette__item')
    expect(items).toHaveLength(2)
    expect(items[0].find('.slash-palette__name').text()).toBe('/goal')
    expect(items[0].find('.slash-palette__desc').text()).toBe('aiChat.slashGoalDesc')
    expect(items[1].find('.slash-palette__name').text()).toBe('/compact')
  })

  it('marks the selectedIndex item as selected', () => {
    const wrapper = mountPalette({ selectedIndex: 1 })
    const items = wrapper.findAll('.slash-palette__item')
    expect(items[0].classes()).not.toContain('slash-palette__item--selected')
    expect(items[1].classes()).toContain('slash-palette__item--selected')
  })

  it('shows the empty hint when there are no matches', () => {
    const wrapper = mountPalette({ commands: [] })
    expect(wrapper.find('.slash-palette__empty').exists()).toBe(true)
    expect(wrapper.find('.slash-palette__empty').text()).toBe('aiChat.slashPaletteEmpty')
    expect(wrapper.findAll('.slash-palette__item')).toHaveLength(0)
  })

  it('emits select with the clicked command (mousedown.prevent keeps focus)', async () => {
    const wrapper = mountPalette()
    const items = wrapper.findAll('.slash-palette__item')
    await items[1].trigger('mousedown')
    const selectEvents = wrapper.emitted('select')
    expect(selectEvents).toHaveLength(1)
    const [emittedCmd] = selectEvents![0] as [SlashCommand]
    expect(emittedCmd.name).toBe('/compact')
  })
})
