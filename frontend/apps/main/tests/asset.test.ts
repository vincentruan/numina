import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAssetStore } from '@/stores/asset'
import * as assetApi from '@/api/assets'
import type { Asset } from '@/types'

// Import the reset function for testing
import { _resetPendingOperations } from '@/stores/asset'

// Mock the API module
vi.mock('@/api/assets', () => ({
  createAsset: vi.fn(),
  getAssets: vi.fn(),
  getAsset: vi.fn(),
  updateAsset: vi.fn(),
  deleteAsset: vi.fn(),
  updateAssetValue: vi.fn(),
  sellAsset: vi.fn(),
  retireAsset: vi.fn(),
  reactivateAsset: vi.fn(),
}))

// Mock dashboard store
vi.mock('@/stores/dashboard', () => ({
  useDashboardStore: () => ({
    invalidateDashboard: vi.fn(),
  }),
}))

describe('useAssetStore - optimistic create', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    // Reset module-level state between tests
    _resetPendingOperations()
  })

  it('happy path: asset appears immediately with syncing indicator, ID replaced on success', async () => {
    const store = useAssetStore()
    const mockAsset: Asset = {
      id: 'server-id-123',
      name: '测试资产',
      category_id: 'cat-1',
      asset_type: 'physical',
      purchase_price: 1000,
      current_value: 1000,
      currency: 'CNY',
      purchase_date: '2026-04-18',
      status: 'in_use',
      user_id: 'user-1',
      family_id: 'family-1',
      created_at: '2026-04-18T00:00:00Z',
      updated_at: '2026-04-18T00:00:00Z',
    }

    // Mock slow API response (simulate network delay)
    let resolveApi: (value: { data: Asset }) => void
    const apiPromise = new Promise<{ data: Asset }>((resolve) => {
      resolveApi = resolve
    })
    vi.mocked(assetApi.createAsset).mockReturnValue(apiPromise as any)

    // Start create operation
    const createPromise = store.createAsset({
      name: '测试资产',
      category_id: 'cat-1',
      asset_type: 'physical',
      purchase_price: 1000,
      current_value: 1000,
    } as any)

    // BEFORE API resolves: asset should already be in list with temp ID
    expect(store.assets.length).toBe(1)
    expect(store.assets[0].name).toBe('测试资产')
    expect(store.assets[0].id).toMatch(/^temp-/) // temp ID format
    expect(store.isSyncing(store.assets[0].id)).toBe(true)

    // Resolve API
    resolveApi!({ data: mockAsset })
    await createPromise

    // AFTER API resolves: temp ID replaced with server ID, syncing cleared
    expect(store.assets.length).toBe(1)
    expect(store.assets[0].id).toBe('server-id-123')
    expect(store.isSyncing('server-id-123')).toBe(false)
    // Temp ID should no longer be tracked
    expect(store.isSyncing(store.assets.find(a => a.id.startsWith('temp-'))?.id || '')).toBe(false)
  })

  it('error path: asset removed from list on API error, syncing cleared', async () => {
    const store = useAssetStore()

    // Mock API error
    const apiError = {
      response: {
        status: 422,
        data: { message: '验证失败' },
      },
    }
    vi.mocked(assetApi.createAsset).mockRejectedValue(apiError)

    // Attempt create
    try {
      await store.createAsset({
        name: '测试资产',
        category_id: 'cat-1',
        asset_type: 'physical',
      })
    } catch (e) {
      // Expected to throw
      expect(e).toEqual(apiError)
    }

    // Asset should be removed from list
    expect(store.assets.length).toBe(0)
    // No syncing IDs tracked
    expect(store.isSyncing('any-id')).toBe(false)
  })

  it('dedup: rapid double-click prevents duplicate API call', async () => {
    const store = useAssetStore()
    const mockAsset: Asset = {
      id: 'server-id-456',
      name: '测试资产2',
      category_id: 'cat-1',
      asset_type: 'physical',
      purchase_price: 500,
      current_value: 500,
      currency: 'CNY',
      purchase_date: '2026-04-18',
      status: 'in_use',
      user_id: 'user-1',
      family_id: 'family-1',
      created_at: '2026-04-18T00:00:00Z',
      updated_at: '2026-04-18T00:00:00Z',
    }

    // Mock delayed API response
    let resolveApi: (value: { data: Asset }) => void
    const apiPromise = new Promise<{ data: Asset }>((resolve) => {
      resolveApi = resolve
    })
    vi.mocked(assetApi.createAsset).mockReturnValue(apiPromise as any)

    // Call createAsset twice rapidly
    const createPromise1 = store.createAsset({
      name: '测试资产2',
      category_id: 'cat-1',
      asset_type: 'physical',
    })
    const createPromise2 = store.createAsset({
      name: '测试资产2',
      category_id: 'cat-1',
      asset_type: 'physical',
    })

    // Resolve API
    resolveApi!({ data: mockAsset })
    await Promise.all([createPromise1, createPromise2])

    // API should have been called only once (deduplication goal)
    expect(assetApi.createAsset).toHaveBeenCalledTimes(1)

    // Only one asset should be in the list (not two temp assets)
    expect(store.assets.length).toBe(1)
    expect(store.assets[0].id).toBe('server-id-456')
  })

  it('currentAsset sync: currentAsset updated when viewing new asset', async () => {
    const store = useAssetStore()
    const mockAsset: Asset = {
      id: 'server-id-789',
      name: '测试资产3',
      category_id: 'cat-1',
      asset_type: 'physical',
      purchase_price: 2000,
      current_value: 2000,
      currency: 'CNY',
      purchase_date: '2026-04-18',
      status: 'in_use',
      user_id: 'user-1',
      family_id: 'family-1',
      created_at: '2026-04-18T00:00:00Z',
      updated_at: '2026-04-18T00:00:00Z',
    }

    vi.mocked(assetApi.createAsset).mockResolvedValue({ data: mockAsset } as any)

    // Create and set as currentAsset
    const created = await store.createAsset({
      name: '测试资产3',
      category_id: 'cat-1',
      asset_type: 'physical',
    })

    // Set currentAsset to the new asset (simulating navigation to detail page)
    store.currentAsset = created

    // After API success, currentAsset should have server ID
    expect(store.currentAsset?.id).toBe('server-id-789')
    expect(store.currentAsset?.name).toBe('测试资产3')
  })
})

