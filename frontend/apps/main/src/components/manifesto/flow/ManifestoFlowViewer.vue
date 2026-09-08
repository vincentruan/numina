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
      <template #node-flow-modifying="nodeProps">
        <FlowModifyingNode v-bind="nodeProps" />
      </template>
      <template #node-flow-effective="nodeProps">
        <FlowEffectiveNode v-bind="nodeProps" />
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
import { computed } from 'vue'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import type { Node, Edge } from '@vue-flow/core'
import FlowCreatedNode from './FlowCreatedNode.vue'
import FlowSigningNode from './FlowSigningNode.vue'
import FlowRejectedNode from './FlowRejectedNode.vue'
import FlowModifyingNode from './FlowModifyingNode.vue'
import FlowEffectiveNode from './FlowEffectiveNode.vue'
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
}>()

const NODE_SPACING = 180
const CENTER_X = 140

const { fitView } = useVueFlow()

/** Build the list of flow nodes based on current state. */
const nodes = computed<Node[]>(() => {
  const result: Node[] = []
  let index = 0

  // Node 1: Created (always present)
  result.push({
    id: 'created',
    type: 'flow-created',
    position: { x: CENTER_X, y: index * NODE_SPACING },
    data: { dimmed: props.flowState !== 'draft' ? false : false },
  })
  index++

  if (props.flowState === 'draft') {
    return result
  }

  // Node 2: Signing (current or historical)
  const isSigningActive = props.flowState === 'signing' || props.flowState === 'expired'
  result.push({
    id: 'signing',
    type: 'flow-signing',
    position: { x: CENTER_X, y: index * NODE_SPACING },
    data: {
      memberStates: props.memberStates,
      progress: props.signingProgress,
      round: props.currentRound,
      deadline: props.deadlineInfo.remaining,
      deadlineExpired: props.deadlineInfo.expired,
      isActive: isSigningActive,
      dimmed: false,
    },
  })
  index++

  if (props.flowState === 'rejected') {
    // Node 3: Rejected
    result.push({
      id: 'rejected',
      type: 'flow-rejected',
      position: { x: CENTER_X, y: index * NODE_SPACING },
      data: {
        memberStates: props.memberStates,
        dimmed: false,
      },
    })
    index++

    // Node 4: Modifying
    result.push({
      id: 'modifying',
      type: 'flow-modifying',
      position: { x: CENTER_X, y: index * NODE_SPACING },
      data: { dimmed: true },
    })
    index++
  }

  if (props.flowState === 'effective') {
    // Effective node
    result.push({
      id: 'effective',
      type: 'flow-effective',
      position: { x: CENTER_X, y: index * NODE_SPACING },
      data: { dimmed: false },
    })
  } else if (props.flowState !== 'rejected') {
    // Future effective node (dimmed)
    result.push({
      id: 'effective',
      type: 'flow-effective',
      position: { x: CENTER_X, y: index * NODE_SPACING },
      data: { dimmed: true },
    })
  }

  return result
})

/** Build edges connecting adjacent nodes. */
const edges = computed<Edge[]>(() => {
  const result: Edge[] = []
  const nodeList = nodes.value

  for (let i = 0; i < nodeList.length - 1; i++) {
    const source = nodeList[i]
    const target = nodeList[i + 1]
    const isCompleted = isNodeCompleted(source.id)
    const isError = target.id === 'rejected'

    result.push({
      id: `e-${source.id}-${target.id}`,
      source: source.id,
      target: target.id,
      type: isCompleted || isError ? 'animated' : 'completed',
      data: { isError },
    })
  }

  return result
})

function isNodeCompleted(nodeId: string): boolean {
  const state = props.flowState
  if (nodeId === 'created') {
    return state !== 'draft'
  }
  if (nodeId === 'signing') {
    return state === 'effective' || state === 'rejected'
  }
  if (nodeId === 'rejected') {
    return false // terminal for this round
  }
  return false
}

const containerHeight = computed(() => `${nodes.value.length * NODE_SPACING}px`)

let currentNodeId = computed(() => {
  switch (props.flowState) {
    case 'draft': return 'created'
    case 'signing':
    case 'expired': return 'signing'
    case 'rejected': return 'rejected'
    case 'effective': return 'effective'
    default: return 'signing'
  }
})

function onNodesInitialized() {
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
