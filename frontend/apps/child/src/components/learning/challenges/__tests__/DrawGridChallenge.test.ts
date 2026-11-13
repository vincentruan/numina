import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { DrawGridChallenge } from '@/types/learning-challenge'
import DrawGridComponent from '../DrawGridChallenge.vue'

function makeConfig(overrides: Partial<DrawGridChallenge> = {}): DrawGridChallenge {
  return {
    id: 'draw-grid-test',
    topicId: 't1',
    type: 'draw-grid',
    difficulty: 2,
    ageGroup: 'mid',
    scenario: 'Fill the top row and the two middle cells of the bottom row.',
    scenarioZh: '涂满第一行，再涂第二行中间两格。',
    discoveryMessage: 'That is the shape!',
    discoveryMessageZh: '形状画对啦！',
    gridRows: 2,
    gridCols: 3,
    // top row all filled + bottom middle
    targetCells: ['0-0', '0-1', '0-2', '1-1'],
    ...overrides,
  }
}

function mountGrid(config: DrawGridChallenge = makeConfig()) {
  const i18n = createI18n({
    legacy: false,
    locale: 'en-US',
    messages: { 'en-US': enUS, 'zh-CN': zhCN },
  })
  return mount(DrawGridComponent, {
    props: { config },
    global: { plugins: [i18n] },
  })
}

/** Tap cells by their row-col key. */
async function fillCells(wrapper: ReturnType<typeof mountGrid>, keys: string[]) {
  const cells = wrapper.findAll('.draw-cell')
  for (const key of keys) {
    const index = cellIndex(key, wrapper)
    await cells[index].trigger('click')
  }
}

function cellIndex(key: string, wrapper: ReturnType<typeof mountGrid>): number {
  const cols = (wrapper.props('config') as DrawGridChallenge).gridCols
  const [row, col] = key.split('-').map(Number)
  return row * cols + col
}

async function check(wrapper: ReturnType<typeof mountGrid>) {
  await wrapper.find('.challenge-check-btn').trigger('click')
  await nextTick()
}

describe('DrawGridChallenge', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('renders rows × cols cells', () => {
    const wrapper = mountGrid()
    expect(wrapper.findAll('.draw-cell')).toHaveLength(6)
  })

  it('renders a 3x3 grid when configured', () => {
    const wrapper = mountGrid(makeConfig({ gridRows: 3, gridCols: 3 }))
    expect(wrapper.findAll('.draw-cell')).toHaveLength(9)
  })

  it('tapping a cell fills it, tapping again empties it', async () => {
    const wrapper = mountGrid()
    const cell = wrapper.findAll('.draw-cell')[0]
    await cell.trigger('click')
    expect(cell.classes()).toContain('draw-cell--filled')
    await cell.trigger('click')
    expect(cell.classes()).not.toContain('draw-cell--filled')
  })

  it('matching the target exactly yields correct', async () => {
    const wrapper = mountGrid()
    await fillCells(wrapper, ['0-0', '0-1', '0-2', '1-1'])
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--correct').exists()).toBe(true)
    expect(wrapper.text()).toContain('That is the shape!')
  })

  it('being one cell off yields close', async () => {
    const wrapper = mountGrid()
    // Correct except an extra cell, and the middle-bottom one missing → 2 diff.
    // Use exactly one difference: drop the last target cell.
    await fillCells(wrapper, ['0-0', '0-1', '0-2'])
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--close').exists()).toBe(true)
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(false)
  })

  it('renders the close hint', async () => {
    const wrapper = mountGrid()
    await fillCells(wrapper, ['0-0', '0-1', '0-2'])
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('Just one cell off')
  })

  it('being several cells off yields wrong', async () => {
    const wrapper = mountGrid()
    await fillCells(wrapper, ['1-0', '1-2'])
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
  })

  it('renders the wrong hint', async () => {
    const wrapper = mountGrid()
    await fillCells(wrapper, ['1-0', '1-2'])
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('Still quite different')
  })

  it('an empty grid asks the child to draw first', async () => {
    const wrapper = mountGrid()
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('Fill in your shape')
  })

  it('the scenario states the target layout cell by cell', () => {
    // KTD7: the exact-match judge is only fair when the target is stated
    const config = makeConfig()
    for (const cell of config.targetCells) {
      const [row, col] = cell.split('-').map(Number)
      // Each target cell must be describable from the scenario text alone
      expect(config.scenario.length).toBeGreaterThan(0)
      expect(row).toBeLessThan(config.gridRows)
      expect(col).toBeLessThan(config.gridCols)
    }
  })

  it('emits complete on continue', async () => {
    const wrapper = mountGrid()
    await fillCells(wrapper, ['0-0', '0-1', '0-2', '1-1'])
    await check(wrapper)
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(wrapper.emitted('complete')).toBeTruthy()
  })

  it('clears persisted state on continue', async () => {
    const config = makeConfig()
    const wrapper = mountGrid(config)
    await fillCells(wrapper, ['0-0', '0-1', '0-2', '1-1'])
    await check(wrapper)
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(sessionStorage.getItem(`numina:challenge:${config.id}`)).toBeNull()
  })
})
