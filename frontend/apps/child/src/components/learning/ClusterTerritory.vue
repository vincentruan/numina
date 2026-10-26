<template>
  <div
    class="cluster-territory"
    :class="territoryClasses"
    :data-cluster-domain="cluster.domain"
    :data-subject="cluster.subject"
  >
    <!-- The title duplicates the enclosing DomainSection header, so callers
         that already show the domain can suppress it. The frontier badge is
         the card's own signal and always survives. -->
    <div v-if="!hideTitle || isFrontierCluster" class="cluster-territory__header">
      <h3 v-if="!hideTitle" class="cluster-territory__title">
        <span class="cluster-territory__marker">{{ territoryIcon }}</span>
        {{ translateDomain(t, cluster.domain) }}
        <span class="cluster-territory__count">({{ items.length }})</span>
      </h3>
      <span v-if="isFrontierCluster" class="cluster-territory__frontier-badge">📍</span>
    </div>

    <p v-if="cluster.summary" class="cluster-territory__summary">{{ cluster.summary }}</p>

    <!-- Bridge badges (U4) -->
    <div v-if="bridges.length > 0" class="cluster-territory__bridges">
      <button
        v-for="bridge in displayBridges"
        :key="`${bridge.to_subject}-${bridge.to_cluster_domain}`"
        :class="['bridge-badge', { 'bridge-badge--inferred': bridge.source_type === 'inferred' }]"
        @click="$emit('bridgeTap', bridge)"
      >
        <span class="bridge-badge__icon">{{ bridge.source_type === 'inferred' ? t('learning.cluster.bridgeInferred') : t('learning.cluster.bridgeExplicit') }}</span>
        <span class="bridge-badge__label">{{ subjectLabel(bridge.to_subject) }} {{ t('learning.cluster.bridgeArrow') }} {{ translateDomain(t, bridge.to_cluster_domain) }}</span>
      </button>
      <span v-if="bridges.length > 2" class="bridge-badge__overflow">+{{ bridges.length - 2 }}</span>
    </div>

    <div class="cluster-territory__nodes">
      <TopicNode
        v-for="item in items"
        :key="item.topic.id"
        :item="item"
        :is-frontier="frontierTopicId === item.topic.id"
        @tap="$emit('topicTap', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ClusterTerritory' })

import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ProgressWithTopic, ClusterResponse, BridgeResponse } from '@/api/learning'
import TopicNode from './TopicNode.vue'
import { domainLabel as translateDomain } from '@/utils/domainLabel'

const { t } = useI18n()

const props = defineProps<{
  cluster: ClusterResponse
  items: ProgressWithTopic[]
  bridges: BridgeResponse[]
  isFrontierCluster?: boolean
  frontierTopicId?: string | null
  /** Suppress the domain title when an enclosing section already shows it. */
  hideTitle?: boolean
}>()

defineEmits<{
  topicTap: [item: ProgressWithTopic]
  bridgeTap: [bridge: BridgeResponse]
}>()

const displayBridges = computed(() => props.bridges.slice(0, 2))

/** Subject → terrain modifier class for continent styling (U3) */
const SUBJECT_TERRAIN_MAP: Record<string, string> = {
  mathematics: 'math',
  science: 'science',
  chinese: 'language',
  english: 'language',
  physics: 'science',
  chemistry: 'science',
  biology: 'science',
  history: 'social',
  geography: 'social',
  politics: 'social',
  art: 'arts',
  music: 'arts',
  physical_education: 'arts',
  information_technology: 'science',
}

const SUBJECT_ICON_MAP: Record<string, string> = {
  mathematics: '📐',
  science: '🔬',
  chinese: '📖',
  english: '🔤',
  physics: '⚡',
  chemistry: '🧪',
  biology: '🌿',
  history: '📜',
  geography: '🌍',
  politics: '🏛',
  art: '🎨',
  music: '🎵',
  physical_education: '🏃',
  information_technology: '💻',
}

const territoryClasses = computed(() => {
  const terrain = SUBJECT_TERRAIN_MAP[props.cluster.subject] ?? 'default'
  return {
    'cluster-territory--frontier': props.isFrontierCluster,
    [`territory--${terrain}`]: true,
  }
})

const territoryIcon = computed(() =>
  SUBJECT_ICON_MAP[props.cluster.subject] ?? '📚',
)

function subjectLabel(subject: string): string {
  const key = `learning.subject.${subject}`
  const translated = t(key)
  return translated === key ? subject.charAt(0).toUpperCase() + subject.slice(1) : translated
}
</script>

<style scoped>
.cluster-territory {
  background: var(--color-surface-card);
  border: 1px solid var(--color-hairline);
  border-radius: 20px;
  padding: 16px;
  position: relative;
  overflow: hidden;
  transition: box-shadow 0.2s ease;
}

/* Subject-specific terrain backgrounds (U3) */
.territory--math       { background: linear-gradient(180deg, var(--continent-terrain-math) 0%, var(--color-surface-card) 60%); border-top: 2px solid var(--color-brand-mint); }
.territory--science    { background: linear-gradient(180deg, var(--continent-terrain-science) 0%, var(--color-surface-card) 60%); border-top: 2px solid var(--color-brand-lavender); }
.territory--language   { background: linear-gradient(180deg, var(--continent-terrain-language) 0%, var(--color-surface-card) 60%); border-top: 2px solid var(--color-brand-peach); }
.territory--arts       { background: linear-gradient(180deg, var(--continent-terrain-arts) 0%, var(--color-surface-card) 60%); border-top: 2px solid var(--color-brand-pink); }
.territory--social     { background: linear-gradient(180deg, var(--continent-terrain-social) 0%, var(--color-surface-card) 60%); border-top: 2px solid var(--color-brand-ochre); }
.territory--default    { background: linear-gradient(180deg, var(--continent-terrain-default) 0%, var(--color-surface-card) 60%); border-top: 2px solid var(--color-hairline); }

.cluster-territory--frontier {
  border-color: var(--color-brand-ochre);
  box-shadow: 0 0 0 1px rgba(var(--color-brand-ochre-rgb), 0.2);
}

.cluster-territory__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.cluster-territory__title {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}

.cluster-territory__marker {
  font-size: 18px;
  line-height: 1;
}

.cluster-territory__count {
  font-size: 13px;
  font-weight: 400;
  color: var(--color-body);
}

.cluster-territory__frontier-badge {
  font-size: 16px;
}

.cluster-territory__summary {
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
  margin: 0 0 12px;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Bridge badges ── */

.cluster-territory__bridges {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.bridge-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-pill);
  background: var(--color-surface-soft);
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-body);
  cursor: pointer;
  transition: background 0.15s;
}

.bridge-badge:active {
  background: var(--color-hairline);
}

.bridge-badge--inferred {
  border-style: dashed;
  opacity: 0.75;
}

.bridge-badge--inferred:active {
  background: var(--color-hairline);
}

.bridge-badge__icon {
  font-size: 12px;
}

.bridge-badge__overflow {
  font-family: Inter, sans-serif;
  font-size: 12px;
  color: var(--color-muted-soft);
  padding: 0 4px;
}

/* ── Topic nodes grid ── */

.cluster-territory__nodes {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

/* Reduced motion — disable transitions (U3) */
@media (prefers-reduced-motion: reduce) {
  .cluster-territory {
    transition: none;
  }
}
</style>
