<template>
  <div class="cluster-map">
    <!-- Progress bar (U5) -->
    <div v-if="totalCount > 0" class="cluster-map__progress">
      <div class="cluster-map__progress-bar">
        <div
          class="cluster-map__progress-fill"
          :class="{ 'cluster-map__progress-fill--complete': masteredCount === totalCount }"
          :style="{ width: progressPercent + '%' }"
        />
      </div>
      <span class="cluster-map__progress-text">
        {{ progressText }}
      </span>
    </div>

    <!-- All mastered celebration (U5) -->
    <div v-if="masteredCount === totalCount && totalCount > 0" class="cluster-map__celebration">
      {{ t('learning.cluster.allMastered') }}
    </div>

    <!-- Frontier banner (U5) -->
    <div v-if="frontierTopic && masteredCount < totalCount" class="cluster-map__frontier-banner">
      {{ t('learning.cluster.frontierBanner') }}
    </div>

    <!-- Empty state -->
    <EmptyState
      v-if="domainGroups.length === 0 && !loading"
      :illustration="noRecordsSvg"
      :text="t('learning.cluster.empty')"
    />

    <!-- Domain-grouped territory list -->
    <div v-else class="cluster-map__domains">
      <DomainSection
        v-for="group in domainGroups"
        :key="group.domainKey"
        :domain="extractDomain(group.domainKey)"
        :domain-label="domainLabel(group.domainKey)"
        :mastered-count="group.masteredCount"
        :total-count="group.totalCount"
        :expanded="expandedDomains.has(group.domainKey)"
        @toggle="toggleDomain(group.domainKey)"
      >
        <div class="cluster-map__territories">
          <ClusterTerritory
            v-for="territory in group.territories"
            :key="territory.cluster.id"
            :cluster="territory.cluster"
            :items="territory.items"
            :bridges="territory.bridges"
            :is-frontier-cluster="frontierClusterDomain === territory.cluster.domain"
            :frontier-topic-id="frontierTopic?.topic.id ?? null"
            @topic-tap="onTopicTap"
            @bridge-tap="onBridgeTap"
          />
        </div>
      </DomainSection>
    </div>

    <!-- Prerequisite guidance bottom sheet (U3) -->
    <PrerequisiteGuidance
      v-if="prereqTopic"
      :topic="prereqTopic"
      :all-items="props.items"
      @close="prereqTopic = null"
      @go-to="onPrereqGoTo"
    />
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ClusterMap' })

