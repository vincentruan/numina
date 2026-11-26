<template>
  <div ref="stageRef" class="learning-ocean-3d-page" data-test="ocean3d-page">
    <RoleShimmer
      v-if="state === 'loading'"
      variant="clay-pulse"
      data-test="ocean3d-skeleton"
    />

    <div v-else-if="state === 'error'" class="ocean3d-message" data-test="ocean3d-error">
      <p>{{ t('learning.ocean3d.error') }}</p>
      <button
        type="button"
        class="ocean3d-message__retry"
        data-test="ocean3d-retry"
        @click="load"
      >
        {{ t('learning.ocean3d.retry') }}
      </button>
    </div>

    <div v-else-if="subjects.length === 0" class="ocean3d-message" data-test="ocean3d-empty">
      <p>{{ t('learning.ocean3d.empty') }}</p>
    </div>

    <template v-else>
      <header class="ocean3d-hud">
        <h1 class="ocean3d-hud__title">{{ t('learning.ocean3d.title') }}</h1>
        <p class="ocean3d-hud__subtitle">{{ t('learning.ocean3d.subtitle') }}</p>
        <p class="ocean3d-hud__hint">{{ t('learning.ocean3d.hint') }}</p>
      </header>

      <div class="ocean3d-stage">
        <KnowledgeOcean3D
          ref="oceanRef"
          :subjects="subjects"
          :domains="domains"
          :selected-subject="selectedSubject"
          :selected-domain="selectedDomain"
          :selected-topic-level="selectedTopicLevel"
          @preview-subject="onPreview"
          @preview-domain="onPreview"
          @select-subject="onSelectSubject"
          @select-domain="onSelectDomain"
          @zoom-out="onZoomOut"
          @ocean-navigation="onOceanNavigation"
        />

        <div
          v-if="selectedTopicLevel"
          class="ocean3d-topic-layer"
          data-test="ocean3d-topic-layer"
        >
          <header class="ocean3d-topic-layer__header">
            <button
              type="button"
              class="ocean3d-topic-layer__back"
              data-test="ocean3d-back"
              @click="onBackToOcean"
            >
              {{ t('learning.ocean3d.back') }}
            </button>
            <span class="ocean3d-topic-layer__count">
              {{ t('learning.ocean3d.topics', { count: topics.length }) }}
            </span>
          </header>
          <svg
            class="ocean3d-topic-layer__canvas"
            :viewBox="`0 0 ${viewWidth} ${viewHeight}`"
            preserveAspectRatio="xMidYMid meet"
          >
            <TopicConstellation
              :topics="topics"
              :edges="edges"
              :view-width="viewWidth"
              :view-height="viewHeight"
              @select-topic="onSelectTopic"
            />
          </svg>
        </div>
      </div>

      <button
        v-if="selectedSubject"
        type="button"
        class="ocean3d-zoom-out"
        data-test="ocean3d-zoom-out"
        @click="onZoomOut"
      >
        {{ t('learning.ocean3d.backToOcean') }}
      </button>
    </template>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'LearningOcean3DPage' })

import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  getMyLearningMapIndex,
  getTopicIndex,
  type TopicIndexRow,
} from '@/api/learning'
import KnowledgeOcean3D, {
  type OceanNodeRef,
} from '@/components/learning/ocean3d/KnowledgeOcean3D.vue'
import TopicConstellation, {
  type ConstellationTopic,
  type ConstellationEdge,
} from '@/components/learning/TopicConstellation.vue'
import RoleShimmer from '@/components/RoleShimmer.vue'
import { useLocalizedTopic } from '@/composables/useLocalizedTopic'
import { getContinentTheme } from '@/data/continentThemes'
import { domainLabel } from '@/utils/domainLabel'
import type {
  OceanDomain,
  OceanSubject,
} from '@/components/learning/KnowledgeOcean.vue'

const { t } = useI18n()
const { topicDisplayName } = useLocalizedTopic()
const router = useRouter()

type PageState = 'loading' | 'error' | 'content'

const state = ref<PageState>('loading')
const progressRows = ref<
  Array<{
    topic_id: string
    mastery_level: string
  }>
>([])
const topicIndex = ref<TopicIndexRow[]>([])

/** Page-local navigation state — nothing survives a remount. */
const selectedSubject = ref('')
const selectedDomain = ref('')
const selectedTopicLevel = ref(false)

const oceanRef = ref<InstanceType<typeof KnowledgeOcean3D> | null>(null)
const stageRef = ref<HTMLElement | null>(null)
const viewWidth = ref(800)
const viewHeight = ref(600)

const progressByTopicId = computed(
  () => new Map(progressRows.value.map((row) => [row.topic_id, row.mastery_level])),
)

/** Same mastery口径 as LearningMapPage: topic index rows are the denominator. */
const subjects = computed<OceanSubject[]>(() => {
  const bySubject = new Map<string, { total: number; mastered: number }>()
  for (const row of topicIndex.value) {
    const stats = bySubject.get(row.subject) ?? { total: 0, mastered: 0 }
    stats.total++
    if (progressByTopicId.value.get(row.id) === 'mastered') stats.mastered++
    bySubject.set(row.subject, stats)
  }
  return Array.from(bySubject.entries())
    .map(([id, stats]) => {
      const theme = getContinentTheme(id)
      return {
        id,
        terrain: theme.terrain,
        displayName: t(`learning.subject.${id}`, id),
        icon: theme.icon,
        topicCount: stats.total,
        masteryRatio: stats.total > 0 ? stats.mastered / stats.total : 0,
      }
    })
    .sort((a, b) => a.displayName.localeCompare(b.displayName))
})

