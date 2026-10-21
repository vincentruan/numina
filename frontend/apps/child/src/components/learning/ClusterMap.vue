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

const territories = computed<Territory[]>(() => {
  const subjectItems = props.items.filter(
    (item) => item.topic.subject === props.selectedSubject,
  )

  // Match items to clusters by subject + domain + age_group
  const clusterMap = new Map<string, ProgressWithTopic[]>()
  const unmatched: ProgressWithTopic[] = []

  for (const item of subjectItems) {
    // Prefer the exact 3-key match; the API now returns one row per key, but
    // a key it never had (e.g. a topic whose age_group is missing from
    // clusters.json) should still land in its domain territory rather than be
    // dropped into "其他".
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
      ) ??
      // Tier 3: subject-only — catches topics with null domain or a domain
      // that has no cluster at all. Better to group them under a same-subject
      // cluster than to dump them into "其他".
      clusters.value.find(
        (c) => c.subject === item.topic.subject,
      )
    if (matchingCluster) {
      if (!clusterMap.has(matchingCluster.id)) clusterMap.set(matchingCluster.id, [])
      clusterMap.get(matchingCluster.id)!.push(item)
    } else {
      unmatched.push(item)
    }
  }

  // Only render territories that actually hold nodes. ``topic_count`` is the
  // taxonomy's count for the (subject, domain, age_group) key, not this
  // child's — trusting it would render empty cards wherever the API's row set
  // and the progress rows disagree.
  const result: Territory[] = clusters.value
    .filter((c) => clusterMap.has(c.id))
    .map((c) => ({
      cluster: c,
      items: clusterMap.get(c.id)!,
      bridges: bridges.value.filter((b) => b.from_cluster_domain === c.domain),
    }))

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
  const match = clusters.value.find(
    (c) => c.subject === ft.subject && c.domain === (ft.domain ?? '') && c.age_group === ft.age_group,
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
