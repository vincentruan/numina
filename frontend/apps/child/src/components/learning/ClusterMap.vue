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

    <!-- Next-up CTA card (replaces frontier banner) -->
    <NextUpCard
      v-if="masteredCount < totalCount"
      :topic="nextTopic"
      :topic-name="nextTopic ? topicDisplayName(nextTopic.topic) : ''"
      :loading="isLoading"
    />

    <!-- Empty state -->
    <EmptyState
      v-if="territories.length === 0 && !loading"
      :illustration="noRecordsSvg"
      :text="t('learning.cluster.empty')"
    />

    <!-- Collapsible domain sections (#133). One section per territory: the
         territory list is already deduplicated per domain (#142). -->
    <div v-else class="cluster-map__domains">
      <DomainSection
        v-for="territory in territories"
        :key="domainKey(territory)"
        :domain="territory.domain"
        :domain-label="translateDomain(t, territory.domain)"
        :mastered-count="territory.masteredCount"
        :total-count="territory.items.length"
        :expanded="isExpanded(territory)"
        :instant="isInstant(territory)"
        :path-count="pathCountByDomain.get(territory.domain) ?? 0"
        @toggle="toggleDomain(territory)"
      >
        <div class="cluster-map__territories">
          <ClusterTerritory
            :cluster="{ domain: territory.domain, summary: territory.summary } as ClusterResponse"
            :items="territory.items"
            :bridges="territory.bridges"
            :is-frontier-cluster="frontierClusterDomain === territory.domain"
            :frontier-topic-id="frontierTopic?.topic.id ?? null"
            hide-title
            @topic-tap="onTopicTap"
            @bridge-tap="onBridgeTap"
          />
        </div>
      </DomainSection>
    </div>

    <!-- SVG path overlay for recommendation path -->
    <PathOverlay
      :path-topic-ids="subjectPathTopicIds"
      :all-items="props.items"
      :expanded-domains="expandedDomainSet"
    />

    <!-- Prerequisite guidance bottom sheet (U3) -->
    <PrerequisiteGuidance
      v-if="prereqTopic"
      :topic="prereqTopic"
      :all-items="props.items"
      @close="prereqTopic = null"
      @go-to="onPrereqGoTo"
    />

    <!-- Recommendation reason popup — shows why a path topic is recommended -->
    <van-popup
      v-model:show="showReasonPopup"
      position="bottom"
      round
      :style="{ padding: '16px', maxWidth: '400px', margin: '0 auto' }"
    >
      <div v-if="reasonPopupTopic" class="path-reason-popup">
        <div class="path-reason-popup__header">
          <span class="path-reason-popup__title">{{ t('learning.recommendPath.whyRecommended') }}</span>
          <button class="path-reason-popup__close" @click="closeReasonPopup">✕</button>
        </div>
        <p class="path-reason-popup__topic">{{ topicDisplayName(reasonPopupTopic.topic) }}</p>
        <ul class="path-reason-popup__reasons">
          <li
            v-for="reason in reasonPopupReasons"
            :key="reason"
            class="path-reason-popup__reason"
          >{{ reason }}</li>
        </ul>
        <button class="path-reason-popup__action" @click="onReasonPopupAction">
          {{ t('learning.recommendPath.startPracticeBtn') }}
        </button>
      </div>
    </van-popup>
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
import NextUpCard from './NextUpCard.vue'
import PathOverlay from './PathOverlay.vue'
import { domainLabel as translateDomain } from '@/utils/domainLabel'
import EmptyState from '@/components/EmptyState.vue'
import { noRecordsSvg } from '@numina/assets/empty-states'
import { useClusterTerritories } from '@/composables/useClusterTerritories'

const { t, locale } = useI18n()
const router = useRouter()

const props = defineProps<{
  items: ProgressWithTopic[]
  selectedSubject: string
  pathTopicIds: string[]
  /** topic_id → reasons[] from the recommendation engine */
  pathReasons?: Record<string, string[]>
  nextTopic: ProgressWithTopic | null
  isLoading: boolean
}>()

const emit = defineEmits<{
  switchSubject: [subject: string]
}>()

const loading = ref(false)
const clusters = ref<ClusterResponse[]>([])
const bridges = ref<BridgeResponse[]>([])
const prereqTopic = ref<ProgressWithTopic | null>(null)
const scrollTargetDomain = ref<string | null>(null)

// ── Recommendation reason popup ──
const showReasonPopup = ref(false)
const reasonPopupTopic = ref<ProgressWithTopic | null>(null)
/** Pending navigation target — resolved after the user dismisses the popup */
let pendingRouteAfterReason: string | null = null

/** Translate backend reason strings ("知识断点" etc.) to i18n labels */
const REASON_I18N_MAP: Record<string, string> = {
  '知识断点': 'learning.recommendPath.reasonBreakpoint',
  '课标必会': 'learning.recommendPath.reasonCurriculumGap',
  '需要复习': 'learning.recommendPath.reasonReviewDue',
}
const reasonPopupReasons = computed(() => {
  if (!reasonPopupTopic.value) return []
  const reasons = props.pathReasons?.[reasonPopupTopic.value.topic.id] ?? []
  return reasons.map((r) => t(REASON_I18N_MAP[r] ?? r))
})

// ── Collapse state (KTD6) ──

/** Explicit user toggles, keyed by `{subject}:{domain}`. Written *only* by
 *  `toggleDomain`, so a manual collapse can never be overwritten by the
 *  auto-expand defaults (R5). Domains absent from this map fall back to the
 *  computed default, which keeps the first render correct instead of
 *  collapsing everything and animating it open on the next flush. */
const userExpanded = reactive(new Map<string, boolean>())

// ── Data loading ──

async function load() {
  loading.value = true
  // Clear stale clusters from the previous subject before the new data lands.
  // Without this, `territories` briefly mixes new items against old clusters
  // during the subject switch, and everything unmatched lands in the "其他"
  // bucket — a visible flash the child sees for a split second.
  clusters.value = []
  bridges.value = []
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

// ── Topic-to-cluster matching (shared composable) ──

const subjectItemsRef = computed(() =>
  props.items.filter((item) => item.topic.subject === props.selectedSubject),
)

const { territories } = useClusterTerritories(
  subjectItemsRef,
  computed(() => clusters.value),
  computed(() => bridges.value),
  computed(() => props.selectedSubject),
  computed(() => loading.value),
)

/** Composite key `{subject}:{domain}` (KTD6) — survives subject switches
 *  without colliding on domain names shared between subjects. */
function domainKey(territory: { domain: string }): string {
  return `${props.selectedSubject}:${territory.domain}`
}

// ── Progress (U5) ──

// subjectItemsRef (defined above) provides the same data as the old
// subjectItems computed — reuse it for progress calculations below.
const subjectItems = subjectItemsRef

// ── Collapse defaults (KTD3) ──

/** A domain opens by default when it holds active learning — anything the
 *  child is working on now, or has mastered but is due to review. Locked and
 *  not-yet-due mastered topics stay hidden. */
function defaultExpanded(territory: { domain: string; items: ProgressWithTopic[] }): boolean {
  return territory.items.some((i) => {
    const level = i.mastery_level
    if (level === 'learning' || level === 'assessing' || level === 'available') return true
    if (level === 'mastered' && i.next_review_at && new Date(i.next_review_at) <= new Date()) return true
    return false
  })
}

/** Derived, not seeded: a user toggle always wins, otherwise the default is
 *  recomputed from current data. Deriving it means the first paint already has
 *  the final expanded state (no collapse-then-animate-open flash) and no
 *  watcher can reset a manual choice. */
function isExpanded(territory: { domain: string; items: ProgressWithTopic[] }): boolean {
  return userExpanded.get(domainKey(territory)) ?? defaultExpanded(territory)
}

function toggleDomain(territory: { domain: string; items: ProgressWithTopic[] }) {
  userExpanded.set(domainKey(territory), !isExpanded(territory))
}

/** True while a programmatic expand (frontier/bridge) has the section open
 *  without its height transition — see the scroll watcher below. */
function isInstant(territory: { domain: string }): boolean {
  return instantExpandKeys.has(domainKey(territory))
}

// ── Recommendation path data ──

/** Topic IDs from the recommendation path filtered to the current subject. */
const subjectPathTopicIds = computed(() => {
  const subjectItemIds = new Set(
    props.items
      .filter((i) => i.topic.subject === props.selectedSubject)
      .map((i) => i.topic.id),
  )
  return props.pathTopicIds.filter((id) => subjectItemIds.has(id))
})

/** Set of currently expanded domain names (not composite keys) for PathOverlay. */
const expandedDomainSet = computed(() => {
  const expanded = new Set<string>()
  for (const territory of territories.value) {
    if (isExpanded(territory)) {
      expanded.add(territory.domain)
    }
  }
  return expanded
})

/** Count of path topics per collapsed domain — for DomainSection badges. */
const pathCountByDomain = computed(() => {
  const counts = new Map<string, number>()
  const subjectPathIds = new Set(subjectPathTopicIds.value)
  for (const territory of territories.value) {
    if (isExpanded(territory)) continue
    const count = territory.items.filter((i) => subjectPathIds.has(i.topic.id)).length
    if (count > 0) {
      counts.set(territory.domain, count)
    }
  }
  return counts
})

/** Localized topic display name for NextUpCard. */
function topicDisplayName(topic: ProgressWithTopic['topic']): string {
  if (locale.value.startsWith('zh') && topic.name_zh) return topic.name_zh
  return topic.name || topic.topic_key
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

/** Domains that were expanded programmatically rather than by the child.
 *  Their height transition is suppressed for the scroll so `scrollIntoView`
 *  resolves its target against final geometry, not a 44px collapsing row. */
const instantExpandKeys = reactive(new Set<string>())

/** Bumped per scroll attempt so an in-flight one can tell it was superseded. */
let scrollSeq = 0

/** Scroll to the section for `targetDomain`, preferring the territory card
 *  the child actually navigated to over the section header. Returns false
 *  when the node is not mounted yet. */
function scrollToDomain(targetDomain: string): boolean {
  const section = document.querySelector(
    `.domain-section[data-domain="${CSS.escape(targetDomain)}"]`,
  )
  if (!section) return false

  const anchor =
    section.querySelector(`[data-cluster-domain="${CSS.escape(targetDomain)}"]`) ??
    section
  anchor.scrollIntoView({ behavior: 'smooth', block: 'center' })
  return true
}

// flush: 'post' — the section this scrolls to only exists once the component
// has re-rendered with the new subject's clusters/topics.
watch(territories, async () => {
  const bridgeTarget = scrollTargetDomain.value
  const targetDomain =
    bridgeTarget || (frontierScrolled ? null : frontierClusterDomain.value)
  if (!targetDomain) return

  const seq = ++scrollSeq
  const target = territories.value.find((ter) => ter.domain === targetDomain)
  const targetKey = target ? domainKey(target) : null

  // Auto-expand a collapsed target before scrolling (R6). The `instant` flag
  // suppresses the height transition, so one nextTick is enough for the
  // section to reach final geometry — no animating row to measure against.
  if (target && targetKey && !isExpanded(target)) {
    userExpanded.set(targetKey, true)
    instantExpandKeys.add(targetKey)
    await nextTick()
    if (seq !== scrollSeq) return
  }

  // Keep the target armed when the node is not mounted yet: a subject switch
  // re-renders from the props change first and only later from the fetch.
  if (!scrollToDomain(targetDomain)) return

  if (targetKey) instantExpandKeys.delete(targetKey)
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
  const isPathTopic = props.pathTopicIds.includes(item.topic.id)
  const hasReasons = isPathTopic && props.pathReasons?.[item.topic.id]?.length

  // Path topic with reasons → show "why recommended" popup first
  if (hasReasons) {
    reasonPopupTopic.value = item
    showReasonPopup.value = true
    // Stage the navigation target for when the user acts on the popup
    switch (status) {
      case 'mastered':
        pendingRouteAfterReason = `/learning/topic/${item.topic.id}`
        break
      case 'learning':
      case 'available':
        pendingRouteAfterReason = `/learning/topic/${item.topic.id}?action=practice`
        break
      case 'review':
        pendingRouteAfterReason = `/learning/topic/${item.topic.id}?action=review`
        break
      default:
        pendingRouteAfterReason = null
    }
    return
  }

  navigateForStatus(item, status)
}

function navigateForStatus(item: ProgressWithTopic, status: string) {
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

function closeReasonPopup() {
  showReasonPopup.value = false
  reasonPopupTopic.value = null
  pendingRouteAfterReason = null
}

function onReasonPopupAction() {
  const route = pendingRouteAfterReason
  closeReasonPopup()
  if (route) router.push(route)
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
  position: relative;
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

/* ── Celebration ── */

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

/* ── Recommendation reason popup ── */

.path-reason-popup__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.path-reason-popup__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-body);
}

.path-reason-popup__close {
  background: none;
  border: none;
  font-size: 18px;
  color: var(--color-body);
  padding: 4px 8px;
  cursor: pointer;
}

.path-reason-popup__topic {
  font-size: 17px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 10px;
}

.path-reason-popup__reasons {
  list-style: none;
  padding: 0;
  margin: 0 0 16px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.path-reason-popup__reason {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  background: var(--color-brand-primary-light, rgba(59, 130, 246, 0.12));
  color: var(--color-brand-primary, #3b82f6);
}

.path-reason-popup__action {
  width: 100%;
  padding: 12px;
  border: none;
  border-radius: 10px;
  background: var(--color-primary);
  color: var(--color-canvas);
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.path-reason-popup__action:active {
  opacity: 0.85;
}
</style>
