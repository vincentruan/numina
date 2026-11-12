/**
 * Map exploration instrumentation (R11, R12).
 *
 * One instance tracks one map visit: elapsed time between map mount and the
 * child's first topic selection (R11), the deepest zoom level reached (R12),
 * and the count of pan/zoom/tap interactions so exploration depth is
 * separable from dwell time. A visit that ends without a selection is still
 * recorded when flushed (AE4).
 */

import { readonly, ref, type Ref } from 'vue'
import { recordMapExploration } from '@/api/learning'

export interface MapExplorationApi {
  /** Timestamp the current visit started (ms epoch). */
  readonly startedAt: Readonly<Ref<number | null>>
  /** Record a pan/tap interaction (not zoom — see recordZoom). */
  recordInteraction: () => void
  /** Record the zoom level the child moved to (0 subject, 1 domain, 2 topic). */
  recordZoom: (level: number) => void
  /**
   * Record the first topic selection and POST immediately. Subsequent
   * selections are ignored — R11 measures time to *first* selection.
   */
  recordTopicSelection: (topicId: string) => void
  /** POST the visit summary if not already recorded (call on map leave). */
  flush: () => void
  /** Re-arm for a new visit (resets timer and counters). */
  start: () => void
}

export function useMapExploration(): MapExplorationApi {
  const startedAt = ref<number | null>(null)
  const maxZoomLevel = ref<0 | 1 | 2>(0)
  const interactionCount = ref(0)
  const recorded = ref(false)

  function start() {
    startedAt.value = Date.now()
    maxZoomLevel.value = 0
    interactionCount.value = 0
    recorded.value = false
  }

  function post() {
    recorded.value = true
    const durationMs = startedAt.value === null ? 0 : Math.max(0, Date.now() - startedAt.value)
    // Fire-and-forget: telemetry must never surface as an error to the child.
    void recordMapExploration({
      duration_ms: durationMs,
      max_zoom_level: maxZoomLevel.value,
      topic_selected: false,
      interaction_count: interactionCount.value,
    }).catch(() => {
      // Swallow — leaving the map must not be blocked by a failed beacon.
    })
  }

  function postSelection(topicId: string) {
    if (recorded.value) return
    const durationMs = startedAt.value === null ? 0 : Math.max(0, Date.now() - startedAt.value)
    recorded.value = true
    void recordMapExploration({
      duration_ms: durationMs,
      max_zoom_level: maxZoomLevel.value,
      topic_selected: true,
      interaction_count: interactionCount.value + 1, // the selection counts as an interaction
      selected_topic_id: topicId,
    }).catch(() => {})
  }

  const api: MapExplorationApi = {
    startedAt: readonly(startedAt),
    recordInteraction: () => {
      interactionCount.value++
    },
    recordZoom: (level: number) => {
      const lv = Math.max(0, Math.min(2, Math.floor(level))) as 0 | 1 | 2
      if (lv > maxZoomLevel.value) maxZoomLevel.value = lv
    },
    recordTopicSelection: postSelection,
    flush: () => {
      if (recorded.value) return
      post()
    },
    start,
  }

  start()
  return api
}
