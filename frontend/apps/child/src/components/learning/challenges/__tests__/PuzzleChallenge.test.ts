import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { nextTick } from 'vue'
import zhCN from '@/i18n/locales/zh-CN'
import enUS from '@/i18n/locales/en-US'
import type { PuzzleChallenge } from '@/types/learning-challenge'
import PuzzleComponent from '../PuzzleChallenge.vue'

function makeConfig(overrides: Partial<PuzzleChallenge> = {}): PuzzleChallenge {
  return {
    id: 'puzzle-test',
    topicId: 't1',
    type: 'puzzle',
    difficulty: 2,
    ageGroup: 'mid',
    scenario: 'Put each piece in the right slot.',
    scenarioZh: '把每块放到正确的位置。',
    discoveryMessage: 'The picture is complete!',
    discoveryMessageZh: '拼图完成啦！',
    slots: [
      { id: 's1', label: 'Slot 1' },
      { id: 's2', label: 'Slot 2' },
      { id: 's3', label: 'Slot 3' },
    ],
    objects: [
      { id: 'p1', label: 'Piece 1', icon: '🟦' },
      { id: 'p2', label: 'Piece 2', icon: '🟩' },
      { id: 'p3', label: 'Piece 3', icon: '🟨' },
      { id: 'p4', label: 'Piece 4', icon: '🟧' },
    ],
    correctPlacement: { s1: 'p1', s2: 'p2', s3: 'p3' },
    ...overrides,
  }
}

function mountPuzzle(config: PuzzleChallenge = makeConfig()) {
  const i18n = createI18n({
    legacy: false,
    locale: 'en-US',
    messages: { 'en-US': enUS, 'zh-CN': zhCN },
  })
  return mount(PuzzleComponent, {
    props: { config },
    global: { plugins: [i18n] },
  })
}

/**
 * Select a piece by its id (looked up in the current pool) and drop it into a
 * slot by id. Pool order shifts as pieces are placed, so select by data.
 */
async function placePiece(
  wrapper: ReturnType<typeof mountPuzzle>,
  pieceId: string,
  slotId: string,
) {
  const pieces = wrapper.findAll('.puzzle-piece')
  let pieceIndex = -1
  for (let i = 0; i < pieces.length; i++) {
    if (pieces[i].text().includes(pieceLabel(pieceId))) {
      pieceIndex = i
      break
    }
  }
  expect(pieceIndex).toBeGreaterThanOrEqual(0)
  await pieces[pieceIndex].trigger('click')

  const slots = wrapper.findAll('.puzzle-slot')
  const slotIndex = ['s1', 's2', 's3'].indexOf(slotId)
  await slots[slotIndex].trigger('click')
}

function pieceLabel(pieceId: string): string {
  return `Piece ${pieceId.slice(1)}`
}

async function check(wrapper: ReturnType<typeof mountPuzzle>) {
  await wrapper.find('.challenge-check-btn').trigger('click')
  await nextTick()
}

describe('PuzzleChallenge', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  it('renders one control per slot and one per available piece', () => {
    const wrapper = mountPuzzle()
    expect(wrapper.findAll('.puzzle-slot')).toHaveLength(3)
    expect(wrapper.findAll('.puzzle-piece')).toHaveLength(4)
  })

  it('tapping a piece then a slot places it', async () => {
    const wrapper = mountPuzzle()
    await placePiece(wrapper, 'p1', 's1')
    expect(wrapper.findAll('.puzzle-piece')).toHaveLength(3)
    expect(wrapper.findAll('.puzzle-slot')[0].classes()).toContain('puzzle-slot--filled')
  })

  it('tapping a filled slot returns the piece to the pool', async () => {
    const wrapper = mountPuzzle()
    await placePiece(wrapper, 'p1', 's1')
    expect(wrapper.findAll('.puzzle-piece')).toHaveLength(3)
    await wrapper.findAll('.puzzle-slot')[0].trigger('click')
    expect(wrapper.findAll('.puzzle-piece')).toHaveLength(4)
  })

  it('all-correct placement yields correct', async () => {
    const wrapper = mountPuzzle()
    await placePiece(wrapper, 'p1', 's1')
    await placePiece(wrapper, 'p2', 's2')
    await placePiece(wrapper, 'p3', 's3')
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--correct').exists()).toBe(true)
    expect(wrapper.text()).toContain('The picture is complete!')
  })

  it('exactly one wrong slot yields close, not wrong', async () => {
    const wrapper = mountPuzzle()
    await placePiece(wrapper, 'p1', 's1')
    await placePiece(wrapper, 'p2', 's2')
    // p4 is a spare piece: correct everywhere except the last slot
    await placePiece(wrapper, 'p4', 's3')
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--close').exists()).toBe(true)
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(false)
  })

  it('renders the close hint when one piece is misplaced', async () => {
    const wrapper = mountPuzzle()
    await placePiece(wrapper, 'p1', 's1')
    await placePiece(wrapper, 'p2', 's2')
    await placePiece(wrapper, 'p4', 's3')
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('Just one piece off')
  })

  it('two or more wrong slots yield wrong', async () => {
    const wrapper = mountPuzzle()
    await placePiece(wrapper, 'p4', 's1')
    await placePiece(wrapper, 'p3', 's2')
    await placePiece(wrapper, 'p2', 's3')
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message--wrong').exists()).toBe(true)
  })

  it('renders the wrong hint for multiple misplaced pieces', async () => {
    const wrapper = mountPuzzle()
    await placePiece(wrapper, 'p4', 's1')
    await placePiece(wrapper, 'p3', 's2')
    await placePiece(wrapper, 'p2', 's3')
    await check(wrapper)
    expect(wrapper.find('.challenge-feedback__message').text()).toContain('A few pieces are wrong')
  })

  it('emits complete on continue', async () => {
    const wrapper = mountPuzzle()
    await placePiece(wrapper, 'p1', 's1')
    await placePiece(wrapper, 'p2', 's2')
    await placePiece(wrapper, 'p3', 's3')
    await check(wrapper)
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(wrapper.emitted('complete')).toBeTruthy()
  })

  it('clears persisted state on continue', async () => {
    const config = makeConfig()
    const wrapper = mountPuzzle(config)
    await placePiece(wrapper, 'p1', 's1')
    await placePiece(wrapper, 'p2', 's2')
    await placePiece(wrapper, 'p3', 's3')
    await check(wrapper)
    await wrapper.find('.challenge-next-btn').trigger('click')
    expect(sessionStorage.getItem(`numina:challenge:${config.id}`)).toBeNull()
  })
})
