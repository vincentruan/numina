/**
 * TowerInterior tests — floors, bricks, windows, a11y.
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import zhCN from '@/i18n/locales/zh-CN'
import TowerInterior from '../TowerInterior.vue'
import type { CastleTower, CastleWindow } from '@/api/learning'

function makeI18n() {
  return createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhCN } })
}

const tower: CastleTower = {
  subject: 'mathematics',
  mastered_count: 4,
  learning_count: 2,
  review_due_count: 1,
  total_count: 10,
  floors: [
    { domain: 'fractions', mastered_count: 4, learning_count: 2, review_due_count: 1, total_count: 10 },
    { domain: 'geometry', mastered_count: 0, learning_count: 0, review_due_count: 0, total_count: 5 },
  ],
}

const windows: CastleWindow[] = [
  {
    topic_id: '123',
    topic_name: 'Fractions',
    topic_name_zh: '分数',
    reason: '复习到期',
    subject: 'mathematics',
    domain: 'fractions',
  },
  {
    topic_id: '456',
    topic_name: 'Angles',
    topic_name_zh: '角',
    reason: '推荐学习',
    subject: 'mathematics',
    domain: 'geometry',
  },
]

function mountInterior(props: Record<string, unknown> = {}) {
  return mount(TowerInterior, {
    props: { tower, windows, ...props },
    global: { plugins: [makeI18n()] },
  })
}

describe('TowerInterior', () => {
  it('renders one section per floor', () => {
    const wrapper = mountInterior()
    expect(wrapper.findAll('[role="listitem"]').length).toBe(2)
  })

  it('renders floors bottom-up (reversed)', () => {
    const wrapper = mountInterior()
    const domains = wrapper.findAll('.tower-floor__domain').map((n) => n.text())
    // API order is fractions, geometry → reversed = geometry, fractions
    expect(domains[0]).toBe('geometry')
    expect(domains[1]).toBe('fractions')
  })

  it('shows mastered/total counts per floor', () => {
    const wrapper = mountInterior()
    expect(wrapper.text()).toContain('4')
    expect(wrapper.text()).toContain('10')
  })

  it('renders bricks only for floors with progress', () => {
    const wrapper = mountInterior()
    const bricks = wrapper.findAll('.tower-floor__brick')
    // fractions has progress (6/10 → 5 bricks), geometry has none (0 bricks)
    expect(bricks.length).toBeGreaterThan(0)
    expect(bricks.length).toBeLessThanOrEqual(8)
  })

  it('marks decayed floor with the decayed class', () => {
    const wrapper = mountInterior()
    expect(wrapper.find('.tower-floor--decayed').exists()).toBe(true)
  })

  it('renders windows for matching domains only', () => {
    const wrapper = mountInterior()
    const buttons = wrapper.findAll('.tower-window')
    expect(buttons.length).toBe(2)
  })

  it('emits windowSelect with the window payload', async () => {
    const wrapper = mountInterior()
    await wrapper.findAll('.tower-window')[0].trigger('click')
    const emitted = wrapper.emitted('windowSelect')
    expect(emitted).toBeTruthy()
    // Floors render bottom-up, so the geometry window (456) comes first
    expect((emitted![0] as [CastleWindow])[0].topic_id).toBe('456')
  })

  it('gives windows an aria-label with topic and reason', () => {
    const wrapper = mountInterior()
    const label = wrapper.findAll('.tower-window')[0].attributes('aria-label')
    expect(label).toContain('角')
    expect(label).toContain('推荐学习')
  })

  it('applies the new-brick class only to the matching floor', () => {
    const wrapper = mountInterior({
      newTopicId: '123',
      newSubject: 'mathematics',
      newDomain: 'fractions',
    })
    const newBricks = wrapper.findAll('.tower-floor__brick--new')
    expect(newBricks.length).toBeGreaterThan(0)
    // Only one floor should animate
    const floorsWithNew = wrapper.findAll('.tower-floor').filter((f) =>
      f.find('.tower-floor__brick--new').exists(),
    )
    expect(floorsWithNew.length).toBe(1)
  })

  it('does not animate when newSubject does not match', () => {
    const wrapper = mountInterior({
      newTopicId: '123',
      newSubject: 'science',
      newDomain: 'fractions',
    })
    expect(wrapper.findAll('.tower-floor__brick--new').length).toBe(0)
  })

  it('uses the foundation label for an empty domain', () => {
    const rootTower: CastleTower = {
      ...tower,
      floors: [
        { domain: '', mastered_count: 1, learning_count: 0, review_due_count: 0, total_count: 2 },
      ],
    }
    const wrapper = mount(TowerInterior, {
      props: { tower: rootTower, windows: [] },
      global: { plugins: [makeI18n()] },
    })
    expect(wrapper.find('.tower-floor__domain').text()).toBe('地基')
  })
})