import { ref, reactive, computed, watch, onMounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type {
  ProgressWithTopic,
  ClusterResponse,
  BridgeResponse,
} from '@/api/learning'
import { getClusters, getBridges } from '@/api/learning'
import ClusterTerritory from './ClusterTerritory.vue'
import DomainSection from './DomainSection.vue'
import PrerequisiteGuidance from './PrerequisiteGuidance.vue'
import EmptyState from '@/components/EmptyState.vue'
import { noRecordsSvg } from '@numina/assets/empty-states'

const { t } = useI18n()
const router = useRouter()

const props = defineProps<{
  items: ProgressWithTopic[]
  selectedSubject: string
}>()

const emit = defineEmits<{
  switchSubject: [subject: string]
}>()

const loading = ref(false)
const clusters = ref<ClusterResponse[]>([])
const bridges = ref<BridgeResponse[]>([])
const prereqTopic = ref<ProgressWithTopic | null>(null)
const scrollTargetDomain = ref<string | null>(null)

// ── Collapse state (KTD6) ──

const expandedDomains = reactive(new Set<string>())
const domainDefaultsInitialized = new Set<string>()

// ── Data loading ──

async function load() {
  loading.value = true
  try {
    const [clusterData, bridgeData] = await Promise.all([
      getClusters(props.selectedSubject),
      getBridges(props.selectedSubject),
    ])
    clusters.value = clusterData
    bridges.value = bridgeData
  } catch {
    clusters.value = []
    bridges.value = []
  } finally {
    loading.value = false
  }
}

watch(() => props.selectedSubject, () => {
  load()
})

onMounted(() => {
  load()
})

// ── Topic-to-cluster matching ──

interface Territory {
  cluster: ClusterResponse
  items: ProgressWithTopic[]
  bridges: BridgeResponse[]
}

interface DomainGroup {
  domainKey: string
  territories: Territory[]
  totalCount: number
  masteredCount: number
}

/** Extract raw domain name from composite key "subject:domain". */
function extractDomain(domainKey: string): string {
  return domainKey.split(':').slice(1).join(':')
}

function buildTerritories(): Territory[] {
  const subjectItems = props.items.filter(
    (item) => item.topic.subject === props.selectedSubject,
  )

  const clusterMap = new Map<string, ProgressWithTopic[]>()
  const unmatched: ProgressWithTopic[] = []

  for (const item of subjectItems) {
    const domain = item.topic.domain ?? ''
    const matchingCluster =
      clusters.value.find(
        (c) =>
          c.subject === item.topic.subject &&
          c.domain === domain &&
          c.age_group === item.topic.age_group,
      ) ??
      clusters.value.find(
        (c) => c.subject === item.topic.subject && c.domain === domain,
      )
    if (matchingCluster) {
      if (!clusterMap.has(matchingCluster.id)) clusterMap.set(matchingCluster.id, [])
      clusterMap.get(matchingCluster.id)!.push(item)
    } else {
      unmatched.push(item)
    }
  }

  const result: Territory[] = clusters.value
    .filter((c) => clusterMap.has(c.id))
    .map((c) => ({
      cluster: c,
      items: clusterMap.get(c.id)!,
      bridges: bridges.value.filter((b) => b.from_cluster_domain === c.domain),
    }))

  if (unmatched.length > 0) {
    result.push({
      cluster: {
        id: '__other__',
        subject: props.selectedSubject,
        domain: '__other__',
        age_range_start: null,
        age_group: '',
        summary: '',
        topic_count: unmatched.length,
      },
      items: unmatched,
      bridges: [],
    })
  }

  return result
}

const domainGroups = computed<DomainGroup[]>(() => {
  const territories = buildTerritories()
  const groups = new Map<string, DomainGroup>()

  for (const territory of territories) {
    const domain = territory.cluster.domain
    const key = `${props.selectedSubject}:${domain}`

    if (!groups.has(key)) {
      groups.set(key, {
        domainKey: key,
        territories: [],
        totalCount: 0,
        masteredCount: 0,
      })
    }

    const group = groups.get(key)!
    group.territories.push(territory)
    group.totalCount += territory.items.length
    group.masteredCount += territory.items.filter(
      (i) => i.mastery_level === 'mastered',
    ).length
  }

  return [...groups.values()]
})

// ── Progress (U5) ──

const subjectItems = computed(() =>
  props.items.filter((item) => item.topic.subject === props.selectedSubject),
)

// ── Collapse defaults (KTD3) ──

/** Reset default-initialization tracking when data changes so new items can
 *  flip a domain from collapsed to expanded. */
watch(
  () => [domainGroups.value, subjectItems.value.length],
  () => {
    domainDefaultsInitialized.clear()
  },
)

/** Reset when switching subjects so the new subject's domains get defaults,
 *  but do NOT clear expandedDomains — R5 requires global persistence. */
watch(() => props.selectedSubject, () => {
  domainDefaultsInitialized.clear()
})

function initializeDomainDefaults() {
  if (subjectItems.value.length === 0) return

  for (const group of domainGroups.value) {
    if (domainDefaultsInitialized.has(group.domainKey)) continue

    const hasActive = group.territories.some((territory) =>
      territory.items.some((i) => {
        const level = i.mastery_level
        if (level === 'learning' || level === 'assessing' || level === 'available') return true
        if (level === 'mastered' && i.next_review_at && new Date(i.next_review_at) <= new Date()) return true
        return false
      }),
    )

    if (hasActive) {
      expandedDomains.add(group.domainKey)
    }

    domainDefaultsInitialized.add(group.domainKey)
  }
}

function toggleDomain(domainKey: string) {
  if (expandedDomains.has(domainKey)) {
    expandedDomains.delete(domainKey)
  } else {
    expandedDomains.add(domainKey)
  }
}

// ── Progress (derived from subjectItems) ──

const totalCount = computed(() => subjectItems.value.length)

const masteredCount = computed(() =>
  subjectItems.value.filter((i) => i.mastery_level === 'mastered').length,
)

const progressPercent = computed(() =>
  totalCount.value > 0 ? Math.round((masteredCount.value / totalCount.value) * 100) : 0,
)

const progressText = computed(() =>
  t('learning.cluster.progress', { mastered: masteredCount.value, total: totalCount.value }),
)

// ── Frontier detection (U5) ──

const frontierTopic = computed<ProgressWithTopic | null>(() => {
  const learning = subjectItems.value.find((i) => i.mastery_level === 'learning' || i.mastery_level === 'assessing')
  if (learning) return learning
  const available = subjectItems.value.find((i) => i.mastery_level === 'available')
  if (available) return available
  const review = subjectItems.value.find(
    (i) => i.mastery_level === 'mastered' && i.next_review_at && new Date(i.next_review_at) <= new Date(),
  )
  if (review) return review
  return null
})

const frontierClusterDomain = computed(() => {
  if (!frontierTopic.value) return null
  const ft = frontierTopic.value.topic
  const match = clusters.value.find(
    (c) => c.subject === ft.subject && c.domain === (ft.domain ?? '') && c.age_group === ft.age_group,
  )
  return match?.domain ?? null
})

// ── Auto-scroll to frontier on load, or to bridge target ──

let frontierScrolled = false

watch(domainGroups, () => {
  initializeDomainDefaults()

  const bridgeTarget = scrollTargetDomain.value
  const targetDomain =
    bridgeTarget || (frontierScrolled ? null : frontierClusterDomain.value)
  if (!targetDomain) return

  const targetKey = `${props.selectedSubject}:${targetDomain}`

  // Auto-expand collapsed domain before scrolling (R6)
  if (!expandedDomains.has(targetKey)) {
    expandedDomains.add(targetKey)
    // Wait for DOM to render expanded content — nextTick resolves after
    // the reactive change has been flushed.
    nextTick(() => {
      const el = document.querySelector(
        `.domain-section[data-domain="${CSS.escape(targetDomain)}"]`,
      )
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        if (bridgeTarget) {
          scrollTargetDomain.value = null
        } else {
          frontierScrolled = true
        }
      }
    })
    return
  }

  const el = document.querySelector(
    `.domain-section[data-domain="${CSS.escape(targetDomain)}"]`,
  )
  if (!el) return

  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  if (bridgeTarget) {
    scrollTargetDomain.value = null
  } else {
    frontierScrolled = true
  }
}, { flush: 'post' })

