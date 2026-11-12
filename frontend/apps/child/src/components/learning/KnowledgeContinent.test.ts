import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import KnowledgeContinent from './KnowledgeContinent.vue'
import type { ContinentSummary } from './KnowledgeContinent.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  messages: { en: { continent: { mastered: '{mastered}/{total} mastered' } } },
})

function makeContinent(overrides: Partial<ContinentSummary> = {}): ContinentSummary {
  return {
    subject: 'mathematics',
    displayName: 'Mathematics',
    icon: '📐',
    itemCount: 10,
    masteredCount: 3,
    masteryRatio: 0.3,
    masteryPercent: 30,
    isFrontier: false,
    ...overrides,
  }
}

function mountContinent(props: Partial<InstanceType<typeof KnowledgeContinent>['$props']> = {}) {
  return mount(KnowledgeContinent, {
    props: {
      continents: [makeContinent()],
      selectedSubject: 'mathematics',
      ...props,
    },
    global: { plugins: [i18n] },
  })
}

describe('KnowledgeContinent', () => {
  it('renders one card per continent', () => {
    const wrapper = mountContinent({
      continents: [makeContinent(), makeContinent({ subject: 'science', displayName: 'Science', icon: '🔬' })],
      selectedSubject: 'mathematics',
    })
    expect(wrapper.findAll('.continent-card')).toHaveLength(2)
  })

  it('marks active continent with continent-card--active class', () => {
    const wrapper = mountContinent()
    expect(wrapper.find('.continent-card').classes()).toContain('continent-card--active')
  })

  it('emits select event when a continent is clicked', async () => {
    const wrapper = mountContinent({ selectedSubject: '' })
    await wrapper.find('.continent-card').trigger('click')
    expect(wrapper.emitted('select')?.[0]).toEqual(['mathematics'])
  })

  it('disables empty continents', () => {
    const wrapper = mountContinent({ continents: [makeContinent({ itemCount: 0 })] })
    const btn = wrapper.find('.continent-card')
    expect(btn.attributes('disabled')).toBeDefined()
  })

  it('shows frontier badge when isFrontier is true', () => {
    const wrapper = mountContinent({ continents: [makeContinent({ isFrontier: true })] })
    expect(wrapper.find('.continent-card__frontier-badge').exists()).toBe(true)
  })
})
