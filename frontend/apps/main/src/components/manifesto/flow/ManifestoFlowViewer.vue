<template>
  <div class="manifesto-flow-viewer" :style="{ height: containerHeight }">
    <VueFlow
      :nodes="nodes"
      :edges="edges"
      :nodes-draggable="false"
      :nodes-connectable="false"
      :elements-selectable="false"
      :zoom-on-scroll="false"
      :zoom-on-pinch="false"
      :pan-on-drag="false"
      :prevent-scrolling="true"
      :fit-view-on-init="false"
      :min-zoom="1"
      :max-zoom="1"
      @init="onFlowInit"
      @nodes-initialized="onNodesInitialized"
    >
      <template #node-flow-created="nodeProps">
        <FlowCreatedNode v-bind="nodeProps" />
      </template>
      <template #node-flow-signing="nodeProps">
        <FlowSigningNode v-bind="nodeProps" />
      </template>
      <template #node-flow-rejected="nodeProps">
        <FlowRejectedNode v-bind="nodeProps" />
      </template>
      <template #node-flow-version-update="nodeProps">
        <FlowVersionUpdateNode v-bind="nodeProps" />
      </template>
      <template #node-flow-effective="nodeProps">
        <FlowEffectiveNode v-bind="nodeProps" />
      </template>
      <template #node-flow-pending="nodeProps">
        <FlowPendingNode v-bind="nodeProps" />
      </template>
      <template #edge-animated="edgeProps">
        <AnimatedFlowEdge v-bind="edgeProps" />
      </template>
      <template #edge-completed="edgeProps">
        <CompletedFlowEdge v-bind="edgeProps" />
      </template>
    </VueFlow>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import type { Node, Edge } from '@vue-flow/core'
import FlowCreatedNode from './FlowCreatedNode.vue'
import FlowSigningNode from './FlowSigningNode.vue'
import FlowRejectedNode from './FlowRejectedNode.vue'
import FlowVersionUpdateNode from './FlowVersionUpdateNode.vue'
import FlowEffectiveNode from './FlowEffectiveNode.vue'
import FlowPendingNode from './FlowPendingNode.vue'
import AnimatedFlowEdge from './AnimatedFlowEdge.vue'
import CompletedFlowEdge from './CompletedFlowEdge.vue'
import type {
  FlowState,
  FlowMemberState,
  FlowDeadlineInfo,
  FlowSigningProgress,
} from '@/types/manifesto'

const props = defineProps<{
  flowState: FlowState
  currentRound: number
  memberStates: FlowMemberState[]
  deadlineInfo: FlowDeadlineInfo
  signingProgress: FlowSigningProgress
  creatorName?: string
  changeType?: string
  hasRejection?: boolean
  nextVersionNumber?: number
}>()

const NODE_GAP = 60
const CENTER_X = 140

const { fitView, getNodes, updateNode } = useVueFlow()

/** Estimated heights per node type (used before DOM is measured). */
const NODE_HEIGHT_ESTIMATE: Record<string, number> = {
  'flow-created': 70,
  'flow-signing': 200,
  'flow-rejected': 100,
  'flow-version-update': 80,
  'flow-effective': 70,
  'flow-pending': 70,
}

/** Build the list of flow nodes based on current state. */
const nodes = computed<Node[]>(() => {
  const result: Node[] = []
  let y = 0
  const state = props.flowState
  const isDraft = state === 'draft'
  const isSigning = state === 'signing' || state === 'expired'
  const isRejected = state === 'rejected'
  const isEffective = state === 'effective'

  function addNode(id: string, type: string, data: Record<string, unknown>) {
    result.push({
      id,
      type,
      position: { x: CENTER_X, y },
      data,
    } as Node)
    y += (NODE_HEIGHT_ESTIMATE[type] ?? 100) + NODE_GAP
  }

  // Node 1: Created (always present)
  addNode('created', 'flow-created', {
    changeType: props.changeType ?? 'initial',
    versionNumber: props.currentRound,
    creatorName: props.creatorName ?? '',
    createdAt: '',
    dimmed: false,
  })

  if (isDraft) {
    return result
  }

  // Node 2: Signing (current round)
  addNode('signing', 'flow-signing', {
    memberStates: props.memberStates,
    progress: props.signingProgress,
    round: props.currentRound,
    deadline: props.deadlineInfo.remaining,
    deadlineExpired: props.deadlineInfo.expired,
    isActive: isSigning,
    dimmed: false,
  })

  if (isRejected) {
    addNode('rejected', 'flow-rejected', {
      memberStates: props.memberStates,
      dimmed: false,
    })

    addNode('versionUpdate', 'flow-version-update', {
      updaterName: props.creatorName ?? '',
      currentVersion: props.currentRound,
      nextVersion: props.nextVersionNumber ?? props.currentRound + 1,
      dimmed: false,
    })

    addNode('signing-next', 'flow-signing', {
      memberStates: props.memberStates,
      progress: props.signingProgress,
      round: props.nextVersionNumber ?? props.currentRound + 1,
      deadline: props.deadlineInfo.remaining,
      deadlineExpired: props.deadlineInfo.expired,
      isActive: false,
      dimmed: true,
    })
  }

  if (isEffective) {
    addNode('effective', 'flow-effective', { dimmed: false })
  } else if (!isRejected && !isDraft) {
    addNode('pending', 'flow-pending', {
      deadline: props.deadlineInfo.remaining,
      deadlineExpired: props.deadlineInfo.expired,
      dimmed: true,
    })
  }

  return result
})

