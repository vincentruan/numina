import { computed, type ComputedRef } from 'vue'

/**
 * Minimal structural types shared between child and parent apps.
 * Each app's concrete interfaces extend these with extra fields.
 */

interface TopicLike {
  id: string
  subject: string
  domain: string | null
  age_group: string
}

interface ProgressLike {
  topic: TopicLike
  mastery_level: string
  next_review_at: string | null
}

interface ClusterLike {
  id: string
  subject: string
  domain: string
  age_range_start: number | null
  summary: string
}

interface BridgeLike {
  from_cluster_domain: string
  to_subject: string
  to_cluster_domain: string
  source_type: string
}

export interface ClusterTerritory<
  TItem extends ProgressLike = ProgressLike,
  TBridge extends BridgeLike = BridgeLike,
> {
  domain: string
  summary: string
  items: TItem[]
  masteredCount: number
  bridges: TBridge[]
}

/** Age-group sort order — consistent across both apps' territory views. */
const AGE_GROUP_ORDER = ['low', 'mid', 'high']

function ageGroupIndex(ag: string | null | undefined): number {
  const idx = AGE_GROUP_ORDER.indexOf(ag ?? '')
  return idx === -1 ? AGE_GROUP_ORDER.length : idx
}

/**
 * Build a single territory from a domain's items, its representative cluster,
 * and matching bridges.
 *
 * Exported so the child app can apply its own "no clusters for subject"
 * fallback (synthetic representative) before constructing territories.
 */
export function buildTerritory<
  TItem extends ProgressLike,
  TBridge extends BridgeLike,
>(
  domain: string,
  domainItems: TItem[],
  cluster: ClusterLike | undefined,
  allBridges: readonly TBridge[],
): ClusterTerritory<TItem, TBridge> {
  const sorted = [...domainItems].sort(
    (a, b) => ageGroupIndex(a.topic.age_group) - ageGroupIndex(b.topic.age_group),
  )
  return {
    domain,
    summary: cluster?.summary ?? '',
    items: sorted,
    masteredCount: sorted.filter((i) => i.mastery_level === 'mastered').length,
    bridges: allBridges.filter((b) => b.from_cluster_domain === domain),
  }
}

/**
 * Compute cluster territories — domain-grouped items matched against cluster
 * definitions with bridge associations.
 *
 * Shared between the child's ClusterMap and the parent's ParentClusterMap so
 * the domain-matching, representative-selection, age-sorting, and "other"
 * bucket logic stay consistent across both views.
 */
export function useClusterTerritories<
  TItem extends ProgressLike,
  TCluster extends ClusterLike,
  TBridge extends BridgeLike,
>(
  items: ComputedRef<TItem[]>,
  clusters: ComputedRef<TCluster[]>,
  bridges: ComputedRef<TBridge[]>,
  selectedSubject: ComputedRef<string>,
  loading: ComputedRef<boolean>,
) {
  const territories = computed<ClusterTerritory<TItem, TBridge>[]>(() => {
    const subjectItems = items.value.filter(
      (item) => item.topic.subject === selectedSubject.value,
    )
    if (subjectItems.length === 0) return []

    const hasClusters = clusters.value.some(
      (c) => c.subject === selectedSubject.value,
    )

    // Group items by domain
    const domainMap = new Map<string, TItem[]>()
    const unmatched: TItem[] = []

    for (const item of subjectItems) {
      const domain = item.topic.domain

      if (!hasClusters && !loading.value) {
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

    // Pick the earliest age_group representative per domain for summary text
    const representatives = new Map<string, TCluster>()
    for (const c of clusters.value) {
      if (!domainMap.has(c.domain)) continue
      const kept = representatives.get(c.domain)
      if (
        !kept ||
        (c.age_range_start !== null &&
          (kept.age_range_start === null || c.age_range_start < kept.age_range_start))
      ) {
        representatives.set(c.domain, c)
      }
    }

    const result: ClusterTerritory<TItem, TBridge>[] = [...domainMap.entries()].map(
      ([domain, domainItems]) =>
        buildTerritory<TItem, TBridge>(domain, domainItems, representatives.get(domain), bridges.value),
    )

    // "Other" bucket for unmatched items (skip while clusters still loading
    // to avoid a transient flash of everything in "其他")
    if (!loading.value && unmatched.length > 0) {
      result.push(
        buildTerritory<TItem, TBridge>('__other__', unmatched, undefined, bridges.value),
      )
    }

    return result
  })

  return { territories }
}
