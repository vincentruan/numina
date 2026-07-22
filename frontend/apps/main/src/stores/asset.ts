import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Asset, AssetFilter, AssetMoneyField, AssetRequestPayload, AssetSellRequest, AssetSellResponse } from '@/types'
import { ASSET_MONEY_FIELDS } from '@/types'
import * as assetApi from '@/api/assets'
import { useDashboardStore } from '@/stores/dashboard'
import { nanoid } from 'nanoid'

// Module-level syncing state tracker — tracks assets currently syncing with server
// (Plain Set, not a ref — Pinia warns on non-serializable state)
const _syncingIds: Set<string> = new Set()

// Module-level pending operations tracker for request deduplication
// Separate maps for different return types
const _pendingCreateOperations: Map<string, Promise<Asset>> = new Map()
const _pendingUpdateOperations: Map<string, Promise<Asset>> = new Map()
const _pendingDeleteOperations: Map<string, Promise<void>> = new Map()

// Operation timeout (30s) - prevents memory leak from stuck promises
const OPERATION_TIMEOUT_MS = 30_000

function isSyncing(id: string): boolean {
  return _syncingIds.has(id)
}

function generateTempId(): string {
  return `temp-${nanoid(8)}`
}

// Helper for tests to reset module-level state
export function _resetPendingOperations(): void {
  _pendingCreateOperations.clear()
  _pendingUpdateOperations.clear()
  _pendingDeleteOperations.clear()
  _syncingIds.clear()
}