describe('useAssetStore - optimistic update', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    _resetPendingOperations()
  })

  it('happy path: update appears immediately with syncing indicator', async () => {
    const store = useAssetStore()
    // Set up existing asset in store
    const existingAsset: Asset = {
      id: 'asset-1',
      name: '原名称',
      category_id: 'cat-1',
      asset_type: 'physical',
      purchase_price: 1000,
      current_value: 1000,
      currency: 'CNY',
      purchase_date: '2026-04-18',
      status: 'in_use',
      user_id: 'user-1',
      family_id: 'family-1',
      created_at: '2026-04-18T00:00:00Z',
      updated_at: '2026-04-18T00:00:00Z',
    }
    store.assets = [existingAsset]

    const updatedAsset: Asset = {
      ...existingAsset,
      name: '新名称',
      updated_at: '2026-04-18T01:00:00Z',
    }

    // Mock slow API response
    let resolveApi: (value: { data: Asset }) => void
    const apiPromise = new Promise<{ data: Asset }>((resolve) => {
      resolveApi = resolve
    })
    vi.mocked(assetApi.updateAsset).mockReturnValue(apiPromise as any)

    // Start update operation
    const updatePromise = store.updateAsset('asset-1', { name: '新名称' })

    // BEFORE API resolves: change should already appear with syncing indicator
    expect(store.assets[0].name).toBe('新名称')
    expect(store.isSyncing('asset-1')).toBe(true)

    // Resolve API
    resolveApi!({ data: updatedAsset })
    await updatePromise

    // AFTER API resolves: syncing indicator cleared
    expect(store.assets[0].name).toBe('新名称')
    expect(store.isSyncing('asset-1')).toBe(false)
  })

  it('error path: change reverted on API error', async () => {
    const store = useAssetStore()
    const existingAsset: Asset = {
      id: 'asset-2',
      name: '原名称',
      category_id: 'cat-1',
      asset_type: 'physical',
      purchase_price: 1000,
      current_value: 1000,
      currency: 'CNY',
      purchase_date: '2026-04-18',
      status: 'in_use',
      user_id: 'user-1',
      family_id: 'family-1',
      created_at: '2026-04-18T00:00:00Z',
      updated_at: '2026-04-18T00:00:00Z',
    }
    store.assets = [existingAsset]

    // Mock API error
    const apiError = {
      response: {
        status: 403,
        data: { message: '权限不足' },
      },
    }
    vi.mocked(assetApi.updateAsset).mockRejectedValue(apiError)

    // Attempt update
    try {
      await store.updateAsset('asset-2', { name: '错误名称' })
    } catch (e) {
      expect(e).toEqual(apiError)
    }

    // Change should be reverted
    expect(store.assets[0].name).toBe('原名称')
    expect(store.isSyncing('asset-2')).toBe(false)
  })

  it('currentAsset sync: currentAsset shows update immediately', async () => {
    const store = useAssetStore()
    const existingAsset: Asset = {
      id: 'asset-3',
      name: '原名称',
      category_id: 'cat-1',
      asset_type: 'physical',
      purchase_price: 1000,
      current_value: 1000,
      currency: 'CNY',
      purchase_date: '2026-04-18',
      status: 'in_use',
      user_id: 'user-1',
      family_id: 'family-1',
      created_at: '2026-04-18T00:00:00Z',
      updated_at: '2026-04-18T00:00:00Z',
    }
    store.assets = [existingAsset]
    store.currentAsset = existingAsset

    const updatedAsset: Asset = {
      ...existingAsset,
      name: '更新名称',
      updated_at: '2026-04-18T01:00:00Z',
    }
    vi.mocked(assetApi.updateAsset).mockResolvedValue({ data: updatedAsset } as any)

    // Update while viewing detail
    await store.updateAsset('asset-3', { name: '更新名称' })

    // currentAsset should reflect the update
    expect(store.currentAsset?.name).toBe('更新名称')
  })
})

