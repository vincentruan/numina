<template>
  <div class="dna-graph-2d" ref="containerRef">
    <van-skeleton v-if="loading" :rows="5" :round="true" />
    <EmptyState v-else-if="nodes.length === 0" :description="t('learning.noGraphData')" />

    <template v-else>
      <!-- Subject filter chips -->
      <div class="subject-filter-chips" v-if="subjectFilters.length > 1">
        <van-tag
          v-for="filter in subjectFilters"
          :key="filter.subject"
          :type="filter.active ? 'primary' : 'default'"
          :plain="!filter.active"
          class="filter-chip"
          @click="toggleSubjectFilter(filter.subject)"
        >
          {{ filter.label }} ({{ filter.count }})
        </van-tag>
      </div>

      <!-- SVG Graph -->
      <div class="graph-container" :class="{ fullscreen: isFullscreen }">
        <svg
          :viewBox="viewBox"
          class="graph-svg"
          @click="handleSvgClick"
          preserveAspectRatio="xMidYMid meet"
        >
          <!-- Definitions for filters -->
          <defs>
            <filter id="glow-mastered" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="4" result="coloredBlur" />
              <feMerge>
                <feMergeNode in="coloredBlur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          <!-- Edges layer -->
          <g class="edges-layer">
            <line
              v-for="edge in visibleEdges"
              :key="`${edge.from}-${edge.to}`"
              :x1="getNode(edge.from)?.x || 0"
              :y1="getNode(edge.from)?.y || 0"
              :x2="getNode(edge.to)?.x || 0"
              :y2="getNode(edge.to)?.y || 0"
              :class="['edge', edge.strength]"
              :stroke-opacity="edge.strength === 'hard' ? 0.6 : 0.3"
              :stroke-width="edge.strength === 'hard' ? 2 : 1"
            />
          </g>

          <!-- Nodes layer -->
          <g class="nodes-layer">
            <circle
              v-for="node in visibleNodes"
              :key="node.topicId"
              :cx="node.x"
              :cy="node.y"
              :r="nodeRadius"
              :class="['node', `mastery-${node.masteryLevel}`]"
              :fill="getMasteryStyle(node.masteryLevel).color || getSubjectColor(node.subject)"
              :opacity="getMasteryStyle(node.masteryLevel).opacity"
              :filter="getMasteryStyle(node.masteryLevel).glow ? 'url(#glow-mastered)' : undefined"
              @click.stop="selectNode(node)"
            />
          </g>
        </svg>

        <!-- Fullscreen toggle -->
        <van-button
          size="small"
          type="primary"
          plain
          class="fullscreen-btn"
          @click="toggleFullscreen"
        >
          {{ isFullscreen ? t('learning.exitFullscreen') : t('learning.fullscreen') }}
        </van-button>
      </div>

      <!-- Legend -->
      <div class="legend" v-if="showLegend">
        <div class="legend-header" @click="showLegend = !showLegend">
          <span class="legend-title">{{ t('learning.legend') }}</span>
          <van-icon :name="showLegend ? 'arrow-up' : 'arrow-down'" />
        </div>
        <div class="legend-content" v-show="showLegend">
          <div class="legend-section">
            <div class="legend-subtitle">{{ t('learning.masteryLevels') }}</div>
            <div class="legend-items">
              <span class="legend-item">
                <span class="dot mastered" /> {{ t('learning.mastered') }}
              </span>
              <span class="legend-item">
                <span class="dot learning" /> {{ t('learning.learning') }}
              </span>
              <span class="legend-item">
                <span class="dot available" /> {{ t('learning.available') }}
              </span>
              <span class="legend-item">
                <span class="dot locked" /> {{ t('learning.locked') }}
              </span>
              <span class="legend-item">
                <span class="dot review" /> {{ t('learning.pendingReview') }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Node detail bottom sheet -->
      <van-popup
        v-model:show="showNodeSheet"
        position="bottom"
        round
        :style="{ maxHeight: '60vh' }"
      >
        <div class="node-detail-panel" v-if="selectedNode">
          <div class="panel-header">
            <h3 class="panel-title">{{ selectedNode.name }}</h3>
            <van-icon name="cross" class="close-btn" @click="showNodeSheet = false" />
          </div>
          <div class="panel-body">
            <div class="info-row">
              <span class="label">{{ t('learning.subject') }}:</span>
              <van-tag :color="getSubjectColor(selectedNode.subject)">
                {{ subjectLabel(selectedNode.subject) }}
              </van-tag>
            </div>
            <div class="info-row">
              <span class="label">{{ t('learning.masteryLevel') }}:</span>
              <van-tag :type="masteryTagType(selectedNode.masteryLevel)">
                {{ masteryLabel(selectedNode.masteryLevel) }}
              </van-tag>
            </div>
            <div class="info-row">
              <span class="label">{{ t('learning.ageGroup') }}:</span>
              <span>{{ selectedNode.ageGroup }}</span>
            </div>
          </div>
          <div class="panel-actions">
            <van-button type="primary" size="small" @click="handleViewTopic">
              {{ t('learning.viewTopic') }}
            </van-button>
          </div>
        </div>
      </van-popup>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import EmptyState from '@/components/common/EmptyState.vue'
import {
  useLearningDnaGraph,
  type GraphNode,
  type GraphEdge,
} from '@/composables/useLearningDnaGraph'
import type { ProgressWithTopic } from '@/api/learning'

const props = defineProps<{
  items: ProgressWithTopic[]
  loading?: boolean
}>()

const { t } = useI18n()
const router = useRouter()

const containerRef = ref<HTMLDivElement | null>(null)
const showLegend = ref(true)
const showNodeSheet = ref(false)
const isFullscreen = ref(false)

// Subject filter state
const activeSubjects = ref<Set<string>>(new Set())

const viewBox = '0 0 800 800'
const nodeRadius = 12

const { nodes, edges, selectedNode, getMasteryStyle, getSubjectColor } = useLearningDnaGraph(
  props.items,
)

// Available subjects from items
const availableSubjects = computed(() => {
  const subjects = new Set(props.items.map((item) => item.topic.subject))
  return Array.from(subjects).sort()
})

// Subject filter chips
const subjectFilters = computed(() => {
  const counts = new Map<string, number>()
  for (const item of props.items) {
    const subject = item.topic.subject
    counts.set(subject, (counts.get(subject) || 0) + 1)
  }

  return availableSubjects.value.map((subject) => ({
    subject,
    label: subjectLabel(subject),
    count: counts.get(subject) || 0,
    active: activeSubjects.value.size === 0 || activeSubjects.value.has(subject),
  }))
})

// Filtered nodes by active subjects
const visibleNodes = computed(() => {
  if (activeSubjects.value.size === 0) return nodes.value
  return nodes.value.filter((node) => activeSubjects.value.has(node.subject))
})

// Filtered edges (only show if both endpoints are visible)
const visibleEdges = computed(() => {
  const visibleIds = new Set(visibleNodes.value.map((n) => n.topicId))
  return edges.value.filter((edge) => visibleIds.has(edge.from) && visibleIds.has(edge.to))
})

function getNode(topicId: string): GraphNode | undefined {
  return nodes.value.find((n) => n.topicId === topicId)
}

function toggleSubjectFilter(subject: string) {
  if (activeSubjects.value.size === 0) {
    // First click: show only this subject
    activeSubjects.value = new Set([subject])
  } else if (activeSubjects.value.has(subject)) {
    // Clicking active: remove it
    activeSubjects.value.delete(subject)
    // If empty, reset to show all
    if (activeSubjects.value.size === 0) {
      activeSubjects.value = new Set()
    }
  } else {
    // Clicking inactive: add it
    activeSubjects.value.add(subject)
  }
}

function selectNode(node: GraphNode) {
  selectedNode.value = node
  showNodeSheet.value = true
}

function handleSvgClick() {
  // Clicking SVG background closes the sheet
  showNodeSheet.value = false
}

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
}

