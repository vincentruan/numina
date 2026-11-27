/** Shader water — uniforms, reduced motion, timeline isolation and disposal. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import * as THREE from 'three'
import { getRootTimeline, revertAll } from '@/motion/animeDriver'
import { OCEAN_HALF_SPAN } from '../oceanGeometry'

beforeEach(() => {
  revertAll()
  vi.stubGlobal('getComputedStyle', () => ({
    getPropertyValue: (name: string) =>
      name === '--ocean-sea-color' ? '#cfe8f5' : '',
  }))
})

afterEach(() => {
  revertAll()
  vi.unstubAllGlobals()
})

describe('createOceanWater', () => {
  it('builds a large plane rotated onto X/Z at y = -0.6', async () => {
    const { createOceanWater } = await import('../OceanWater')
    const water = createOceanWater(THREE)

    expect(water.mesh).toBeInstanceOf(THREE.Mesh)
    const geometry = water.mesh.geometry as THREE.PlaneGeometry
    expect(geometry).toBeInstanceOf(THREE.PlaneGeometry)
    expect(geometry.parameters.width).toBe(2 * OCEAN_HALF_SPAN)
    expect(geometry.parameters.height).toBe(2 * OCEAN_HALF_SPAN)
    expect(geometry.parameters.widthSegments).toBe(32)
    expect(geometry.parameters.heightSegments).toBe(32)
    expect(water.mesh.rotation.x).toBeCloseTo(-Math.PI / 2)
    expect(water.mesh.position.y).toBe(-0.6)
    water.dispose()
  })

  it('reads the default sea color from the clay ocean-sea token', async () => {
    const { createOceanWater } = await import('../OceanWater')
    const water = createOceanWater(THREE)
    const material = water.mesh.material as THREE.ShaderMaterial

    expect(material.uniforms.uSeaColor.value.getHexString()).toBe(
      new THREE.Color('#cfe8f5').getHexString(),
    )
    expect(material.uniforms.uHighlight.value).toBeGreaterThan(0)
    expect(material.vertexShader).toContain('uTime')
    expect(material.vertexShader).toContain('sin')
    expect(material.vertexShader).toContain('cos')
    expect(material.fragmentShader).toContain('uSeaColor')
    expect(material.fragmentShader).toContain('uHighlight')
    expect(material.fragmentShader).toContain('#include <colorspace_fragment>')
    water.dispose()
  })

  it('writes uTime from update without creating an anime timeline', async () => {
    const { createOceanWater } = await import('../OceanWater')
    const water = createOceanWater(THREE, { seaColor: '#123456' })
    const material = water.mesh.material as THREE.ShaderMaterial

    expect(material.uniforms.uTime.value).toBe(0)
    water.update(1.5)
    expect(material.uniforms.uTime.value).toBe(1.5)
    water.update(4.25)
    expect(material.uniforms.uTime.value).toBe(4.25)
    expect(material.uniforms.uSeaColor.value.getHexString()).toBe('123456')
    expect(getRootTimeline()).toBeNull()
    water.dispose()
  })

  it('freezes uTime at zero under reduced motion and resumes when toggled', async () => {
    const { createOceanWater } = await import('../OceanWater')
    const water = createOceanWater(THREE, { reducedMotion: true })
    const material = water.mesh.material as THREE.ShaderMaterial

    water.update(9)
    expect(material.uniforms.uTime.value).toBe(0)

    water.setReducedMotion(false)
    water.update(2.5)
    expect(material.uniforms.uTime.value).toBe(2.5)

    water.setReducedMotion(true)
    water.update(6)
    expect(material.uniforms.uTime.value).toBe(0)
    water.dispose()
  })

  it('disposes geometry and material exactly once', async () => {
    const { createOceanWater } = await import('../OceanWater')
    const water = createOceanWater(THREE)
    const geometry = water.mesh.geometry as THREE.PlaneGeometry
    const material = water.mesh.material as THREE.ShaderMaterial
    const geometrySpy = vi.spyOn(geometry, 'dispose')
    const materialSpy = vi.spyOn(material, 'dispose')

    water.dispose()

    expect(geometrySpy).toHaveBeenCalledTimes(1)
    expect(materialSpy).toHaveBeenCalledTimes(1)

    water.dispose()
    expect(geometrySpy).toHaveBeenCalledTimes(1)
    expect(materialSpy).toHaveBeenCalledTimes(1)
  })
})
