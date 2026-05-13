// Vitest global setup for HMR mocks
import { vi } from 'vitest'

// Mock import.meta.hot before any modules load
const mockHotData: Record<string, unknown> = {}

if (!globalThis.importMetaHotMocked) {
  Object.defineProperty(globalThis, 'importMetaHotMocked', {
    value: true,
    writable: false,
  })

  const originalImportMeta = globalThis.importMeta

  globalThis.importMeta = {
    ...originalImportMeta,
    hot: {
      data: mockHotData,
      accept: vi.fn(),
      dispose: vi.fn(),
      invalidate: vi.fn(),
      on: vi.fn(),
    },
  }

  // Also stub for vitest
  vi.stubGlobal('import.meta', globalThis.importMeta)
}

// Mock the loading composable to prevent import.meta.hot initialization issues
vi.mock('../../packages/auth/src/composables/loading', () => ({
  useLoadingOverlay: () => ({
    isLoading: { value: false },
    isDismissing: { value: false },
    increment: vi.fn(),
    decrement: vi.fn(),
    show: vi.fn(),
    hide: vi.fn(),
  }),
}))