function subjectLabel(subject: string): string {
  const key = `learning.subject${subject.charAt(0).toUpperCase()}${subject.slice(1)}`
  const translated = t(key)
  return translated === key ? subject.charAt(0).toUpperCase() + subject.slice(1) : translated
}

function masteryTagType(level: string): 'primary' | 'success' | 'warning' | 'danger' | 'default' {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'danger' | 'default'> = {
    mastered: 'success',
    learning: 'primary',
    parent_review: 'warning',
    review: 'warning',
    available: 'default',
    locked: 'default',
  }
  return map[level] ?? 'default'
}

function masteryLabel(level: string): string {
  const map: Record<string, string> = {
    mastered: t('learning.mastered'),
    learning: t('learning.learning'),
    parent_review: t('learning.pendingReview'),
    review: t('learning.pendingReview'),
    available: t('learning.available'),
    locked: t('learning.locked'),
  }
  return map[level] ?? level
}

function handleViewTopic() {
  if (selectedNode.value) {
    // Navigate to topic detail (route depends on your app structure)
    router.push({
      path: `/baby/learning/topic/${selectedNode.value.topicId}`,
    })
  }
}

// Reset filter when items change
watch(
  () => props.items,
  () => {
    activeSubjects.value = new Set()
  },
)
</script>

