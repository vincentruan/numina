import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import HumanInputCard from '../HumanInputCard.vue'

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

// Mock MarkdownContent to avoid full markdown rendering
vi.mock('../MarkdownContent.vue', () => ({
  default: {
    name: 'MarkdownContent',
    props: ['content'],
    template: '<div class="mock-markdown">{{ content }}</div>',
  },
}))

function mountCard(propsOverrides = {}) {
  return mount(HumanInputCard, {
    props: {
      question: 'Which color?',
      threadId: 'thread-1',
      interruptId: 'intr-1',
      ...propsOverrides,
    },
  })
}

describe('HumanInputCard', () => {
  describe('single-select mode (DeerFlow one-step)', () => {
    const options = [
      { label: 'Red', value: 'red' },
      { label: 'Blue', value: 'blue' },
      { label: 'Green', value: 'green' },
    ]

    it('renders option buttons for each option', () => {
      const wrapper = mountCard({ options })
      const buttons = wrapper.findAll('.option-btn')
      expect(buttons).toHaveLength(3)
      expect(buttons[0].text()).toBe('Red')
      expect(buttons[1].text()).toBe('Blue')
      expect(buttons[2].text()).toBe('Green')
    })

    it('clicking an option immediately emits submit with that value (one-step)', async () => {
      const wrapper = mountCard({ options })
      const buttons = wrapper.findAll('.option-btn')
      await buttons[1].trigger('click')
      const emitted = wrapper.emitted('submit')
      expect(emitted).toHaveLength(1)
      expect(emitted![0]).toEqual(['blue'])
    })

    it('disables buttons when status is submitting', () => {
      const wrapper = mountCard({ options, status: 'submitting' })
      const buttons = wrapper.findAll('.option-btn')
      buttons.forEach(btn => {
        expect(btn.attributes('disabled')).toBeDefined()
      })
    })

    it('does not emit when status is answered', async () => {
      const wrapper = mountCard({ options, status: 'answered', answer: 'red' })
      const buttons = wrapper.findAll('.option-btn')
      // No option buttons rendered in answered state
      expect(buttons).toHaveLength(0)
    })
  })

  describe('multi-select mode', () => {
    const options = [
      { label: 'Red', value: 'red' },
      { label: 'Blue', value: 'blue' },
      { label: 'Green', value: 'green' },
    ]

    it('renders checkboxes when multiSelect is true', () => {
      const wrapper = mountCard({ options, multiSelect: true })
      const checkboxes = wrapper.findAll('.checkbox-input')
      expect(checkboxes).toHaveLength(3)
    })

    it('toggles selection on checkbox change', async () => {
      const wrapper = mountCard({ options, multiSelect: true })
      const checkboxes = wrapper.findAll('.checkbox-input')

      // Check first option
      await checkboxes[0].setValue(true)
      expect(wrapper.find('.checkbox-option--checked').exists()).toBe(true)

      // Check second option
      await checkboxes[1].setValue(true)
      const checked = wrapper.findAll('.checkbox-option--checked')
      expect(checked).toHaveLength(2)

      // Uncheck first option
      await checkboxes[0].setValue(false)
      const checkedAfter = wrapper.findAll('.checkbox-option--checked')
      expect(checkedAfter).toHaveLength(1)
    })

    it('submit button is disabled until at least one option selected', () => {
      const wrapper = mountCard({ options, multiSelect: true })
      const submitBtn = wrapper.find('.submit-btn')
      expect(submitBtn.attributes('disabled')).toBeDefined()
    })

    it('emits JSON array of selected values on submit', async () => {
      const wrapper = mountCard({ options, multiSelect: true })
      const checkboxes = wrapper.findAll('.checkbox-input')

      // Select red and green
      await checkboxes[0].setValue(true)
      await checkboxes[2].setValue(true)

      const submitBtn = wrapper.find('.submit-btn')
      await submitBtn.trigger('click')

      const emitted = wrapper.emitted('submit')
      expect(emitted).toHaveLength(1)
      const answer = JSON.parse(emitted![0][0] as string)
      expect(answer).toEqual(['red', 'green'])
    })
  })

  describe('free-text mode (no options)', () => {
    it('renders textarea when no options', () => {
      const wrapper = mountCard()
      expect(wrapper.find('.custom-textarea').exists()).toBe(true)
    })

    it('shows submit button only when text is entered', async () => {
      const wrapper = mountCard()
      expect(wrapper.find('.submit-btn').exists()).toBe(false)

      const textarea = wrapper.find('.custom-textarea')
      await textarea.setValue('hello')
      expect(wrapper.find('.submit-btn').exists()).toBe(true)
    })

    it('emits text on submit', async () => {
      const wrapper = mountCard()
      const textarea = wrapper.find('.custom-textarea')
      await textarea.setValue('my answer')

      const submitBtn = wrapper.find('.submit-btn')
      await submitBtn.trigger('click')

      const emitted = wrapper.emitted('submit')
      expect(emitted).toHaveLength(1)
      expect(emitted![0]).toEqual(['my answer'])
    })

    it('Enter key submits (non-IME)', async () => {
      const wrapper = mountCard()
      const textarea = wrapper.find('.custom-textarea')
      await textarea.setValue('answer')
      await textarea.trigger('keydown', { key: 'Enter', shiftKey: false })

      const emitted = wrapper.emitted('submit')
      expect(emitted).toHaveLength(1)
    })
  })

  describe('choiceWithOther mode', () => {
    const options = [{ label: 'Red', value: 'red' }]

    it('shows both option buttons and textarea', () => {
      const wrapper = mountCard({ options, choiceWithOther: true })
      expect(wrapper.find('.option-btn').exists()).toBe(true)
      expect(wrapper.find('.custom-textarea').exists()).toBe(true)
    })
  })

  describe('status states', () => {
    it('shows answered state with answer text', () => {
      const wrapper = mountCard({ status: 'answered', answer: 'red' })
      expect(wrapper.find('.card-answer').exists()).toBe(true)
      expect(wrapper.find('.answer-text').text()).toBe('red')
    })

    it('shows submitting spinner', () => {
      const wrapper = mountCard({ status: 'submitting' })
      expect(wrapper.find('.card-submitting').exists()).toBe(true)
    })

    it('shows error state', () => {
      const wrapper = mountCard({ status: 'error', errorMessage: 'timeout' })
      expect(wrapper.find('.card-error').exists()).toBe(true)
      expect(wrapper.find('.error-detail').text()).toBe('timeout')
    })

    it('shows superseded state', () => {
      const wrapper = mountCard({ status: 'superseded' })
      expect(wrapper.find('.card-superseded').exists()).toBe(true)
    })
  })
})
