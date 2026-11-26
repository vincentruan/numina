/** T9 sprite labels — canvas textures, readability flags, sorting and disposal. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as THREE from 'three'
import type { CanvasTexture, SpriteMaterial } from 'three'
import { createOceanLabels, sortLabelsByCameraDistance, type OceanLabelNode } from '../OceanLabels'

interface MockCanvasContext {
  clearRect: ReturnType<typeof vi.fn>
  beginPath: ReturnType<typeof vi.fn>
  roundRect: ReturnType<typeof vi.fn>
  fill: ReturnType<typeof vi.fn>
  fillText: ReturnType<typeof vi.fn>
  measureText: ReturnType<typeof vi.fn>
  font: string
  fillStyle: string
  textAlign: CanvasTextAlign
  textBaseline: CanvasTextBaseline
}

const contexts: MockCanvasContext[] = []

function makeContext(): MockCanvasContext {
  return {
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    roundRect: vi.fn(),
    fill: vi.fn(),
    fillText: vi.fn(),
    measureText: vi.fn((text: string) => ({ width: text.length * 16 })),
    font: '',
    fillStyle: '',
    textAlign: 'left',
    textBaseline: 'alphabetic',
  }
}

function makeNode(overrides: Partial<OceanLabelNode> = {}): OceanLabelNode {
  return {
    id: 'math',
    displayName: 'Mathematics',
    icon: '📐',
    x: 0,
    z: 0,
    worldRadius: 0.7,
    ...overrides,
  }
}

function materialOf(sprite: THREE.Sprite): SpriteMaterial {
  return sprite.material as SpriteMaterial
}

beforeEach(() => {
  contexts.length = 0
  vi.stubGlobal('getComputedStyle', () => ({
    getPropertyValue: (name: string) => {
      if (name === '--ocean-label-color') return '#16324a'
      if (name === '--ocean-label-outline') return 'rgba(255, 255, 255, 0.85)'
      return ''
    },
  }))
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(() => {
    const context = makeContext()
    contexts.push(context)
    return context as unknown as CanvasRenderingContext2D
  })
})

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('createOceanLabels', () => {
  it('creates one constant-size sprite per node above its island', () => {
    const set = createOceanLabels(THREE, [makeNode({ id: 'math', x: 2, z: -3, worldRadius: 0.7 })])

    expect(set.sprites).toHaveLength(1)
    expect(set.labels).toHaveLength(1)
    expect(set.labels[0].id).toBe('math')
    expect(set.labels[0].sprite).toBe(set.sprites[0])

    const sprite = set.sprites[0]
    expect(sprite).toBeInstanceOf(THREE.Sprite)
    expect(sprite.position.x).toBe(2)
    expect(sprite.position.y).toBeCloseTo(2.6)
    expect(sprite.position.z).toBe(-3)
    expect(sprite.renderOrder).toBe(20)
    expect(sprite.scale.x / sprite.scale.y).toBeCloseTo(256 / 72)
    expect(sprite.scale.x).toBeLessThanOrEqual(256 / 1000)
    expect(sprite.frustumCulled).toBe(false)

    const material = materialOf(sprite)
    expect(material.map).toBeInstanceOf(THREE.CanvasTexture)
    expect(material.map?.colorSpace).toBe(THREE.SRGBColorSpace)
    expect(material.sizeAttenuation).toBe(false)
    expect(material.transparent).toBe(true)
    expect(material.depthTest).toBe(false)
    expect(material.depthWrite).toBe(false)
  })

  it('draws icon and name with the theme color in the inherited system font', () => {
    const set = createOceanLabels(THREE, [makeNode()])

    const context = contexts[0]
    expect(context.clearRect).toHaveBeenCalledTimes(1)
    expect(context.beginPath).toHaveBeenCalledTimes(1)
    expect(context.roundRect).toHaveBeenCalledTimes(1)
    expect(context.fill).toHaveBeenCalledTimes(1)
    expect(context.fillText).toHaveBeenCalledWith(
      '📐 Mathematics',
      expect.any(Number),
      expect.any(Number),
    )
    expect(context.font).toContain('system-ui')
    expect(context.font).not.toContain('Inter')
    expect(context.fillStyle).toBe('#16324a')
    set.dispose()
  })

  it('sorts nearest-last and assigns ascending renderOrder from 20', () => {
    const camera = new THREE.PerspectiveCamera()
    camera.position.set(0, 10, 20)
    const set = createOceanLabels(THREE, [
      makeNode({ id: 'near', z: 8 }),
      makeNode({ id: 'far', z: -8 }),
      makeNode({ id: 'mid', z: 0 }),
    ])
    const [near, far, mid] = set.labels
    const input = [far, near, mid]

    const sorted = sortLabelsByCameraDistance(input, camera)
    expect(sorted.map((label) => label.id)).toEqual(['far', 'mid', 'near'])
    expect(input.map((label) => label.id)).toEqual(['far', 'near', 'mid'])

    set.update(camera)
    expect(far.sprite.renderOrder).toBe(20)
    expect(mid.sprite.renderOrder).toBe(21)
    expect(near.sprite.renderOrder).toBe(22)
  })

  it('toggles sprite visibility per label', () => {
    const set = createOceanLabels(THREE, [makeNode({ id: 'a' }), makeNode({ id: 'b' })])

    set.labels[0].setVisible(false)
    expect(set.sprites[0].visible).toBe(false)
    expect(set.sprites[1].visible).toBe(true)

    set.labels[0].setVisible(true)
    expect(set.sprites[0].visible).toBe(true)
  })

  it('caches resources by icon + displayName and disposes each once', () => {
    const set = createOceanLabels(THREE, [
      makeNode({ id: 'a', displayName: 'Math', icon: '📐' }),
      makeNode({ id: 'b', displayName: 'Math', icon: '📐' }),
      makeNode({ id: 'c', displayName: 'Math', icon: '🧮' }),
      makeNode({ id: 'd', displayName: 'Science', icon: '🔬' }),
    ])
    expect(set.sprites).toHaveLength(4)

    const materialA = materialOf(set.sprites[0])
    expect(materialOf(set.sprites[1])).toBe(materialA)
    expect(materialOf(set.sprites[2])).not.toBe(materialA)
    expect(materialOf(set.sprites[3])).not.toBe(materialA)

    const materials = [...new Set(set.sprites.map(materialOf))]
    const textures = [...new Set(materials.map((material) => material.map as CanvasTexture))]
    expect(materials).toHaveLength(3)
    expect(textures).toHaveLength(3)

    const materialSpies = materials.map((material) => vi.spyOn(material, 'dispose'))
    const textureSpies = textures.map((texture) => vi.spyOn(texture, 'dispose'))

    set.dispose()
    set.dispose()
    for (const spy of materialSpies) expect(spy).toHaveBeenCalledTimes(1)
    for (const spy of textureSpies) expect(spy).toHaveBeenCalledTimes(1)
    expect(set.sprites).toHaveLength(0)
    expect(set.labels).toHaveLength(0)
  })
})
