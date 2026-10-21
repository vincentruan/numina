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

    <!-- Collapsible domain sections (#133). One section per territory: the
         territory list is already deduplicated per domain (#142). -->
    <div v-else class="cluster-map__domains">
      <DomainSection
        v-for="territory in territories"
        :key="domainKey(territory)"
        :domain="territory.cluster.domain"
        :domain-label="translateDomain(t, territory.cluster.domain)"
        :mastered-count="masteredIn(territory)"
        :total-count="territory.items.length"
        :expanded="isExpanded(territory)"
        :instant="isInstant(territory)"
        @toggle="toggleDomain(territory)"
      >
        <div class="cluster-map__territories">
          <ClusterTerritory
            :cluster="territory.cluster"
            :items="territory.items"
            :bridges="territory.bridges"
            :is-frontier-cluster="frontierClusterDomain === territory.cluster.domain"
            :frontier-topic-id="frontierTopic?.topic.id ?? null"
            hide-title
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
import { domainLabel as translateDomain } from '@/utils/domainLabel'
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

  // When no clusters exist for the selected subject (e.g. Beijing-only
  // subjects like art/biology whose clusters were seeded under os-taxonomy
  // keys), fall back to grouping items directly by domain so they still
  // render as meaningful cards instead of all collapsing into "其他".
  const hasClustersForSubject = clusters.value.some(
    (c) => c.subject === props.selectedSubject,
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

    if (!hasClustersForSubject && !loading.value) {
      // No clusters for this subject and not mid-load — group by domain
      // directly so Beijing-only subjects still render meaningful cards
      // instead of collapsing everything into "其他".
      const target = domain || '__other__'
      if (!domainMap.has(target)) domainMap.set(target, [])
      domainMap.get(target)!.push(item)
      continue
    }

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
  // backed by a representative row. When no clusters exist for the subject
  // (Beijing-only subjects with os-taxonomy seed clusters), synthesize a
  // minimal representative so the domain card still renders.
  const result: Territory[] = [...domainMap.entries()].flatMap(([domain, items]) => {
    let cluster = representatives.get(domain)
    if (!cluster && !hasClustersForSubject && !loading.value) {
      cluster = {
        id: `synthetic:${props.selectedSubject}:${domain}`,
        subject: props.selectedSubject,
        domain,
        age_range_start: null,
        age_group: '',
        summary: '',
        topic_count: items.length,
      } as ClusterResponse
    }
    if (!cluster) return []
    return [{
      cluster,
      items: [...items].sort(
        (a, b) => AGE_GROUP_ORDER.indexOf(a.topic.age_group) - AGE_GROUP_ORDER.indexOf(b.topic.age_group),
      ),
      bridges: bridges.value.filter((b) => b.from_cluster_domain === domain),
    }]
  })

  // Append "Other" territory for unmatched items. Skip this when clusters
  // are still loading — during a subject switch the old clusters were just
  // cleared, so every item is temporarily unmatched and would flash into a
  // transient "其他" section. Once the new clusters land, the unmatched set
  // settles correctly. After a failed load, clusters is empty and loading is
  // false, and the bucket still applies — it's the legitimate fallback for
  // items whose domain has no cluster row at all.
  if (!loading.value && unmatched.length > 0) {
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

/** Composite key `{subject}:{domain}` (KTD6) — survives subject switches
 *  without colliding on domain names shared between subjects. */
function domainKey(territory: Territory): string {
  return `${props.selectedSubject}:${territory.cluster.domain}`
}

function masteredIn(territory: Territory): number {
  return territory.items.filter((i) => i.mastery_level === 'mastered').length
}

// ── Progress (U5) ──

const subjectItems = computed(() =>
  props.items.filter((item) => item.topic.subject === props.selectedSubject),
)

// ── Collapse defaults (KTD3) ──

/** A domain opens by default when it holds active learning — anything the
 *  child is working on now, or has mastered but is due to review. Locked and
 *  not-yet-due mastered topics stay hidden. */
function defaultExpanded(territory: Territory): boolean {
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
function isExpanded(territory: Territory): boolean {
  return userExpanded.get(domainKey(territory)) ?? defaultExpanded(territory)
}

function toggleDomain(territory: Territory) {
  userExpanded.set(domainKey(territory), !isExpanded(territory))
}

/** True while a programmatic expand (frontier/bridge) has the section open
 *  without its height transition — see the scroll watcher below. */
function isInstant(territory: Territory): boolean {
  return instantExpandKeys.has(domainKey(territory))
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
  const target = territories.value.find((t) => t.cluster.domain === targetDomain)
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