/** Build edges connecting nodes. */
const edges = computed<Edge[]>(() => {
  const result: Edge[] = []
  const nodeList = nodes.value

  // Linear edges between adjacent nodes
  for (let i = 0; i < nodeList.length - 1; i++) {
    const source = nodeList[i]
    const target = nodeList[i + 1]
    const isCompleted = isNodeCompleted(source.id)
    const isError = target.id === 'rejected'

    // For the loop-back edge (versionUpdate → signing-next), use animated
    const isLoopBack = source.id === 'versionUpdate' && target.id === 'signing-next'

    result.push({
      id: `e-${source.id}-${target.id}`,
      source: source.id,
      target: target.id,
      type: (!isCompleted || isError || isLoopBack) ? 'animated' : 'completed',
      data: { isError },
    })
  }

  return result
})

function isNodeCompleted(nodeId: string): boolean {
  const state = props.flowState
  if (nodeId === 'created') return state !== 'draft'
  if (nodeId === 'signing') return state === 'effective' || state === 'rejected'
  if (nodeId === 'rejected') return false
  if (nodeId === 'versionUpdate') return true
  if (nodeId === 'signing-next') return false
  if (nodeId === 'pending') return false
  return false
}

const containerHeightPx = ref(0)
const containerHeight = computed(() => `${containerHeightPx.value || nodes.value.length * (NODE_GAP + 100)}px`)

const currentNodeId = computed(() => {
  switch (props.flowState) {
    case 'draft': return 'created'
    case 'signing':
    case 'expired': return 'signing'
    case 'rejected': return 'rejected'
    case 'effective': return 'effective'
    default: return 'signing'
  }
})

function onFlowInit() {
  // Inject arrow marker definitions into Vue Flow's SVG <defs>
  const svg = document.querySelector('.vue-flow > svg')
  if (!svg) return
  let defs = svg.querySelector('defs')
  if (!defs) {
    defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs')
    svg.insertBefore(defs, svg.firstChild)
  }
  defs.innerHTML = `
    <marker id="arrow-primary" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--van-primary-color, #646cff)" />
    </marker>
    <marker id="arrow-muted" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--text-secondary, #c0c0c0)" />
    </marker>
  `
}

function onNodesInitialized() {
  // Measure actual DOM heights and reposition nodes with consistent gaps
  const domNodes = getNodes.value
  const measured: { id: string; y: number }[] = []
  let nextY = 0

  for (const node of domNodes) {
    const el = document.querySelector(`[data-id="${node.id}"]`) as HTMLElement | null
    const height = el?.offsetHeight ?? (NODE_HEIGHT_ESTIMATE[node.type as string] ?? 100)
    measured.push({ id: node.id, y: nextY })
    nextY += height + NODE_GAP
  }

  if (measured.length > 0) {
    for (const m of measured) {
      updateNode(m.id, { position: { x: CENTER_X, y: m.y } })
    }
    containerHeightPx.value = nextY
  }

  const targetNode = currentNodeId.value
  fitView({
    nodes: [targetNode],
    padding: 0.3,
    duration: 200,
  })
}
</script>

<style scoped>
.manifesto-flow-viewer {
  width: 100%;
  overflow: hidden;
}

.manifesto-flow-viewer :deep(.vue-flow) {
  background: transparent;
}

.manifesto-flow-viewer :deep(.vue-flow__node) {
  cursor: default;
}
</style>
