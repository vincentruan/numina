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
      v-if="territories.length === 0 && !loading"
      :illustration="noRecordsSvg"
      :text="t('learning.cluster.empty')"
    />

    <!-- Territory list -->
    <div v-else class="cluster-map__territories">
      <ClusterTerritory
        v-for="territory in territories"
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

import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type {
  ProgressWithTopic,
  ClusterResponse,
  BridgeResponse,
} from '@/api/learning'
import { getClusters, getBridges } from '@/api/learning'
import ClusterTerritory from './ClusterTerritory.vue'
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

// Cards span every age_group of a domain, so their nodes are ordered by
// difficulty rather than by the order the API happened to return rows in.
const AGE_GROUP_ORDER = ['low', 'mid', 'high']

const territories = computed<Territory[]>(() => {
  const subjectItems = props.items.filter(
    (item) => item.topic.subject === props.selectedSubject,
  )

  // One card per domain, not per cluster row. ``clusters.json`` stores several
  // rows per domain (one per age_group), so keying the map on ``cluster.id``
  // rendered the same domain as several separate cards.
  const domainMap = new Map<string, ProgressWithTopic[]>()
  const unmatched: ProgressWithTopic[] = []

  for (const item of subjectItems) {
    // Only the domain decides which territory a topic belongs to. A domain the
    // taxonomy has no cluster for must not be attributed to an unrelated
    // domain of the same subject — it goes to "其他" instead.
    //
    // A null domain carries no signal at all, so it falls back to the first
    // cluster of the same subject: arbitrary, but better than hiding the node
    // in "其他" where the child would never see it.
    const domain = item.topic.domain
    const target =
      domain !== null && clusters.value.some((c) => c.domain === domain)
        ? domain
        : domain === null
          ? clusters.value.find((c) => c.subject === item.topic.subject)?.domain
          : undefined
    if (target === undefined) {
      unmatched.push(item)
      continue
    }
    if (!domainMap.has(target)) domainMap.set(target, [])
    domainMap.get(target)!.push(item)
  }

  // Only render territories that actually hold nodes. ``topic_count`` is the
  // taxonomy's count for the (subject, domain, age_group) key, not this
  // child's — trusting it would render empty cards wherever the API's row set
  // and the progress rows disagree.
  //
  // One representative row per domain supplies the card's summary/age range;
  // the cards themselves come from the child's own progress, never from the
  // taxonomy's row set.
  const representatives = new Map<string, ClusterResponse>()
  for (const c of clusters.value) {
    if (!domainMap.has(c.domain)) continue
    const kept = representatives.get(c.domain)
    if (!kept || (c.age_range_start !== null && (kept.age_range_start === null || c.age_range_start < kept.age_range_start))) {
      representatives.set(c.domain, c)
    }
  }

  // A domain reaches this map only if a cluster carries it, so every entry is
  // backed by a representative row.
  const result: Territory[] = [...domainMap.entries()].flatMap(([domain, items]) => {
    const cluster = representatives.get(domain)
    if (!cluster) return []
    return [{
      cluster,
      items: [...items].sort(
        (a, b) => AGE_GROUP_ORDER.indexOf(a.topic.age_group) - AGE_GROUP_ORDER.indexOf(b.topic.age_group),
      ),
      bridges: bridges.value.filter((b) => b.from_cluster_domain === domain),
    }]
  })

  // Append "Other" territory for unmatched items
  if (unmatched.length > 0) {
    if (import.meta.env.DEV) {
      console.warn(
        `[ClusterMap] ${unmatched.length} topic(s) unmatched — no cluster found:`,
        unmatched.map((i) => ({
          topic_id: i.topic.id,
          subject: i.topic.subject,
          domain: i.topic.domain,
          age_group: i.topic.age_group,
        })),
      )
    }
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
})

// ── Progress (U5) ──

const subjectItems = computed(() =>
  props.items.filter((item) => item.topic.subject === props.selectedSubject),
)

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
  // Priority: learning > available > review
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
  // Cards are keyed by domain, so the frontier only matters when a card for
  // this domain actually renders.
  const match = clusters.value.find(
    (c) => c.subject === ft.subject && c.domain === ft.domain,
  )
  return match?.domain ?? null
})

// ── Auto-scroll to frontier on load, or to bridge target ──

// The frontier scroll is one-shot (it brings the child to their place on
// first view); a bridge tap must work on *every* subject switch, because
// the target territory only exists in the DOM after the new clusters and
// topics resolve. Tracking the two modes separately is what the previous
// `{ once: … }` could not express — it disabled the bridge scroll too
// whenever the child had a frontier.
let frontierScrolled = false

// flush: 'post' — the territory this scrolls to only exists once the
// component has re-rendered with the new subject's clusters/topics.
watch(territories, async () => {
  const bridgeTarget = scrollTargetDomain.value
  const targetDomain =
    bridgeTarget || (frontierScrolled ? null : frontierClusterDomain.value)
  if (!targetDomain) return

  const el = document.querySelector(
    `[data-cluster-domain="${CSS.escape(targetDomain)}"]`,
  )
  // The target territory may still be pending: a subject switch re-renders
  // territories from the props change first, and only later from the
  // clusters/topics fetch. Keep the target armed until the node is really
  // there, so the scroll fires on a later recomputation instead of being
  // silently dropped.
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
  // Switch to target subject tab
  emit('switchSubject', bridge.to_subject)
}

// ── Prerequisite navigation ──

function onPrereqGoTo(topicId: string) {
  prereqTopic.value = null
  router.push(`/learning/topic/${topicId}`)
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

/* ── Territory list ── */

.cluster-map__territories {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
</style>
