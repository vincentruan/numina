/**
 * T9 ocean labels — canvas-texture sprites that stay legible above fog/water.
 *
 * Sprites never attenuate, never depth-test/write, and draw after the scene's
 * fog/water; `update(camera)` keeps nearer labels above farther ones.
 */
import type { CanvasTexture, PerspectiveCamera, Sprite, SpriteMaterial, Vector3 } from 'three'

export interface OceanLabelNode {
  id: string
  displayName: string
  icon: string
  x: number
  z: number
  worldRadius: number
}

export interface OceanLabelOptions {
  reducedMotion?: boolean
}

export interface OceanLabelSet {
  sprites: Sprite[]
  update(camera: PerspectiveCamera): void
  dispose(): void
}

const TEXTURE_WIDTH = 256
const TEXTURE_HEIGHT = 72
const LABEL_BASE_RENDER_ORDER = 20
/** Clears the island top (y = 0.08) and fog disc (y = 0.26). */
const LABEL_HEIGHT_OFFSET = 1.2
const LABEL_FONT = '600 32px system-ui, sans-serif'
/** Screen-space divisor for `sizeAttenuation: false` sprites: 256/1000 keeps
 *  labels readable without covering the scene (including on phones). */
const LABEL_SCALE_DIVISOR = 1000
const PILL_PADDING = 16
const PILL_RADIUS = 18

/** Read a CSS variable from the live theme, falling back to a sane color. */
function readCssColor(name: string, fallback: string): string {
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}

function measureTextWidth(context: CanvasRenderingContext2D, text: string): number {
  return context.measureText(text).width
}

/** Rounded pill with the label text; no font is loaded by this module. */
function drawLabelCanvas(canvas: HTMLCanvasElement, text: string, color: string): void {
  canvas.width = TEXTURE_WIDTH
  canvas.height = TEXTURE_HEIGHT

  const context = canvas.getContext('2d')
  if (!context) return

  context.clearRect(0, 0, TEXTURE_WIDTH, TEXTURE_HEIGHT)
  context.font = LABEL_FONT
  const pillWidth = Math.min(TEXTURE_WIDTH, measureTextWidth(context, text) + 2 * PILL_PADDING)
  const x = (TEXTURE_WIDTH - pillWidth) / 2
  const y = (TEXTURE_HEIGHT - TEXTURE_HEIGHT / 2) / 2
  context.beginPath()
  context.roundRect(x, y, pillWidth, TEXTURE_HEIGHT / 2, PILL_RADIUS)
  context.fillStyle = 'rgba(255, 255, 255, 0.88)'
  context.fill()
  context.fillStyle = color
  context.textAlign = 'center'
  context.textBaseline = 'middle'
  context.fillText(text, TEXTURE_WIDTH / 2, TEXTURE_HEIGHT / 2)
}

/** Nearer labels sort last so they draw on top; input is left untouched. */
export function sortLabelsByCameraDistance(
  sprites: Sprite[],
  camera: PerspectiveCamera,
): Sprite[] {
  const cameraPosition: Vector3 = camera.position
  return [...sprites].sort((a, b) => {
    const aDistance = a.position.distanceToSquared(cameraPosition)
    const bDistance = b.position.distanceToSquared(cameraPosition)
    return bDistance - aDistance
  })
}

/** Build one sprite per node, sharing textures/materials for identical text. */
export function createOceanLabels(
  THREE: typeof import('three'),
  nodes: OceanLabelNode[],
  _options: OceanLabelOptions = {},
): OceanLabelSet {
  const labelColor = readCssColor('--ocean-label-color', '#16324a')
  const textureCache = new Map<string, CanvasTexture>()
  const materialCache = new Map<string, SpriteMaterial>()

  const textures = (): CanvasTexture[] => [...textureCache.values()]
  const materials = (): SpriteMaterial[] => [...materialCache.values()]

  const labels = nodes.map((node): Sprite => {
    const cacheKey = `${node.icon} ${node.displayName}`
    let texture = textureCache.get(cacheKey)
    if (!texture) {
      const canvas = document.createElement('canvas')
      drawLabelCanvas(canvas, cacheKey, labelColor)
      texture = new THREE.CanvasTexture(canvas)
      texture.colorSpace = THREE.SRGBColorSpace
      textureCache.set(cacheKey, texture)
    }

    let material = materialCache.get(cacheKey)
    if (!material) {
      material = new THREE.SpriteMaterial({
        map: texture,
        sizeAttenuation: false,
        transparent: true,
        depthTest: false,
        depthWrite: false,
      })
      materialCache.set(cacheKey, material)
    }

    const sprite = new THREE.Sprite(material)
    sprite.position.set(node.x, node.worldRadius * 2 + LABEL_HEIGHT_OFFSET, node.z)
    sprite.frustumCulled = false
    sprite.scale.set(TEXTURE_WIDTH / LABEL_SCALE_DIVISOR, TEXTURE_HEIGHT / LABEL_SCALE_DIVISOR, 1)
    sprite.renderOrder = LABEL_BASE_RENDER_ORDER

    return sprite
  })

  let disposed = false
  return {
    sprites: labels,
    update(camera: PerspectiveCamera): void {
      if (disposed) return
      sortLabelsByCameraDistance(labels, camera).forEach((sprite, index) => {
        sprite.renderOrder = LABEL_BASE_RENDER_ORDER + index
      })
    },
    dispose(): void {
      if (disposed) return
      disposed = true
      for (const material of materials()) material.dispose()
      for (const texture of textures()) texture.dispose()
      textureCache.clear()
      materialCache.clear()
      this.sprites.length = 0
      labels.length = 0
    },
  }
}
