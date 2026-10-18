import { computed, ref } from 'vue'
import type { ProgressWithTopic } from '@/api/learning'

export interface GraphNode {
  topicId: string
  name: string
  subject: string
  masteryLevel: string
  centrality: number
  ageGroup: string
  x: number
  y: number
}

export interface GraphEdge {
  from: string
  to: string
  strength: 'hard' | 'soft'
}

interface MasteryStyle {
  opacity: number
  animation?: string
  glow?: boolean
  color?: string
}

// Age group mapping to radius rings
const AGE_GROUP_RINGS: Record<string, number> = {
  low: 0.3, // inner ring
  mid: 0.6, // middle ring
  high: 0.9, // outer ring
}

// Subject color mapping
const SUBJECT_COLORS: Record<string, string> = {
  mathematics: '#3b82f6', // blue
  chinese: '#ef4444', // red
  english: '#10b981', // green
  science: '#a855f7', // purple
  history: '#f59e0b', // amber
  geography: '#06b6d4', // cyan
  physics: '#8b5cf6', // violet
  chemistry: '#ec4899', // pink
  biology: '#84cc16', // lime
}

const DEFAULT_COLOR = '#6b7280' // gray

function getSubjectColor(subject: string): string {
  return SUBJECT_COLORS[subject.toLowerCase()] || DEFAULT_COLOR
}

function ageGroupToRing(ageGroup: string): number {
  return AGE_GROUP_RINGS[ageGroup.toLowerCase()] ?? 0.6
}

/**
 * Spiral layout: angle = f(subject), radius = f(age_group)
 * Topics are arranged in concentric rings by age group,
 * with angle distributed by subject to cluster related topics.
 */
function layoutSpiral(items: ProgressWithTopic[]): GraphNode[] {
  if (items.length === 0) return []

  // Group by subject to assign angles
  const subjectGroups = new Map<string, ProgressWithTopic[]>()
  for (const item of items) {
    const subject = item.topic.subject
    if (!subjectGroups.has(subject)) {
      subjectGroups.set(subject, [])
    }
    subjectGroups.get(subject)!.push(item)
  }

  // Assign angle ranges to each subject
  const subjectAngles = new Map<string, number>()
  const subjects = Array.from(subjectGroups.keys()).sort()
  const anglePerSubject = (2 * Math.PI) / Math.max(subjects.length, 1)
  subjects.forEach((subject, idx) => {
    subjectAngles.set(subject, idx * anglePerSubject)
  })

  // Calculate positions
  const nodes: GraphNode[] = []
  const svgSize = 800 // viewBox size
  const centerX = svgSize / 2
  const centerY = svgSize / 2
  const maxRadius = svgSize * 0.4 // leave margin for labels

  for (const [subject, group] of subjectGroups.entries()) {
    const baseAngle = subjectAngles.get(subject) ?? 0
    const angleSpread = anglePerSubject / Math.max(group.length, 1)

    group.forEach((item, idx) => {
      const ageGroup = item.topic.age_group || 'mid'
      const centrality = item.topic.centrality ?? 0.5
      const ring = ageGroupToRing(ageGroup)

      // Angle: base + spread within subject group
      const angle = baseAngle + idx * angleSpread

      // Radius: ring * maxRadius, adjusted slightly by centrality
      const baseRadius = ring * maxRadius
      const centralityBoost = (centrality - 0.5) * maxRadius * 0.1
      const radius = baseRadius + centralityBoost

      const x = centerX + radius * Math.cos(angle)
      const y = centerY + radius * Math.sin(angle)

      nodes.push({
        topicId: item.topic.id,
        name: item.topic.name_zh || item.topic.name || item.topic.topic_key,
        subject,
        masteryLevel: item.mastery_level,
        centrality,
        ageGroup,
        x,
        y,
      })
    })
  }

  return nodes
}

/**
 * Extract edges from progress items (no dependencies in current API,
 * so we infer connections between topics in the same subject/domain).
 */
function extractEdges(items: ProgressWithTopic[]): GraphEdge[] {
  const edges: GraphEdge[] = []
  const topicMap = new Map(items.map((item) => [item.topic.id, item]))

  // Group by subject+domain to create logical connections
  const groups = new Map<string, string[]>()
  for (const item of items) {
    const key = `${item.topic.subject}|${item.topic.domain || ''}`
    if (!groups.has(key)) {
      groups.set(key, [])
    }
    groups.get(key)!.push(item.topic.id)
  }

  // Connect topics within each group (linear chain by centrality)
  for (const [, topicIds] of groups.entries()) {
    if (topicIds.length < 2) continue

    // Sort by centrality (high centrality first as "hub")
    const sorted = [...topicIds].sort((a, b) => {
      const topicA = topicMap.get(a)!.topic
      const topicB = topicMap.get(b)!.topic
      return (topicB.centrality ?? 0) - (topicA.centrality ?? 0)
    })

    // Connect top 3 high-centrality topics to all others (hub-and-spoke)
    const hubs = sorted.slice(0, 3)
    const spokes = sorted.slice(3)

    for (const spoke of spokes) {
      for (const hub of hubs) {
        edges.push({
          from: hub,
          to: spoke,
          strength: 'soft',
        })
      }
    }

    // Connect hubs to each other (hard edges)
    for (let i = 0; i < hubs.length; i++) {
      for (let j = i + 1; j < hubs.length; j++) {
        edges.push({
          from: hubs[i],
          to: hubs[j],
          strength: 'hard',
        })
      }
    }
  }

  return edges
}

export function useLearningDnaGraph(items: ProgressWithTopic[]) {
  const nodes = computed<GraphNode[]>(() => layoutSpiral(items))
  const edges = computed<GraphEdge[]>(() => extractEdges(items))
  const selectedNode = ref<GraphNode | null>(null)

  function getMasteryStyle(level: string): MasteryStyle {
    switch (level) {
      case 'mastered':
        return { opacity: 1, glow: true }
      case 'learning':
        return { opacity: 1, animation: 'pulse' }
      case 'available':
        return { opacity: 0.5 }
      case 'locked':
        return { opacity: 0.2, color: '#9ca3af' }
      case 'review':
      case 'parent_review':
        return { opacity: 1, animation: 'blink', color: '#fbbf24' }
      default:
        return { opacity: 0.5 }
    }
  }

  function getSubjectColorFn(subject: string): string {
    return getSubjectColor(subject)
  }

  return {
    nodes,
    edges,
    selectedNode,
    getMasteryStyle,
    getSubjectColor: getSubjectColorFn,
  }
}
