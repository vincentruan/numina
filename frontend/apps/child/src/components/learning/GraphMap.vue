<template>
  <div class="graph-map">
    <!-- Layout toggle -->
    <div class="graph-map__controls">
      <button
        class="graph-map__layout-btn"
        :class="{ 'graph-map__layout-btn--active': layout === 'cose' }"
        @click="switchLayout('cose')"
      >
        {{ t('learning.graphMap.layoutForce') }}
      </button>
      <button
        class="graph-map__layout-btn"
        :class="{ 'graph-map__layout-btn--active': layout === 'dagre' }"
        @click="switchLayout('dagre')"
      >
        {{ t('learning.graphMap.layoutHierarchical') }}
      </button>
    </div>

    <!-- Graph container -->
    <div ref="containerRef" class="graph-map__container" />

    <!-- Loading overlay -->
    <div v-if="loading" class="graph-map__loading">
      <van-loading size="24px" />
    </div>

    <!-- Error state -->
    <div v-if="error" class="graph-map__error">
      <p>{{ error }}</p>
      <button class="graph-map__retry-btn" @click="loadAndRender">
        {{ t('common.retry') }}
      </button>
    </div>

    <!-- Node detail popup -->
    <van-popup
      v-model:show="showPopup"
      position="bottom"
      round
      :style="{ padding: '16px', maxWidth: '400px', margin: '0 auto' }"
    >
      <div v-if="popupItem" class="graph-map__popup">
        <div class="graph-map__popup-header">
          <span
            class="graph-map__popup-dot"
            :class="`graph-map__popup-dot--${masteryStatus(popupItem)}`"
          />
          <span class="graph-map__popup-title">{{ topicDisplayName(popupItem.topic) }}</span>
          <button class="graph-map__popup-close" @click="showPopup = false">✕</button>
        </div>
        <p class="graph-map__popup-domain">{{ domainLabel(popupItem.topic.domain) }}</p>
        <p class="graph-map__popup-desc">{{ topicDescription(popupItem.topic) }}</p>
        <button class="graph-map__popup-action" @click="onPopupAction">
          {{ popupActionLabel }}
        </button>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'GraphMap' })

import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { Core } from 'cytoscape'
import type { ProgressWithTopic, DependencyEdge } from '@/api/learning'
import { getSubjectDependencies } from '@/api/learning'
import { domainLabel as translateDomain } from '@/utils/domainLabel'

const { t, locale } = useI18n()
const router = useRouter()

const props = defineProps<{
  items: ProgressWithTopic[]
  selectedSubject: string
}>()

const emit = defineEmits<{
  switchSubject: [subject: string]
}>()

// ── Refs ──

const containerRef = ref<HTMLDivElement>()
const loading = ref(false)
const error = ref('')
const layout = ref<'cose' | 'dagre'>('cose')
const showPopup = ref(false)
const popupItem = ref<ProgressWithTopic | null>(null)
const edges = ref<DependencyEdge[]>([])

let cyInstance: Core | null = null

// ── Cytoscape lazy import (core + dagre extension) ──

// Cytoscape default export is the factory function; cache it for code splitting
type CytoscapeFactory = { (opts?: Record<string, unknown>): Core; use(ext: unknown): void }
let cytoscapeLib: CytoscapeFactory | null = null
let dagreRegistered = false

async function getCytoscape(): Promise<CytoscapeFactory> {
  if (!cytoscapeLib) {
    const mod = await import('cytoscape')
    cytoscapeLib = (mod.default ?? mod) as unknown as CytoscapeFactory
  }
  return cytoscapeLib
}

async function registerDagre() {
  if (dagreRegistered) return
  const cy = await getCytoscape()
  const dagreMod = await import('cytoscape-dagre')
  cy.use(dagreMod.default)
  dagreRegistered = true
}

// ── Mastery stylesheet ──
// Maps the 5 mastery states + frontier to Cytoscape node styles,
// reusing the same Clay CSS color tokens as TopicNode.vue.

