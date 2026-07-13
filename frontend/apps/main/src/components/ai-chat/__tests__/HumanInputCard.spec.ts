import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import HumanInputCard from '../HumanInputCard.vue'

// Mock vue-i18n useI18n to return the key as the value
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

// Stub MarkdownContent as a simple div
const MarkdownContentStub = {
  name: 'MarkdownContent',
  props: ['content'],
  template: '<div class="mock-markdown">{{ content }}</div>',
}

function createWrapper(propsOverrides: Record<string, unknown> = {}) {
  return mount(HumanInputCard, {
    props: {
      question: 'What is your name?',
      threadId: 'thread-1',
      interruptId: 'interrupt-1',
      ...propsOverrides,
    },
    global: {
      stubs: {
        MarkdownContent: MarkdownContentStub,
      },
    },
  })
}

describe('HumanInputCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders question text', () => {
    const wrapper = createWrapper()
    const questionEl = wrapper.find('.card-question')
    expect(questionEl.exists()).toBe(true)
    expect(questionEl.text()).toContain('What is your name?')
  })

  it('renders option buttons when options provided', () => {
    const options = [
      { label: 'Option A', value: 'a' },
      { label: 'Option B', value: 'b' },
    ]
    const wrapper = createWrapper({ options })
    const buttons = wrapper.findAll('.option-btn')
    expect(buttons).toHaveLength(2)
    expect(buttons[0].text()).toBe('Option A')
    expect(buttons[1].text()).toBe('Option B')
  })

  it('clicking option button emits submit with option value', async () => {
    const options = [
      { label: 'Option A', value: 'a' },
      { label: 'Option B', value: 'b' },
    ]
    const wrapper = createWrapper({ options })
    await wrapper.findAll('.option-btn')[0].trigger('click')
    expect(wrapper.emitted('submit')).toBeTruthy()
    expect(wrapper.emitted('submit')![0]).toEqual(['a'])
  })

  it('typing in textarea and clicking submit emits submit with typed text', async () => {
    const wrapper = createWrapper()
    const textarea = wrapper.find('.custom-textarea')
    await textarea.setValue('my custom answer')
    await wrapper.find('.submit-btn').trigger('click')
    expect(wrapper.emitted('submit')).toBeTruthy()
    expect(wrapper.emitted('submit')![0]).toEqual(['my custom answer'])
  })

  it('shows loading state when status is submitting', () => {
    const options = [{ label: 'A', value: 'a' }]
    const wrapper = createWrapper({ status: 'submitting', options })
    expect(wrapper.find('.card-submitting').exists()).toBe(true)
    expect(wrapper.find('.submit-spinner').exists()).toBe(true)
  })

  it('shows answered state when status is answered', () => {
    const wrapper = createWrapper({ status: 'answered', answer: 'My answer' })
    expect(wrapper.find('.card-answer').exists()).toBe(true)
    expect(wrapper.find('.answer-text').text()).toBe('My answer')
  })

  it('shows superseded state when status is superseded', () => {
    const wrapper = createWrapper({ status: 'superseded' })
    expect(wrapper.find('.card-superseded').exists()).toBe(true)
    expect(wrapper.classes()).toContain('superseded')
  })

  it('shows error state with retry button when status is error', async () => {
    const wrapper = createWrapper({
      status: 'error',
      errorMessage: 'Network timeout',
      answer: 'previous answer',
    })
    expect(wrapper.find('.card-error').exists()).toBe(true)
    expect(wrapper.find('.error-detail').text()).toBe('Network timeout')
    expect(wrapper.find('.retry-btn').exists()).toBe(true)

    await wrapper.find('.retry-btn').trigger('click')
    expect(wrapper.emitted('submit')).toBeTruthy()
    expect(wrapper.emitted('submit')![0]).toEqual(['previous answer'])
  })
})