<style scoped>
.dna-graph-2d {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.subject-filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 0 12px;
}

.filter-chip {
  cursor: pointer;
  transition: all 0.2s;
}

.filter-chip:active {
  transform: scale(0.95);
}

.graph-container {
  position: relative;
  width: 100%;
  aspect-ratio: 1;
  background: var(--bg-secondary, #f8f8f8);
  border-radius: 12px;
  overflow: hidden;
}

.graph-container.fullscreen {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  width: 100vw;
  height: 100vh;
  aspect-ratio: auto;
  z-index: 9999;
  background: var(--bg-primary, #fff);
  border-radius: 0;
}

.graph-svg {
  width: 100%;
  height: 100%;
  cursor: grab;
}

.graph-svg:active {
  cursor: grabbing;
}

.fullscreen-btn {
  position: absolute;
  top: 12px;
  right: 12px;
  z-index: 10;
}

/* Edges */
.edge {
  stroke: var(--text-secondary, #666);
  stroke-linecap: round;
  transition: stroke-opacity 0.2s;
}

.edge.hard {
  stroke-dasharray: none;
}

.edge.soft {
  stroke-dasharray: 4 4;
}

/* Nodes */
.node {
  cursor: pointer;
  transition: all 0.2s;
  stroke: var(--card-bg, #fff);
  stroke-width: 2;
}

.node:active {
  transform: scale(1.1);
}

/* Mastery level animations */
.mastery-mastered {
  filter: drop-shadow(0 0 8px currentColor);
}

.mastery-learning {
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.mastery-review,
.mastery-parent_review {
  animation: blink 1.5s ease-in-out infinite;
}

@keyframes blink {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

/* Legend */
.legend {
  background: var(--card-bg, #fff);
  border-radius: 8px;
  padding: 12px;
  margin: 0 12px;
}

.legend-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  user-select: none;
}

.legend-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.legend-content {
  margin-top: 12px;
}

.legend-section {
  margin-bottom: 12px;
}

.legend-subtitle {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 8px;
}

.legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-primary);
}

.dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: inline-block;
}

.dot.mastered {
  background: var(--van-primary-color, #3b82f6);
  box-shadow: 0 0 6px var(--van-primary-color, #3b82f6);
}

.dot.learning {
  background: var(--van-primary-color, #3b82f6);
  animation: pulse-dot 2s ease-in-out infinite;
}

@keyframes pulse-dot {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.dot.available {
  background: var(--van-primary-color, #3b82f6);
  opacity: 0.5;
}

.dot.locked {
  background: #9ca3af;
  opacity: 0.2;
}

.dot.review {
  background: #fbbf24;
  animation: blink-dot 1.5s ease-in-out infinite;
}

@keyframes blink-dot {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

/* Node detail panel */
.node-detail-panel {
  padding: 16px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.panel-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.close-btn {
  font-size: 20px;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px;
}

.panel-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.info-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.label {
  font-size: 14px;
  color: var(--text-secondary);
  min-width: 80px;
}

.panel-actions {
  display: flex;
  gap: 8px;
}
</style>
