/**
 * Shader sea surface — driven by the scene's single clock via `update()`.
 * This module owns no anime timeline and never calls `tickDriver`.
 */
import type { Mesh } from 'three'
import { clayColor } from '@/motion/materials'
import { OCEAN_HALF_SPAN } from './oceanGeometry'

export interface OceanWater {
  mesh: Mesh
  update(elapsedSeconds: number): void
  setReducedMotion(reduced: boolean): void
  dispose(): void
}

export interface OceanWaterOptions {
  reducedMotion?: boolean
  seaColor?: string
}

/** Low-amplitude swells in world units; highlight strength is deliberately subtle. */
const HIGHLIGHT_STRENGTH = 0.18

const VERTEX_SHADER = /* glsl */ `
  uniform float uTime;
  varying float vWave;
  varying vec3 vWorldPosition;

  void main() {
    vec4 worldPosition = modelMatrix * vec4(position, 1.0);
    float waveA = sin(worldPosition.x * 0.65 + uTime * 1.1) * 0.10;
    float waveB = cos(worldPosition.z * 0.45 - uTime * 0.8) * 0.07;
    float wave = waveA + waveB;
    worldPosition.y += wave;
    vWave = wave;
    vWorldPosition = worldPosition.xyz;
    gl_Position = projectionMatrix * viewMatrix * worldPosition;
  }
`

const FRAGMENT_SHADER = /* glsl */ `
  uniform vec3 uSeaColor;
  uniform float uHighlight;
  varying float vWave;

  void main() {
    float crest = smoothstep(-0.08, 0.17, vWave);
    vec3 color = mix(uSeaColor, vec3(1.0), uHighlight * crest);
    gl_FragColor = vec4(color, 1.0);
  }
`

/** Build the animated ocean plane using the caller's three.js namespace. */
export function createOceanWater(
  THREE: typeof import('three'),
  options: OceanWaterOptions = {},
): OceanWater {
  const geometry = new THREE.PlaneGeometry(
    2 * OCEAN_HALF_SPAN,
    2 * OCEAN_HALF_SPAN,
    32,
    32,
  )
  const uniforms = {
    uTime: { value: 0 },
    uSeaColor: {
      value: new THREE.Color(options.seaColor ?? clayColor('ocean-sea')),
    },
    uHighlight: { value: HIGHLIGHT_STRENGTH },
  }
  const material = new THREE.ShaderMaterial({
    uniforms,
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
  })
  const mesh = new THREE.Mesh(geometry, material)
  mesh.rotation.x = -Math.PI / 2
  mesh.position.y = -0.6

  let reducedMotion = options.reducedMotion ?? false
  let disposed = false

  return {
    mesh,
    update(elapsedSeconds: number): void {
      if (!reducedMotion) uniforms.uTime.value = elapsedSeconds
    },
    setReducedMotion(reduced: boolean): void {
      reducedMotion = reduced
      if (reduced) uniforms.uTime.value = 0
    },
    dispose(): void {
      if (disposed) return
      disposed = true
      geometry.dispose()
      material.dispose()
    },
  }
}
