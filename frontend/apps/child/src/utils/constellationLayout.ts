/**
 * Deterministic constellation layout for topic-level prerequisite graphs (R9, R10).
 *
 * Places topics as nodes in a normalized [0,1]² coordinate space, layered by
 * topological depth (prerequisites flow left-to-right). Isolated topics (no
 * edges within the set) are placed in a separate band at the bottom.
 */

export interface TopicEdge {
  from: string
  to: string
}

export interface ConstellationNode {
  id: string
  x: number
  y: number
  connected: boolean
}

export interface ConstellationEdge {
  from: string
  to: string
  path: string // SVG path data (cubic bezier)
}

export interface ConstellationLayout {
  nodes: ConstellationNode[]
  edges: ConstellationEdge[]
}

// Mulberry32 seeded PRNG (same as islandLayout.ts).
function mulberry32(seed: number): () => number {
  return function () {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

function hashString(s: string): number {
  let hash = 0
  for (let i = 0; i < s.length; i++) {
    const char = s.charCodeAt(i)
    hash = (hash << 5) - hash + char
    hash |= 0
  }
  return hash >>> 0
}

/**
 * Compute constellation layout for a set of topics and prerequisite edges.
 */
export function layoutConstellation(topics: string[], edges: TopicEdge[]): ConstellationLayout {
  if (topics.length === 0) return { nodes: [], edges: [] }

  const topicSet = new Set(topics)
  const rng = mulberry32(hashString(topics.slice().sort().join(',')))

  // Build adjacency: incoming edges per node (prerequisites).
  const incoming = new Map<string, string[]>()
  for (const t of topics) incoming.set(t, [])
  const validEdges: TopicEdge[] = []
  for (const e of edges) {
    if (topicSet.has(e.from) && topicSet.has(e.to)) {
      validEdges.push(e)
      incoming.get(e.to)!.push(e.from)
    }
  }

  // Identify isolated nodes (no edges in subset).
  const connectedIds = new Set<string>()
  for (const e of validEdges) {
    connectedIds.add(e.from)
    connectedIds.add(e.to)
  }
  const isolatedIds = new Set(topics.filter((t) => !connectedIds.has(t)))

  // Compute topological depth (longest path from roots) — only for connected nodes.
  const depthCache = new Map<string, number>()
  function computeDepth(id: string, visited: Set<string>): number {
    if (depthCache.has(id)) return depthCache.get(id)!
    if (visited.has(id)) return 0 // cycle guard
    visited.add(id)
    const prereqs = incoming.get(id) || []
    if (prereqs.length === 0) {
      depthCache.set(id, 0)
      return 0
    }
    const maxPrereqDepth = Math.max(...prereqs.map((p) => computeDepth(p, visited)))
    const depth = maxPrereqDepth + 1
    depthCache.set(id, depth)
    return depth
  }

  const connectedTopics = topics.filter((t) => connectedIds.has(t))
  const depths = new Map<string, number>()
  for (const t of connectedTopics) {
    depths.set(t, computeDepth(t, new Set()))
  }

  const maxDepth = connectedTopics.length > 0 ? Math.max(...depths.values(), 0) : 0

  // Group connected topics by depth.
  const layers = new Map<number, string[]>()
  for (const t of connectedTopics) {
    const d = depths.get(t)!
    if (!layers.has(d)) layers.set(d, [])
    layers.get(d)!.push(t)
  }

  // Assign positions.
  const nodes: ConstellationNode[] = []
  const MARGIN = 0.1
  const AVAILABLE_WIDTH = 1 - 2 * MARGIN
  const AVAILABLE_HEIGHT = 0.7 // Top 70% for layered topics, bottom 30% for isolated.

  for (const [depth, layerTopics] of layers.entries()) {
    const x = maxDepth === 0 ? 0.5 : MARGIN + (depth / maxDepth) * AVAILABLE_WIDTH
    const ySpread = AVAILABLE_HEIGHT / (layerTopics.length + 1)
    for (let i = 0; i < layerTopics.length; i++) {
      const baseY = ySpread * (i + 1)
      const jitter = (rng() - 0.5) * 0.05 // ±0.025
      nodes.push({
        id: layerTopics[i],
        x,
        y: baseY + jitter,
        connected: true,
      })
    }
  }

  // Isolated nodes at the bottom.
  const ISOLATED_Y = 0.9
  const isolatedList = [...isolatedIds]
  const isolatedXSpread = AVAILABLE_WIDTH / (isolatedList.length + 1)
  for (let i = 0; i < isolatedList.length; i++) {
    nodes.push({
      id: isolatedList[i],
      x: MARGIN + isolatedXSpread * (i + 1),
      y: ISOLATED_Y,
      connected: false,
    })
  }

  // Build edge paths (cubic bezier).
  const nodePositions = new Map(nodes.map((n) => [n.id, n]))
  const edgeLayouts: ConstellationEdge[] = validEdges.map((e) => {
    const from = nodePositions.get(e.from)!
    const to = nodePositions.get(e.to)!
    const midX = (from.x + to.x) / 2
    const path = `M ${from.x} ${from.y} C ${midX} ${from.y}, ${midX} ${to.y}, ${to.x} ${to.y}`
    return { from: e.from, to: e.to, path }
  })

  return { nodes, edges: edgeLayouts }
}
