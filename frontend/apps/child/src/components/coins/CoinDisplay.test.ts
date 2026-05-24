import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CoinDisplay from './CoinDisplay.vue'

describe('CoinDisplay animation behavior', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  function readTierCounts(html: string): { gold: string | null; silver: string | null; copper: string | null } {
    const grab = (cls: string) => {
      const m = html.match(new RegExp(`<span[^>]*class="[^"]*${cls}[^"]*"[^>]*>([^<]*)</span>`))
      return m ? m[1].trim() : null
    }
    return { gold: grab('gold'), silver: grab('silver'), copper: grab('copper') }
  }

  it('snaps immediately when animateChanges is false (default)', async () => {
    const wrapper = mount(CoinDisplay, { props: { amount: 0 } })
    await wrapper.setProps({ amount: 25 })
    // 25 = 0 gold, 2 silver, 5 copper (with default 10:1 ratios)
    const counts = readTierCounts(wrapper.html())
    expect(counts.silver).toBe('2')
    expect(counts.copper).toBe('5')
  })

  it('settles on the new tier values after the cascade duration when animateChanges is true', async () => {
    const wrapper = mount(CoinDisplay, { props: { amount: 0, animateChanges: true } })
    await wrapper.setProps({ amount: 25 })

    // advance past the full cascade window (gold delay 900 + duration 600 = 1500ms)
    await vi.advanceTimersByTimeAsync(1600)
    await flushPromises()

    const counts = readTierCounts(wrapper.html())
    expect(counts.silver).toBe('2')
    expect(counts.copper).toBe('5')
  })
})
