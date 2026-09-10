/**
 * IndexedDB-based offline mutation queue.
 * Persists failed POST/PATCH/DELETE requests so they can be retried
 * when connectivity resumes.
 */

const DB_NAME = 'numina_offline_queue'
const DB_VERSION = 1
const STORE_NAME = 'pending_mutations'

export interface PendingMutation {
  key: string
  method: 'POST' | 'PATCH' | 'DELETE'
  url: string
  body: unknown
  idempotencyKey: string
  tempId?: string
  createdAt: number
  status: 'pending' | 'syncing' | 'failed'
  retryCount: number
}

function openQueueDb(): Promise<IDBDatabase | null> {
  return new Promise((resolve) => {
    try {
      const request = indexedDB.open(DB_NAME, DB_VERSION)
      request.onupgradeneeded = () => {
        const db = request.result
        if (!db.objectStoreNames.contains(STORE_NAME)) {
          db.createObjectStore(STORE_NAME, { keyPath: 'key' })
        }
      }
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => resolve(null)
    } catch {
      resolve(null)
    }
  })
}

export async function enqueue(
  mutation: Omit<PendingMutation, 'key' | 'createdAt' | 'status' | 'retryCount'>,
): Promise<string> {
  const db = await openQueueDb()
  if (!db) return ''

  const key = `${Date.now()}-${crypto.randomUUID()}`
  const entry: PendingMutation = {
    ...mutation,
    key,
    createdAt: Date.now(),
    status: 'pending',
    retryCount: 0,
  }

  return new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).put(entry)
    tx.oncomplete = () => resolve(key)
    tx.onerror = () => resolve('')
  })
}

export async function listPending(): Promise<PendingMutation[]> {
  const db = await openQueueDb()
  if (!db) return []

  return new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const request = tx.objectStore(STORE_NAME).getAll()
    request.onsuccess = () => {
      const all = request.result as PendingMutation[]
      resolve(
        all
          .filter((m) => m.status === 'pending')
          .sort((a, b) => a.createdAt - b.createdAt),
      )
    }
    request.onerror = () => resolve([])
  })
}

export async function listFailed(): Promise<PendingMutation[]> {
  const db = await openQueueDb()
  if (!db) return []

  return new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const request = tx.objectStore(STORE_NAME).getAll()
    request.onsuccess = () => {
      const all = request.result as PendingMutation[]
      resolve(
        all
          .filter((m) => m.status === 'failed')
          .sort((a, b) => a.createdAt - b.createdAt),
      )
    }
    request.onerror = () => resolve([])
  })
}

export async function updateStatus(
  key: string,
  status: PendingMutation['status'],
  retryCount?: number,
): Promise<void> {
  const db = await openQueueDb()
  if (!db) return

  return new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const getReq = store.get(key)
    getReq.onsuccess = () => {
      const entry = getReq.result as PendingMutation | undefined
      if (entry) {
        entry.status = status
        if (retryCount !== undefined) entry.retryCount = retryCount
        store.put(entry)
      }
    }
    tx.oncomplete = () => resolve()
    tx.onerror = () => resolve()
  })
}

export async function remove(key: string): Promise<void> {
  const db = await openQueueDb()
  if (!db) return

  return new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).delete(key)
    tx.oncomplete = () => resolve()
    tx.onerror = () => resolve()
  })
}

export async function clearQueue(): Promise<void> {
  const db = await openQueueDb()
  if (!db) return

  return new Promise((resolve) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    tx.objectStore(STORE_NAME).clear()
    tx.oncomplete = () => resolve()
    tx.onerror = () => resolve()
  })
}