function getMasteryStylesheet() {
  // Cache computed style to avoid repeated layout-forcing reads
  const cs = getComputedStyle(document.documentElement)
  const getVar = (name: string) => cs.getPropertyValue(name).trim()

  return [
    // Domain cluster (compound parent node)
    {
      selector: 'node.domain',
      style: {
        'background-opacity': 0,
        'border-width': 1,
        'border-color': getVar('--color-hairline') || '#e5e5e5',
        'border-opacity': 0.5,
        'border-style': 'dashed' as const,
        'text-valign': 'top' as const,
        'text-halign': 'center' as const,
        'font-size': '11px',
        'font-family': 'Inter, sans-serif',
        color: getVar('--color-muted') || '#6a6a6a',
        'text-margin-y': 4,
        label: 'data(label)',
      },
    },
    // Topic nodes — default (available)
    {
      selector: 'node.topic',
      style: {
        width: 36,
        height: 36,
        'background-color': getVar('--color-brand-lavender') || '#b8a4ed',
        'border-width': 2,
        'border-color': getVar('--color-brand-lavender') || '#b8a4ed',
        label: '',
        'text-valign': 'center' as const,
        'text-halign': 'center' as const,
        'font-size': '8px',
        'font-family': 'Inter, sans-serif',
        color: '#ffffff',
        'text-wrap': 'ellipsis' as const,
        'text-max-width': '60px',
        'active-bg-color': 'rgba(0,0,0,0.1)',
        'active-bg-size': '20px',
        'active-bg-opacity': 0.2,
        'transition-property': 'background-color, border-color, width, height' as const,
        'transition-duration': '0.2s',
      },
    },
    // Mastery state classes
    {
      selector: 'node.topic.mastered',
      style: {
        'background-color': getVar('--color-brand-ochre') || '#e8b94a',
        'border-color': getVar('--color-brand-ochre') || '#e8b94a',
        'border-width': 2,
      },
    },
    {
      selector: 'node.topic.learning',
      style: {
        'background-color': getVar('--color-primary') || '#0a0a0a',
        'border-color': getVar('--color-primary') || '#0a0a0a',
      },
    },
    {
      selector: 'node.topic.available',
      style: {
        'background-color': getVar('--color-brand-lavender') || '#b8a4ed',
        'border-color': getVar('--color-brand-lavender') || '#b8a4ed',
      },
    },
    {
      selector: 'node.topic.locked',
      style: {
        'background-color': getVar('--color-body') || '#3a3a3a',
        'border-color': getVar('--color-body') || '#3a3a3a',
        opacity: 0.5,
      },
    },
    {
      selector: 'node.topic.review',
      style: {
        'background-color': getVar('--color-brand-peach') || '#ffb084',
        'border-color': getVar('--color-brand-coral') || '#ff6b5a',
      },
    },
    {
      selector: 'node.topic.frontier',
      style: {
        'border-width': 3,
        'border-color': getVar('--color-brand-coral') || '#ff6b5a',
        'border-style': 'dashed' as const,
        'background-color': getVar('--color-brand-peach') || '#ffb084',
      },
    },
    // Edges
    {
      selector: 'edge',
      style: {
        width: 1.5,
        'line-color': getVar('--color-hairline') || '#e5e5e5',
        'target-arrow-color': getVar('--color-hairline') || '#e5e5e5',
        'target-arrow-shape': 'triangle' as const,
        'arrow-scale': 0.8,
        'curve-style': 'bezier' as const,
        opacity: 0.5,
      },
    },
    // Highlighted edges (path)
    {
      selector: 'edge.path',
      style: {
        width: 2.5,
        'line-color': getVar('--color-brand-ochre') || '#e8b94a',
        'target-arrow-color': getVar('--color-brand-ochre') || '#e8b94a',
        opacity: 0.9,
      },
    },
  ]
}

// ── Build graph elements ──

