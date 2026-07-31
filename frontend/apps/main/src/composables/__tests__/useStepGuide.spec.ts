// frontend/apps/main/src/composables/__tests__/useStepGuide.spec.ts
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useStepGuide } from '../useStepGuide'

describe('useStepGuide', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('initializes with isActive=false', () => {
    const { isActive, currentStep } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
    })
    expect(isActive.value).toBe(false)
    expect(currentStep.value).toBe(0)
  })

  it('start() activates when key not done', () => {
    const { isActive, start } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
    })
    start()
    expect(isActive.value).toBe(true)
  })

  it('start() does NOT activate when key is done', () => {
    localStorage.setItem('guide_test', 'done')
    const { isActive, start } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
    })
    start()
    expect(isActive.value).toBe(false)
  })

  it('next() advances step', () => {
    const { currentStep, start, next } = useStepGuide({
      key: 'guide_test',
      steps: [
        { selector: '.a', mode: 'spotlight', title: 't1', desc: 'd1' },
        { selector: '.b', mode: 'spotlight', title: 't2', desc: 'd2' },
      ],
    })
    start()
    expect(currentStep.value).toBe(0)
    next()
    expect(currentStep.value).toBe(1)
  })

  it('skip() deactivates and marks done', () => {
    const { isActive, start, skip } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
    })
    start()
    skip()
    expect(isActive.value).toBe(false)
    expect(localStorage.getItem('guide_test')).toBe('done')
  })

  it('complete() deactivates and marks done', () => {
    const { isActive, start, complete } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
    })
    start()
    complete()
    expect(isActive.value).toBe(false)
    expect(localStorage.getItem('guide_test')).toBe('done')
  })

  it('calls onComplete callback when completed', () => {
    const onComplete = vi.fn()
    const { start, complete } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
      onComplete,
    })
    start()
    complete()
    expect(onComplete).toHaveBeenCalledOnce()
  })

  it('calls onSkip callback when skipped', () => {
    const onSkip = vi.fn()
    const { start, skip } = useStepGuide({
      key: 'guide_test',
      steps: [{ selector: '.test', mode: 'spotlight', title: 't', desc: 'd' }],
      onSkip,
    })
    start()
    skip()
    expect(onSkip).toHaveBeenCalledOnce()
  })
})