export const useAssetStore = defineStore('asset', () => {
  const assets = ref<Asset[]>([])
  const currentAsset = ref<Asset | null>(null)
  const loading = ref(false)

  async function fetchAssets(filters?: AssetFilter) {
    loading.value = true
    try {
      const res = await assetApi.getAssets(filters)
      const raw = res.data as unknown as { items?: Asset[] } | Asset[]
      assets.value = Array.isArray(raw) ? raw : ((raw as { items?: Asset[] }).items ?? [])
    } finally {
      loading.value = false
    }
  }

  async function fetchAsset(id: string) {
    loading.value = true
    try {
      const res = await assetApi.getAsset(id)
      currentAsset.value = res.data
    } finally {
      loading.value = false
    }
  }

  function createAsset(data: AssetRequestPayload): Promise<Asset> {
    // 1. Generate dedup key from input data (for create operations)
    // Use serialized form data as key to dedupe rapid double-clicks
    const dedupKey = `create:${JSON.stringify({
      name: data.name,
      category_id: data.category_id,
      asset_type: data.asset_type,
      purchase_price: data.purchase_price,
      current_value: data.current_value,
    })}`

    // 2. Check for existing pending operation (dedup) - return immediately if found
    const existingOp = _pendingCreateOperations.get(dedupKey)
    if (existingOp) {
      return existingOp
    }

    // 3. Generate temp ID for the optimistic asset
    const tempId = generateTempId()

    // 4. Build temp asset object with form data + tempId + placeholder fields
    // Use undefined instead of null to match Asset type
    const tempAsset: Asset = {
      id: tempId,
      name: data.name || '',
      category_id: data.category_id || '',
      asset_type: data.asset_type || 'physical',
      purchase_price: data.purchase_price != null ? String(data.purchase_price) : '0',
      current_value: data.current_value != null ? String(data.current_value) : '0',
      currency: data.currency || 'CNY',
      purchase_date: data.purchase_date || '',
      status: 'in_use',
      location: data.location,
      institution: data.institution,
      interest_rate: data.interest_rate,
      maturity_date: data.maturity_date,
      expected_lifespan_days: data.expected_lifespan_days,
      annual_maintenance_cost: data.annual_maintenance_cost != null ? String(data.annual_maintenance_cost) : undefined,
      usage_frequency: data.usage_frequency,
      properties: data.properties,
      notes: data.notes,
      target_daily_cost: data.target_daily_cost != null ? String(data.target_daily_cost) : undefined,
      image_url: data.image_url,
      tags: data.tags || [],
      // Placeholder fields (server-only)
      user_id: '',
      family_id: '',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    }

    // 5. Insert at top of assets list and mark as syncing
    assets.value.unshift(tempAsset)
    _syncingIds.add(tempId)

    // 6. Create the operation Promise - IMPORTANT: set in map immediately before async work
    let resolvePromise: (value: Asset) => void
    let rejectPromise: (reason: unknown) => void
    const operationPromise = new Promise<Asset>((resolve, reject) => {
      resolvePromise = resolve
      rejectPromise = reject
    })

    // Store pending operation BEFORE starting async work (critical for dedup)
    _pendingCreateOperations.set(dedupKey, operationPromise)

    // Timeout handler to prevent memory leak
    const timeoutId = setTimeout(() => {
      if (_pendingCreateOperations.has(dedupKey)) {
        console.warn('[createAsset] Timeout - cleaning up stuck operation', tempId)
        _pendingCreateOperations.delete(dedupKey)
        _syncingIds.delete(tempId)
        // Remove temp asset on timeout
        const timeoutIdx = assets.value.findIndex(a => a.id === tempId)
        if (timeoutIdx !== -1) {
          assets.value.splice(timeoutIdx, 1)
        }
        if (currentAsset.value?.id === tempId) {
          currentAsset.value = null
        }
        rejectPromise!(new Error('Operation timed out'))
      }
    }, OPERATION_TIMEOUT_MS)

    // Start async work in background
    ;(async () => {
      try {
        const res = await assetApi.createAsset(data)
        clearTimeout(timeoutId)
        const serverAsset = res.data

        // On success: find by tempId, replace with server response
        const idx = assets.value.findIndex(a => a.id === tempId)
        if (idx !== -1) {
          assets.value[idx] = serverAsset
        }

        // Update currentAsset if it was set to the temp asset
        if (currentAsset.value?.id === tempId) {
          currentAsset.value = serverAsset
        }

        _syncingIds.delete(tempId)
        _pendingCreateOperations.delete(dedupKey)
        useDashboardStore().invalidateDashboard()
        resolvePromise!(serverAsset)
      } catch (error) {
        clearTimeout(timeoutId)
        // On error: rollback by removing temp asset
        console.warn('[createAsset] Rollback - removing temp asset', tempId)
        const idx = assets.value.findIndex(a => a.id === tempId)
        if (idx !== -1) {
          assets.value.splice(idx, 1)
        }
        if (currentAsset.value?.id === tempId) {
          currentAsset.value = null
        }
        _syncingIds.delete(tempId)
        _pendingCreateOperations.delete(dedupKey)
        rejectPromise!(error)
      }
    })()

    return operationPromise
  }

  function updateAsset(id: string, data: AssetRequestPayload): Promise<Asset> {
    // 1. Check for existing pending operation (dedup)
    const dedupKey = `update:${id}`
    const existingOp = _pendingUpdateOperations.get(dedupKey)
    if (existingOp) {
      return existingOp
    }

    // 2. Find asset in list
    const idx = assets.value.findIndex(a => a.id === id)
    if (idx === -1) {
      // Asset not found, fall back to pessimistic API call
      return assetApi.updateAsset(id, data).then(res => res.data)
    }

    // 3. Snapshot original asset (deep copy for rollback)
    const originalAsset = JSON.parse(JSON.stringify(assets.value[idx])) as Asset

    // 4. Build updated asset (optimistic). `data` is a request payload: its money
    // fields are numbers and it carries tag_ids, neither of which belongs on the
    // Asset wire shape (money-as-str). Spread only the scalar (non-money, non-tag)
    // fields, then set each money field from ASSET_MONEY_FIELDS: present (≠ undefined)
    // → coerce back to str; omitted → keep the existing asset's value.
    const { tag_ids: _tagIds, ...rest } = data
    // Strip the number-typed money keys so the spread is Asset-shaped; the loop below
    // is the sole writer of money fields. The cast is a truthful narrowing: after the
    // deletes, only scalar (non-money) fields remain.
    const scalarData = { ...rest }
    for (const k of ASSET_MONEY_FIELDS) {
      delete scalarData[k]
    }
    const scalar = scalarData as Omit<Partial<Asset>, AssetMoneyField>
    const toStr = (v: number | null | undefined): string | null => (v != null ? String(v) : null)
    const updatedAsset: Asset = {
      ...assets.value[idx],
      ...scalar,
      updated_at: new Date().toISOString(),
    }
    for (const k of ASSET_MONEY_FIELDS) {
      const v = data[k]
      updatedAsset[k] = v !== undefined ? toStr(v) : (assets.value[idx][k] ?? null)
    }

    // 5. Apply optimistic update
    assets.value[idx] = updatedAsset
    if (currentAsset.value?.id === id) {
      currentAsset.value = updatedAsset
    }
    _syncingIds.add(id)

    // 6. Create operation Promise
    let resolvePromise: (value: Asset) => void
    let rejectPromise: (reason: unknown) => void
    const operationPromise = new Promise<Asset>((resolve, reject) => {
      resolvePromise = resolve
      rejectPromise = reject
    })

    // Store pending operation
    _pendingUpdateOperations.set(dedupKey, operationPromise)

    // Timeout handler to prevent memory leak
    const timeoutId = setTimeout(() => {
      if (_pendingUpdateOperations.has(dedupKey)) {
        console.warn('[updateAsset] Timeout - cleaning up stuck operation', id)
        _pendingUpdateOperations.delete(dedupKey)
        _syncingIds.delete(id)
        // Rollback to original on timeout
        const timeoutIdx = assets.value.findIndex(a => a.id === id)
        if (timeoutIdx !== -1) {
          assets.value[timeoutIdx] = originalAsset
        }
        if (currentAsset.value?.id === id) {
          currentAsset.value = originalAsset
        }
        rejectPromise!(new Error('Operation timed out'))
      }
    }, OPERATION_TIMEOUT_MS)

    // 7. Start async work
    ;(async () => {
      try {
        const res = await assetApi.updateAsset(id, data)
        clearTimeout(timeoutId)
        const serverAsset = res.data

        // On success: use server response
        const currentIdx = assets.value.findIndex(a => a.id === id)
        if (currentIdx !== -1) {
          assets.value[currentIdx] = serverAsset
        }
        if (currentAsset.value?.id === id) {
          currentAsset.value = serverAsset
        }

        _syncingIds.delete(id)
        _pendingUpdateOperations.delete(dedupKey)
        useDashboardStore().invalidateDashboard()
        resolvePromise!(serverAsset)
      } catch (error) {
        clearTimeout(timeoutId)
        // On error: rollback to original
        console.warn('[updateAsset] Rollback - restoring original asset', id)
        const currentIdx = assets.value.findIndex(a => a.id === id)
        if (currentIdx !== -1) {
          assets.value[currentIdx] = originalAsset
        }
        if (currentAsset.value?.id === id) {
          currentAsset.value = originalAsset
        }
        _syncingIds.delete(id)
        _pendingUpdateOperations.delete(dedupKey)
        rejectPromise!(error)
      }
    })()

    return operationPromise
  }

  function deleteAsset(id: string): Promise<void> {
    // 1. Check for existing pending operation (dedup)
    const dedupKey = `delete:${id}`
    const existingOp = _pendingDeleteOperations.get(dedupKey)
    if (existingOp) {
      return existingOp
    }

    // 2. Find asset and capture neighbor references for rollback positioning
    const idx = assets.value.findIndex(a => a.id === id)
    if (idx === -1) {
      // Asset not found, fall back to pessimistic API call
      return assetApi.deleteAsset(id).then(() => undefined)
    }

    // 3. Snapshot deleted asset + neighbor IDs for rollback (avoid stale index problem)
    const deletedAsset = JSON.parse(JSON.stringify(assets.value[idx])) as Asset
    const prevNeighborId = idx > 0 ? assets.value[idx - 1].id : null
    const nextNeighborId = idx < assets.value.length - 1 ? assets.value[idx + 1].id : null

    // Track whether this delete cleared currentAsset (for rollback)
    const wasCurrentAsset = currentAsset.value?.id === id

    // 4. Remove from assets list (optimistic)
    assets.value.splice(idx, 1)
    if (wasCurrentAsset) {
      currentAsset.value = null
    }
    _syncingIds.add(id)

    // 5. Create operation Promise with timeout
    let resolvePromise: () => void
    let rejectPromise: (reason: unknown) => void
    const operationPromise = new Promise<void>((resolve, reject) => {
      resolvePromise = resolve
      rejectPromise = reject
    })

    // Store pending operation
    _pendingDeleteOperations.set(dedupKey, operationPromise)

    // Timeout handler to prevent memory leak
    const timeoutId = setTimeout(() => {
      if (_pendingDeleteOperations.has(dedupKey)) {
        console.warn('[deleteAsset] Timeout - cleaning up stuck operation', id)
        _pendingDeleteOperations.delete(dedupKey)
        _syncingIds.delete(id)
        rejectPromise!(new Error('Operation timed out'))
      }
    }, OPERATION_TIMEOUT_MS)

    // 6. Start async work
    ;(async () => {
      try {
        await assetApi.deleteAsset(id)

        // On success: no further action needed, asset already removed
        clearTimeout(timeoutId)
        _syncingIds.delete(id)
        _pendingDeleteOperations.delete(dedupKey)
        useDashboardStore().invalidateDashboard()
        resolvePromise!()
      } catch (error) {
        clearTimeout(timeoutId)
        // On error: re-insert at correct position using neighbor references
        console.warn('[deleteAsset] Rollback - re-inserting deleted asset', id)
        const rollbackIdx = findInsertIndex(prevNeighborId, nextNeighborId)
        assets.value.splice(rollbackIdx, 0, deletedAsset)
        // Only restore currentAsset if this delete operation originally cleared it
        if (wasCurrentAsset) {
          currentAsset.value = deletedAsset
        }
        _syncingIds.delete(id)
        _pendingDeleteOperations.delete(dedupKey)
        rejectPromise!(error)
      }
    })()

    return operationPromise
  }

  // Helper: Find correct insertion index using neighbor references
  function findInsertIndex(prevId: string | null, nextId: string | null): number {
    if (prevId !== null) {
      const prevIdx = assets.value.findIndex(a => a.id === prevId)
      if (prevIdx !== -1) return prevIdx + 1
    }
    if (nextId !== null) {
      const nextIdx = assets.value.findIndex(a => a.id === nextId)
      if (nextIdx !== -1) return nextIdx
    }
    // Fallback: insert at end if neighbors not found
    return assets.value.length
  }

  async function updateValue(id: string, value: number) {
    const res = await assetApi.updateAssetValue(id, value)
    const idx = assets.value.findIndex(a => a.id === id)
    if (idx !== -1) assets.value[idx] = res.data
    if (currentAsset.value?.id === id) currentAsset.value = res.data
    useDashboardStore().invalidateDashboard()
  }

  async function sellAsset(id: string, data: AssetSellRequest): Promise<AssetSellResponse> {
    const res = await assetApi.sellAsset(id, data)
    assets.value = assets.value.filter(a => a.id !== id)
    if (currentAsset.value?.id === id) currentAsset.value = null
    useDashboardStore().invalidateDashboard()
    return res.data
  }

  async function retireAsset(id: string) {
    const res = await assetApi.retireAsset(id)
    const idx = assets.value.findIndex(a => a.id === id)
    if (idx !== -1) assets.value[idx] = res.data
    if (currentAsset.value?.id === id) currentAsset.value = res.data
    useDashboardStore().invalidateDashboard()
    return res.data
  }

  async function reactivateAsset(id: string) {
    const res = await assetApi.reactivateAsset(id)
    const idx = assets.value.findIndex(a => a.id === id)
    if (idx !== -1) assets.value[idx] = res.data
    if (currentAsset.value?.id === id) currentAsset.value = res.data
    useDashboardStore().invalidateDashboard()
    return res.data
  }

  return {
    assets, currentAsset, loading, isSyncing,
    fetchAssets, fetchAsset, createAsset, updateAsset, deleteAsset, updateValue,
    sellAsset, retireAsset, reactivateAsset,
  }
})