const domains = computed<OceanDomain[]>(() => {
  if (!selectedSubject.value) return []
  const byDomain = new Map<string, { total: number; mastered: number }>()
  for (const row of topicIndex.value) {
    if (row.subject !== selectedSubject.value) continue
    const domain = row.domain || '__other__'
    const stats = byDomain.get(domain) ?? { total: 0, mastered: 0 }
    stats.total++
    if (progressByTopicId.value.get(row.id) === 'mastered') stats.mastered++
    byDomain.set(domain, stats)
  }
  return Array.from(byDomain.entries()).map(([domain, stats]) => ({
    id: `${selectedSubject.value}:${domain}`,
    subject: selectedSubject.value,
    domain,
    displayName: domainLabel(t, domain),
    topicCount: stats.total,
    masteryRatio: stats.total > 0 ? stats.mastered / stats.total : 0,
  }))
})

const topics = computed<ConstellationTopic[]>(() => {
  if (!selectedSubject.value || !selectedDomain.value) return []
  return topicIndex.value
    .filter(
      (row) =>
        row.subject === selectedSubject.value &&
        (row.domain || '__other__') === selectedDomain.value,
    )
    .map((row) => ({
      id: row.id,
      displayName:
        topicDisplayName({
          name: row.name,
          name_zh: row.name_zh,
          description: '',
          description_zh: null,
        }) || row.id,
      masteryLevel: progressByTopicId.value.get(row.id) ?? 'available',
    }))
})

/** The light index has no prerequisite detail — nodes stay isolated. */
const edges = computed<ConstellationEdge[]>(() => [])

async function load(): Promise<void> {
  state.value = 'loading'
  try {
    const [progress, index] = await Promise.all([
      getMyLearningMapIndex(),
      getTopicIndex(),
    ])
    progressRows.value = progress
    topicIndex.value = index
    state.value = 'content'
  } catch {
    state.value = 'error'
  }
}

function onPreview(): void {
  // Preview HUD belongs to T14 — deliberately a no-op here.
}

function onSelectSubject(subject: string): void {
  applySubject(subject)
}

function onSelectDomain(payload: { subject: string; domain: string }): void {
  applyDomain(payload.subject, payload.domain)
}

/** One transition function for component events and camera gestures. */
function onOceanNavigation(node: OceanNodeRef | null): void {
  if (!node) {
    applyZoomOut()
    return
  }
  const domain = domains.value.find(
    (candidate) =>
      candidate.id === node.id ||
      (candidate.subject === (node.subject ?? selectedSubject.value) &&
        candidate.domain === node.id),
  )
  if (domain) {
    applyDomain(domain.subject, domain.domain)
    return
  }
  if (node.subject) {
    applyDomain(node.subject, node.id)
    return
  }
  applySubject(node.id)
}

function applySubject(subject: string): void {
  selectedSubject.value = subject
  selectedDomain.value = ''
  selectedTopicLevel.value = false
  void oceanRef.value?.diveTo(subject)
}

function applyDomain(subject: string, domain: string): void {
  selectedSubject.value = subject
  selectedDomain.value = domain
  selectedTopicLevel.value = true
}

function onBackToOcean(): void {
  selectedTopicLevel.value = false
}

function onZoomOut(): void {
  applyZoomOut()
}

function applyZoomOut(): void {
  selectedSubject.value = ''
  selectedDomain.value = ''
  selectedTopicLevel.value = false
  void oceanRef.value?.resetCamera()
}

function onSelectTopic(payload: { id: string }): void {
  void router.push(`/learning/topic/${payload.id}`)
}

function updateViewport(): void {
  viewWidth.value = Math.max(stageRef.value?.clientWidth ?? 0, 1)
  viewHeight.value = Math.max(stageRef.value?.clientHeight ?? 0, 1)
}

onMounted(() => {
  updateViewport()
  window.addEventListener('resize', updateViewport)
  void load()
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', updateViewport)
})
</script>

<style scoped>
.learning-ocean-3d-page {
  position: relative;
  width: 100%;
  min-height: 100vh;
  background: var(--color-canvas);
}

.ocean3d-hud {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 1;
  padding: 16px;
  pointer-events: none;
  text-align: center;
}

.ocean3d-hud__title {
  margin: 0;
  color: var(--color-ink);
  font-size: 22px;
}

.ocean3d-hud__subtitle,
.ocean3d-hud__hint {
  margin: 4px 0 0;
  color: var(--color-muted);
  font-size: 13px;
}

.ocean3d-stage {
  position: relative;
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.ocean3d-topic-layer {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-canvas);
}

.ocean3d-topic-layer__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-hairline);
}

.ocean3d-topic-layer__back,
.ocean3d-zoom-out {
  min-height: 44px;
  padding: 6px 16px;
  border: 1px solid var(--color-hairline);
  border-radius: var(--radius-pill, 999px);
  background: var(--color-surface-card);
  color: var(--color-ink);
  font-size: 14px;
  cursor: pointer;
}

.ocean3d-topic-layer__count {
  color: var(--color-muted);
  font-size: 13px;
}

.ocean3d-topic-layer__canvas {
  flex: 1;
  width: 100%;
  min-height: 0;
}

.ocean3d-zoom-out {
  position: absolute;
  bottom: 16px;
  left: 16px;
  z-index: 2;
}

.ocean3d-message {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 48px 16px;
  color: var(--color-body);
  text-align: center;
}

.ocean3d-message__retry {
  min-height: 44px;
  padding: 0 24px;
  border: none;
  border-radius: var(--radius-pill, 999px);
  background: var(--color-primary);
  color: var(--color-on-dark, #fff);
  cursor: pointer;
}
</style>