describe('useAssetStore - optimistic delete', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    _resetPendingOperations()
  })

  it('happy path: asset disappears immediately on delete', async () => {
    const store = useAssetStore()
    const asset1: Asset = {
      id: 'asset-a',
      name: '资产A',
      category_id: 'cat-1',
      asset_type: 'physical',
      purchase_price: 1000,
      current_value: 1000,
      currency: 'CNY',
      purchase_date: '2026-04-18',
      status: 'in_use',
      user_id: 'user-1',
      family_id: 'family-1',
      created_at: '2026-04-18T00:00:00Z',
      updated_at: '2026-04-18T00:00:00Z',
    }
    const asset2: Asset = {
      id: 'asset-b',
      name: '资产B',
      category_id: 'cat-1',
      asset_type: 'physical',
      purchase_price: 2000,
      current_value: 2000,
      currency: 'CNY',
      purchase_date: '2026-04-18',
      status: 'in_use',
      user_id: 'user-1',
      family_id: 'family-1',
      created_at: '2026-04-18T00:00:00Z',
      updated_at: '2026-04-18T00:00:00Z',
    }
    store.assets = [asset1, asset2]

    // Mock slow API response
    let resolveApi: () => void
    const apiPromise = new Promise<void>((resolve) => {
      resolveApi = resolve
    })
    vi.mocked(assetApi.deleteAsset).mockReturnValue(apiPromise as any)

    // Start delete operation for asset1
    const deletePromise = store.deleteAsset('asset-a')

    // BEFORE API resolves: asset should already be removed
    expect(store.assets.length).toBe(1)
    expect(store.assets[0].id).toBe('asset-b') // Only asset2 remains
    expect(store.isSyncing('asset-a')).toBe(true)

    // Resolve API
    resolveApi!()
    await deletePromise

    // AFTER API resolves: no further action needed
    expect(store.assets.length).toBe(1)
    expect(store.isSyncing('asset-a')).toBe(false)
  })

  it('error path: asset reappears on API error', async () => {
    const store = useAssetStore()
    const asset1: Asset = {
      id: 'asset-c',
      name: '资产C',
      category_id: 'cat-1',
      asset_type: 'physical',
      purchase_price: 1000,
      current_value: 1000,
      currency: 'CNY',
      purchase_date: '2026-04-18',
      status: 'in_use',
      user_id: 'user-1',
      family_id: 'family-1',
      created_at: '2026-04-18T00:00:00Z',
      updated_at: '2026-04-18T00:00:00Z',
    }
    store.assets = [asset1]

    // Mock API error
    const apiError = {
      response: {
        status: 500,
        data: { message: '服务器错误' },
      },
    }
    vi.mocked(assetApi.deleteAsset).mockRejectedValue(apiError)

    // Attempt delete
    try {
      await store.deleteAsset('asset-c')
    } catch (e) {
      expect(e).toEqual(apiError)
    }

    // Asset should reappear
    expect(store.assets.length).toBe(1)
    expect(store.assets[0].id).toBe('asset-c')
    expect(store.isSyncing('asset-c')).toBe(false)
  })

  it('currentAsset sync: currentAsset restored on rollback', async () => {
    const store = useAssetStore()
    const asset1: Asset = {
      id: 'asset-d',
      name: '资产D',
      category_id: 'cat-1',
      asset_type: 'physical',
      purchase_price: 1000,
      current_value: 1000,
      currency: 'CNY',
      purchase_date: '2026-04-18',
      status: 'in_use',
      user_id: 'user-1',
      family_id: 'family-1',
      created_at: '2026-04-18T00:00:00Z',
      updated_at: '2026-04-18T00:00:00Z',
    }
    store.assets = [asset1]
    store.currentAsset = asset1 // Viewing the asset being deleted

    // Mock API error
    const apiError = {
      response: { status: 500, data: {} },
    }
    vi.mocked(assetApi.deleteAsset).mockRejectedValue(apiError)

    // Attempt delete while viewing
    try {
      await store.deleteAsset('asset-d')
    } catch (e) {
      expect(e).toEqual(apiError)
    }

    // currentAsset should be restored
    expect(store.currentAsset?.id).toBe('asset-d')
  })
})