const COOKIE_NAME = 'numina_device_id'
const LS_KEY = 'numina_device_id'
const IDB_NAME = 'numina_device_store'
const IDB_STORE = 'kv'
const IDB_KEY = 'device_id'

// --- IndexedDB helpers ---

function openIdb(): Promise<IDBDatabase | null> {
  return new Promise((resolve) => {
    try {
      const req = indexedDB.open(IDB_NAME, 1)
      req.onupgradeneeded = () => {
        const db = req.result
        if (!db.objectStoreNames.contains(IDB_STORE)) {
          db.createObjectStore(IDB_STORE)
        }
      }
      req.onsuccess = () => resolve(req.result)
      req.onerror = () => resolve(null)
    } catch {
      resolve(null)
    }
  })
}

async function readFromIdb(): Promise<string | null> {
  try {
    const db = await openIdb()
    if (!db) return null
    return new Promise((resolve) => {
      try {
        const tx = db.transaction(IDB_STORE, 'readonly')
        const req = tx.objectStore(IDB_STORE).get(IDB_KEY)
        req.onsuccess = () => resolve((req.result as string) ?? null)
        req.onerror = () => resolve(null)
        // 注意：不调用 db.close()，因为会中止事务
        // IndexedDB 连接由浏览器 GC 管理
      } catch {
        resolve(null)
      }
    })
  } catch {
    return null
  }
}

async function writeToIdb(value: string): Promise<void> {
  try {
    const db = await openIdb()
    if (!db) return
    await new Promise<void>((resolve) => {
      try {
        const tx = db.transaction(IDB_STORE, 'readwrite')
        tx.objectStore(IDB_STORE).put(value, IDB_KEY)
        tx.oncomplete = () => resolve()
        tx.onerror = () => resolve()
        tx.onabort = () => resolve()
      } catch {
        resolve()
      }
    })
  } catch {
    // IndexedDB unavailable — non-fatal
  }
}

async function clearIdb(): Promise<void> {
  try {
    const db = await openIdb()
    if (!db) return
    await new Promise<void>((resolve) => {
      try {
        const tx = db.transaction(IDB_STORE, 'readwrite')
        tx.objectStore(IDB_STORE).delete(IDB_KEY)
        tx.oncomplete = () => resolve()
        tx.onerror = () => resolve()
        tx.onabort = () => resolve()
      } catch {
        resolve()
      }
    })
  } catch {
    // ignore
  }
}

// --- Public API ---

export function readDeviceIdSync(): string | null {
  const match = document.cookie.match(/(?:^|; )numina_device_id=([^;]+)/)
  if (match) return decodeURIComponent(match[1])
  try {
    return localStorage.getItem(LS_KEY)
  } catch {
    return null
  }
}

export async function readDeviceId(): Promise<string | null> {
  // L1: cookie
  const match = document.cookie.match(/(?:^|; )numina_device_id=([^;]+)/)
  if (match) {
    const value = decodeURIComponent(match[1])
    // backfill lower layers
    try { localStorage.setItem(LS_KEY, value) } catch { /* ignore */ }
    writeToIdb(value) // fire-and-forget
    return value
  }

  // L2: localStorage
  try {
    const lsValue = localStorage.getItem(LS_KEY)
    if (lsValue) {
      writeToIdb(lsValue) // backfill
      return lsValue
    }
  } catch { /* ignore */ }

  // L3: IndexedDB
  const idbValue = await readFromIdb()
  if (idbValue) {
    // backfill localStorage
    try { localStorage.setItem(LS_KEY, idbValue) } catch { /* ignore */ }
    return idbValue
  }

  // L4: ETag recovery from HTTP cache
  const etagValue = await recoverFromEtag()
  if (etagValue) {
    // recoverFromEtag already writes to all layers
    return etagValue
  }

  return null
}

export function writeDeviceId(deviceId: string): void {
  const maxAge = 90 * 24 * 3600
  document.cookie = `${COOKIE_NAME}=${encodeURIComponent(deviceId)}; path=/; max-age=${maxAge}; samesite=lax`
  try {
    localStorage.setItem(LS_KEY, deviceId)
  } catch {
    // localStorage unavailable (private mode, quota exceeded) — cookie is primary
  }
  writeToIdb(deviceId) // fire-and-forget
}

export async function clearDeviceId(): Promise<void> {
  document.cookie = `${COOKIE_NAME}=; path=/; max-age=0`
  try {
    localStorage.removeItem(LS_KEY)
  } catch {
    // ignore
  }
  await clearIdb()
}

// --- ETag layer (L4) ---

/**
 * Recover device_id from HTTP cache ETag.
 * Called when all JS storage layers (cookie, localStorage, IndexedDB) are empty.
 * The browser's HTTP cache may still have the ETag from a previous trust response.
 */
export async function recoverFromEtag(): Promise<string | null> {
  try {
    const resp = await fetch('/api/v1/auth/device-ping', {
      credentials: 'same-origin',
      cache: 'force-cache', // 强制使用缓存，确保从 HTTP cache 恢复 ETag
    })
    if (!resp.ok) return null
    const json = await resp.json()
    // Response is envelope-wrapped: { code, message, data: { device_id } }
    const deviceId = json?.data?.device_id ?? json?.device_id ?? null
    if (deviceId) {
      // Write back to all layers
      writeDeviceId(deviceId)
      return deviceId
    }
    return null
  } catch {
    return null
  }
}

/**
 * Establish ETag cache after trust.
 * Sends a ping with If-None-Match header so the browser caches the ETag.
 */
export async function establishEtag(deviceId: string): Promise<void> {
  try {
    await fetch('/api/v1/auth/device-ping', {
      credentials: 'same-origin',
      headers: { 'If-None-Match': `"${deviceId}"` },
    })
  } catch {
    // non-fatal
  }
}
