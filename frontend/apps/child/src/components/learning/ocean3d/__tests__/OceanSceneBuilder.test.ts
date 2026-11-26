/** Ocean scene builder — geometry, fog, picking, timeline and disposal. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Box3, Group, Mesh, type Material, type Object3D } from 'three'
import {
  OCEAN_HALF_SPAN,
  fogOpacityForMastery,
  layoutOceanDomains,
  layoutOceanNodes,
  type OceanDomainNode,
} from '../oceanGeometry'

const { timelineFactory } = vi.hoisted(() => {
  const timeline = { add: vi.fn(), revert: vi.fn() }
  return { timelineFactory: vi.fn(() => timeline) }
})

vi.mock('@/motion/animeDriver', () => ({
  createChildTimeline: timelineFactory,
}))
vi.mock('@/components/learning/scene3d/resolveThemeColor', () => ({
  resolveThemeColor: (subject: string) =>
    subject === 'math' ? '#123456' : '#abcdef',
}))

import { createChildTimeline } from '@/motion/animeDriver'
import { buildOceanScene, disposeOceanScene } from '../OceanSceneBuilder'

const subjects = [
  {
    id: 'math',
    terrain: 'logic',
    displayName: 'Math',
    icon: '📐',
    topicCount: 2,
    masteryRatio: 0.25,
  },
  {
    id: 'science',
    terrain: 'nature',
    displayName: 'Science',
    icon: '🔬',
    topicCount: 4,
    masteryRatio: 1,
  },
]

beforeEach(() => {
  timelineFactory.mockClear()
  timelineFactory.mock.results.length = 0
  const timeline = timelineFactory()
  timeline.add.mockClear()
  timeline.revert.mockClear()
  timelineFactory.mockClear()
})

afterEach(() => {
  vi.resetModules()
})

describe('buildOceanScene (L0)', () => {
  it('builds one pick target, one fog ring and one fog layer per island', () => {
    const nodes = layoutOceanNodes(subjects)
    const scene = buildOceanScene(nodes)

    expect(scene.islands).toEqual(nodes)
    expect(scene.pickTargets).toHaveLength(nodes.length)
    expect(scene.root.children).toHaveLength(nodes.length)

    for (let i = 0; i < nodes.length; i++) {
      const target = scene.pickTargets[i]
      const group = scene.root.children[i] as Group
      expect(target.userData.islandId).toBe(nodes[i].id)
      expect(target.userData.domainId).toBeUndefined()
      expect(group.position.x).toBe(nodes[i].x)
      expect(group.position.z).toBe(nodes[i].z)
      expect(target).toBe(group)
      expect(target.position.x).toBe(nodes[i].x)
      expect(target.position.z).toBe(nodes[i].z)

      const fogMeshes: Mesh[] = []
      scene.root.children[i].traverse((child) => {
        if (child instanceof Mesh && child.userData.type === 'fog')
          fogMeshes.push(child)
      })
      expect(fogMeshes).toHaveLength(1)
    }
    disposeOceanScene(scene)
  })

  it('uses resolved theme colors and a valid material color', () => {
    const [node] = layoutOceanNodes([subjects[0]])
    const scene = buildOceanScene([node])
    const islandMesh = (scene.pickTargets[0] as Group).children.find(
      (child) => child instanceof Mesh && child.userData.type === 'island',
    ) as Mesh
    const material = islandMesh.material as unknown as {
      color: { getHexString(): string }
    }
    // Builder resolves colors via scene3d/resolveThemeColor(subject.terrain).
    expect(material.color.getHexString()).toBe('abcdef')
    disposeOceanScene(scene)
  })

  it('maps mastery to fog opacity and depthWrite false', () => {
    const scene = buildOceanScene(layoutOceanNodes(subjects))
    for (let i = 0; i < subjects.length; i++) {
      const islandGroup = scene.root.children[i]
      const fog = islandGroup.children.find(
        (child) => child instanceof Mesh && child.userData.type === 'fog',
      ) as Mesh
      const material = fog.material as { opacity: number; depthWrite: boolean }
      expect(material.opacity).toBeCloseTo(
        fogOpacityForMastery(subjects[i].masteryRatio),
      )
      expect(material.depthWrite).toBe(false)
    }
    disposeOceanScene(scene)
  })

  it('encodes mastery in the ring arc', () => {
    const scene = buildOceanScene(layoutOceanNodes(subjects))
    const arcLengths = scene.root.children.map((islandGroup) => {
      const ring = islandGroup.children.find(
        (child) =>
          child instanceof Mesh && child.userData.type === 'masteryRing',
      ) as Mesh
      const geometry = ring.geometry as unknown as {
        parameters: { thetaLength: number }
      }
      return geometry.parameters.thetaLength
    })
    expect(arcLengths[0]).toBeCloseTo(Math.PI / 2)
    expect(arcLengths[1]).toBeCloseTo(Math.PI * 2)
    disposeOceanScene(scene)
  })

  it('creates exactly one bob timeline for all islands, and none for reduced motion', () => {
    const scene = buildOceanScene(layoutOceanNodes(subjects))
    expect(createChildTimeline).toHaveBeenCalledTimes(1)
    const timeline = timelineFactory.mock.results[0]?.value as {
      add: ReturnType<typeof vi.fn>
      revert: ReturnType<typeof vi.fn>
    }
    expect(timeline.add).toHaveBeenCalledTimes(1)
    expect(timeline.revert).not.toHaveBeenCalled()
    disposeOceanScene(scene)
    expect(timeline.revert).toHaveBeenCalledTimes(1)

    const reduced = buildOceanScene(layoutOceanNodes(subjects), {
      reducedMotion: true,
    })
    expect(createChildTimeline).toHaveBeenCalledTimes(1)
    disposeOceanScene(reduced)
    expect(timeline.revert).toHaveBeenCalledTimes(1)
  })

  it('creates no timeline for an empty scene', () => {
    const scene = buildOceanScene([])
    expect(createChildTimeline).not.toHaveBeenCalled()
    disposeOceanScene(scene)
  })

  it('disposes all unique geometry/material references and clears the group', () => {
    const scene = buildOceanScene(layoutOceanNodes(subjects))
    const disposals: Array<ReturnType<typeof vi.fn>> = []
    scene.root.traverse((object) => {
      if (!(object instanceof Mesh)) return
      const geometry = object.geometry as { dispose(): void }
      const geometrySpy = vi.spyOn(geometry, 'dispose')
      const materialSpies = (
        Array.isArray(object.material) ? object.material : [object.material]
      ).map((material) =>
        vi.spyOn(material as Material & { dispose(): void }, 'dispose'),
      )
      disposals.push(geometrySpy, ...materialSpies)
    })
    expect(disposals.length).toBeGreaterThan(0)

    disposeOceanScene(scene)
    for (const spy of disposals) expect(spy).toHaveBeenCalledTimes(1)
    expect(scene.root.children).toHaveLength(0)
    expect(scene.pickTargets).toHaveLength(0)
  })

  it('scene.dispose() is equivalent to disposeOceanScene()', () => {
    const scene = buildOceanScene(layoutOceanNodes([subjects[0]]))
    scene.dispose()
    expect(scene.root.children).toHaveLength(0)
  })
})

describe('buildOceanScene (L1 domainMode)', () => {
  function domainNodes(): OceanDomainNode[] {
    return layoutOceanDomains(
      [subjects[0], subjects[1], { ...subjects[0], id: 'history' }].map(
        (subject) => ({
          id: subject.id,
          subject: subject.id,
          domain: subject.id,
          displayName: subject.displayName,
          topicCount: subject.topicCount,
          masteryRatio: subject.masteryRatio,
        }),
      ),
    )
  }

  it('builds one domain tile per node with domainId/subject pick metadata', () => {
    const nodes = domainNodes()
    const scene = buildOceanScene(nodes, { domainMode: true })

    expect(scene.islands).toEqual(nodes)
    expect(scene.pickTargets).toHaveLength(nodes.length)
    for (let i = 0; i < nodes.length; i++) {
      const target = scene.pickTargets[i] as Mesh
      const group = scene.root.children[i] as Group
      expect(target.userData.domainId).toBe(nodes[i].id)
      expect(target.userData.subject).toBe(nodes[i].subject)
      expect(target.userData.islandId).toBeUndefined()
      expect(group.position.x).toBe(nodes[i].x)
      expect(group.position.z).toBe(nodes[i].z)
      expect(target).toBe(group)
      expect(target.position.x).toBe(nodes[i].x)
      expect(target.position.z).toBe(nodes[i].z)
    }
    disposeOceanScene(scene)
  })

  it('leaves a water lane between neighboring tiles', () => {
    const nodes = domainNodes()
    const scene = buildOceanScene(nodes, { domainMode: true })
    const boxes = scene.pickTargets.map((target) =>
      new Box3().setFromObject(target),
    )

    expect(OCEAN_HALF_SPAN).toBe(10)
    for (let i = 0; i < boxes.length; i++) {
      for (let j = i + 1; j < boxes.length; j++) {
        const gapX = Math.max(
          boxes[i].min.x - boxes[j].max.x,
          boxes[j].min.x - boxes[i].max.x,
        )
        const gapZ = Math.max(
          boxes[i].min.z - boxes[j].max.z,
          boxes[j].min.z - boxes[i].max.z,
        )
        expect(Math.max(gapX, gapZ)).toBeGreaterThan(0.1)
      }
    }
    disposeOceanScene(scene)
  })

  it('adds fog layers to domain tiles too', () => {
    const scene = buildOceanScene(domainNodes(), { domainMode: true })
    let fogCount = 0
    scene.root.traverse((object: Object3D) => {
      if (object instanceof Mesh && object.userData.type === 'fog') fogCount++
    })
    expect(fogCount).toBe(3)
    disposeOceanScene(scene)
  })
})