function buildElements() {
  const subjectItems = props.items.filter(
    (item) => item.topic.subject === props.selectedSubject,
  )

  // Group by domain for compound parent nodes
  const domainGroups = new Map<string, ProgressWithTopic[]>()
  for (const item of subjectItems) {
    const domain = item.topic.domain || '__other__'
    if (!domainGroups.has(domain)) domainGroups.set(domain, [])
    domainGroups.get(domain)!.push(item)
  }

  const elements: Array<{
    data: Record<string, string | boolean>
    classes?: string
    position?: { x: number; y: number }
  }> = []

  // Domain compound nodes (parents)
  for (const [domain, items] of domainGroups) {
    elements.push({
      data: {
        id: `domain:${domain}`,
        label: translateDomain(t, domain),
      },
      classes: 'domain',
    })

    // Topic child nodes
    for (const item of items) {
      const status = masteryStatus(item)
      const classes = ['topic', status]
      if (isFrontierTopic(item)) classes.push('frontier')

      elements.push({
        data: {
          id: item.topic.id,
          parent: `domain:${domain}`,
          label: shortName(item),
        },
        classes: classes.join(' '),
      })
    }
  }

  // Edges from dependencies.
  // Only keep edges whose endpoints both became nodes above — the dependency
  // API returns every edge for the subject, including topics the child has no
  // progress row for (and therefore no node). Cytoscape throws on edges with a
  // nonexistent source/target, so unresolved edges are dropped here.
  const nodeIds = new Set(subjectItems.map((item) => item.topic.id))
  for (const edge of edges.value) {
    if (!nodeIds.has(edge.prerequisite_id) || !nodeIds.has(edge.topic_id)) continue
    elements.push({
      data: {
        id: `${edge.prerequisite_id}->${edge.topic_id}`,
        source: edge.prerequisite_id,
        target: edge.topic_id,
      },
    })
  }

  return elements
}

function shortName(item: ProgressWithTopic): string {
  const name = locale.value.startsWith('zh') && item.topic.name_zh
    ? item.topic.name_zh
    : item.topic.name || item.topic.topic_key
  // Truncate for graph display
  return name.length > 12 ? name.slice(0, 11) + '…' : name
}

// ── Mastery status (matches TopicNode logic) ──

type MasteryStatus = 'mastered' | 'learning' | 'available' | 'locked' | 'review'

function masteryStatus(item: ProgressWithTopic): MasteryStatus {
  const level = item.mastery_level
  if (level === 'mastered') {
    if (item.next_review_at) {
      const reviewDate = new Date(item.next_review_at)
      if (reviewDate <= new Date()) return 'review'
    }
    return 'mastered'
  }
  if (level === 'learning' || level === 'assessing') return 'learning'
  if (level === 'locked') return 'locked'
  return 'available'
}

function isFrontierTopic(item: ProgressWithTopic): boolean {
  const level = item.mastery_level
  return level === 'learning' || level === 'assessing' || level === 'available'
}

function topicDisplayName(topic: ProgressWithTopic['topic']): string {
  if (locale.value.startsWith('zh') && topic.name_zh) return topic.name_zh
  return topic.name || topic.topic_key
}

function topicDescription(topic: ProgressWithTopic['topic']): string {
  if (locale.value.startsWith('zh') && topic.description_zh) return topic.description_zh
  return topic.description || ''
}

function domainLabel(domain: string | null): string {
  return translateDomain(t, domain || '')
}

const popupActionLabel = computed(() => {
  if (!popupItem.value) return ''
  const status = masteryStatus(popupItem.value)
  switch (status) {
    case 'mastered': return t('learning.topicDetail')
    case 'learning':
    case 'available': return t('learning.startPractice')
    case 'review': return t('learning.startReview')
    case 'locked': return t('learning.cluster.prereqGoTo')
    default: return t('learning.startLearning')
  }
})

function onPopupAction() {
  if (!popupItem.value) return
  const status = masteryStatus(popupItem.value)
  showPopup.value = false
  switch (status) {
    case 'mastered':
      router.push(`/learning/topic/${popupItem.value.topic.id}`)
      break
    case 'learning':
    case 'available':
      router.push(`/learning/topic/${popupItem.value.topic.id}?action=practice`)
      break
    case 'review':
      router.push(`/learning/topic/${popupItem.value.topic.id}?action=review`)
      break
    default:
      router.push(`/learning/topic/${popupItem.value.topic.id}`)
  }
}

// ── Layout ──

function runLayout() {
  if (!cyInstance) return

  const isDagre = layout.value === 'dagre'
  const opts = isDagre
    ? {
        name: 'dagre' as const,
        rankDir: 'TB' as const,
        nodeSep: 40,
        rankSep: 60,
        animate: true,
        animationDuration: 300,
      }
    : {
        name: 'cose' as const,
        animate: true,
        animationDuration: 500,
        nodeRepulsion: () => 8000,
        idealEdgeLength: () => 80,
        edgeElasticity: () => 100,
        gravity: 0.25,
        numIter: 1000,
        padding: 30,
      }
  cyInstance.layout(opts).run()
}

