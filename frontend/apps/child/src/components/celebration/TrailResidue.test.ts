import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import TrailResidue from './TrailResidue.vue'

interface ExposedTrail {
  addPath: (d: string) => void
  clearAll: () => void
}

describe('TrailResidue FIFO cap', () => {
  function clearBody(): void {
    document.body.innerHTML = ''
  }

  it('caps active SVG paths at 50 (oldest evicted first)', async () => {
    const wrapper = mount(TrailResidue, { attachTo: document.body })
    await nextTick()
    const exposed = wrapper.vm as unknown as ExposedTrail
    const overlay = document.body.querySelector('.trail-overlay') as SVGSVGElement
    expect(overlay).not.toBeNull()

    for (let i = 0; i < 60; i++) {
      exposed.addPath(`M 0 0 Q 50 -10 100 ${i}`)
    }

    expect(overlay.querySelectorAll('path.trail-segment').length).toBe(50)

    // The first 10 paths should have been evicted; the last 50 retained.
    // Last path's `d` attribute encodes its index, so the oldest surviving
    // path corresponds to i=10.
    const firstSurvivor = overlay.querySelector('path.trail-segment') as SVGPathElement
    expect(firstSurvivor.getAttribute('d')).toBe('M 0 0 Q 50 -10 100 10')

    wrapper.unmount()
    clearBody()
  })

  it('clearAll removes every path immediately', async () => {
    const wrapper = mount(TrailResidue, { attachTo: document.body })
    await nextTick()
    const exposed = wrapper.vm as unknown as ExposedTrail
    const overlay = document.body.querySelector('.trail-overlay') as SVGSVGElement

    for (let i = 0; i < 5; i++) {
      exposed.addPath(`M 0 0 Q 50 -10 100 ${i}`)
    }
    expect(overlay.querySelectorAll('path.trail-segment').length).toBe(5)

    exposed.clearAll()
    expect(overlay.querySelectorAll('path.trail-segment').length).toBe(0)

    wrapper.unmount()
    clearBody()
  })
})