// ── Tap handlers (U3) ──

function masteryStatus(item: ProgressWithTopic): string {
  const level = item.mastery_level
  if (level === 'mastered') {
    if (item.next_review_at && new Date(item.next_review_at) <= new Date()) return 'review'
    return 'mastered'
  }
  if (level === 'learning' || level === 'assessing') return 'learning'
  if (level === 'locked') return 'locked'
  return 'available'
}

function onTopicTap(item: ProgressWithTopic) {
  const status = masteryStatus(item)
  switch (status) {
    case 'mastered':
      router.push(`/learning/topic/${item.topic.id}`)
      break
    case 'learning':
    case 'available':
      router.push(`/learning/topic/${item.topic.id}?action=practice`)
      break
    case 'review':
      router.push(`/learning/topic/${item.topic.id}?action=review`)
      break
    case 'locked':
      prereqTopic.value = item
      break
  }
}

// ── Bridge navigation (U4) ──

function onBridgeTap(bridge: BridgeResponse) {
  scrollTargetDomain.value = bridge.to_cluster_domain
  emit('switchSubject', bridge.to_subject)
}

// ── Prerequisite navigation ──

function onPrereqGoTo(topicId: string) {
  prereqTopic.value = null
  router.push(`/learning/topic/${topicId}`)
}

// ── Domain label helper ──

function domainLabel(domainKey: string): string {
  const domain = extractDomain(domainKey)
  if (domain === '__other__') return t('learning.cluster.otherDomain')
  const key = `learning.domains.${domain}`
  const translated = t(key)
  return translated === key ? domain : translated
}
</script>

<style scoped>
.cluster-map {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ── Progress bar ── */

.cluster-map__progress {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 2px;
}

.cluster-map__progress-bar {
  flex: 1;
  height: 6px;
  background: var(--color-hairline);
  border-radius: 3px;
  overflow: hidden;
}

.cluster-map__progress-fill {
  height: 100%;
  background: var(--color-brand-ochre);
  border-radius: 3px;
  transition: width 0.4s ease;
}

.cluster-map__progress-fill--complete {
  background: var(--color-brand-mint);
}

.cluster-map__progress-text {
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 600;
  color: var(--color-body);
  white-space: nowrap;
}

/* ── Celebration / frontier banner ── */

.cluster-map__celebration {
  text-align: center;
  padding: 12px 16px;
  background: rgba(var(--color-brand-mint-rgb), 0.15);
  border-radius: var(--radius-md);
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 500;
  color: var(--color-ink);
}

.cluster-map__frontier-banner {
  text-align: center;
  padding: 10px 16px;
  background: rgba(var(--color-brand-ochre-rgb), 0.12);
  border-radius: var(--radius-md);
  font-family: Inter, sans-serif;
  font-size: 13px;
  color: var(--color-body);
}

/* ── Domain groups ── */

.cluster-map__domains {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.cluster-map__territories {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
</style>