function switchLayout(newLayout: 'cose' | 'dagre') {
  layout.value = newLayout
  runLayout()
}

// ── Load edges and render ──

async function loadAndRender() {
  if (!containerRef.value) return
  loading.value = true
  error.value = ''

  try {
    // Load edges for this subject
    edges.value = await getSubjectDependencies(props.selectedSubject)

    // Dynamically import cytoscape (code-split from main bundle)
    const cytoscape = await getCytoscape()

    // Register dagre layout extension
    await registerDagre()

    // Destroy previous instance
    if (cyInstance) {
      cyInstance.destroy()
      cyInstance = null
    }

    // Create new instance
    const cy = cytoscape({
      container: containerRef.value,
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
      style: getMasteryStylesheet(),
      elements: [],
    })
    cyInstance = cy

    // Build and add elements
    const elements = buildElements()
    cy.add(elements)

    // Run layout
    runLayout()

    // Bind tap event
    cy.on('tap', 'node.topic', (evt) => {
      const topicId = evt.target.id()
      const item = props.items.find((i) => i.topic.id === topicId)
      if (item) {
        popupItem.value = item
        showPopup.value = true
      }
    })

    // Fit to viewport after layout settles
    cy.on('layoutstop', () => {
      cy.fit(undefined, 30)
    })
  } catch (err) {
    console.error('[GraphMap] Failed to initialize:', err)
    error.value = t('learning.graphMap.loadError')
  } finally {
    loading.value = false
  }
}

// ── Lifecycle ──

watch(
  () => [props.selectedSubject, props.items] as const,
  () => {
    // Re-render when subject changes or items are refreshed (parent reassigns array)
    void nextTick(() => loadAndRender())
  },
)

onMounted(() => {
  void loadAndRender()
})

onBeforeUnmount(() => {
  if (cyInstance) {
    cyInstance.destroy()
    cyInstance = null
  }
})
</script>

<style scoped>
.graph-map {
  position: relative;
  width: 100%;
  display: flex;
  flex-direction: column;
}

.graph-map__controls {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}

.graph-map__layout-btn {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md, 8px);
  background: var(--color-surface-card);
  color: var(--color-body);
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  min-height: 36px;
}

.graph-map__layout-btn--active {
  background: var(--color-primary);
  color: var(--color-on-dark);
  border-color: var(--color-primary);
}

.graph-map__container {
  width: 100%;
  height: 60vh;
  min-height: 400px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-lg, 12px);
  background: var(--color-surface-soft);
  overflow: hidden;
  touch-action: none;
}

.graph-map__loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
}

.graph-map__error {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
  text-align: center;
  color: var(--color-body);
  font-family: Inter, sans-serif;
  font-size: 14px;
}

.graph-map__retry-btn {
  margin-top: 8px;
  padding: 8px 16px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-md, 8px);
  background: var(--color-surface-card);
  color: var(--color-body);
  font-family: Inter, sans-serif;
  font-size: 13px;
  cursor: pointer;
  min-height: 36px;
}

/* ── Popup ── */

.graph-map__popup {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.graph-map__popup-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.graph-map__popup-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.graph-map__popup-dot--mastered {
  background: var(--color-brand-ochre);
}

.graph-map__popup-dot--learning {
  background: var(--color-primary);
}

.graph-map__popup-dot--available {
  background: var(--color-brand-lavender);
}

.graph-map__popup-dot--locked {
  background: var(--color-body);
  opacity: 0.5;
}

.graph-map__popup-dot--review {
  background: var(--color-brand-peach);
  border: 2px solid var(--color-brand-coral);
}

.graph-map__popup-title {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
}

.graph-map__popup-close {
  background: none;
  border: none;
  font-size: 18px;
  color: var(--color-body);
  padding: 4px 8px;
  cursor: pointer;
}

.graph-map__popup-domain {
  font-size: 13px;
  color: var(--color-muted);
  margin: 0;
}

.graph-map__popup-desc {
  font-size: 14px;
  color: var(--color-body);
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.graph-map__popup-action {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 10px;
  background: var(--color-primary);
  color: var(--color-on-dark);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 4px;
  min-height: 44px;
}

.graph-map__popup-action:active {
  opacity: 0.85;
}

/* ── Reduced motion ── */

@media (prefers-reduced-motion: reduce) {
  .graph-map__container {
    transition: none;
  }
}
</style>
