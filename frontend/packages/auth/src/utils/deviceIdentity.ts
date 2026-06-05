const COOKIE_NAME = 'numina_device_id'
const LS_KEY = '_numina_device_id'
const IDB_STORE = 'numina_device_store'
const IDB_KEY = 'device_id'

export async function readDeviceId(): Promise<string | null> {
  const match = document.cookie.match(/(?:^|; )numina_device_id=([^;]+)/)
  if (match) {
    const value = decodeURIComponent(match[1])
    localStorage.setItem(LS_KEY, value)
    await writeToIdb(value)
    return value
  }

  const lsValue = localStorage.getItem(LS_KEY)
  if (lsValue) {
    await writeToIdb(lsValue)
    return lsValue
  }

  const idbValue = await readFromIdb()
  if (idbValue) {
    localStorage.setItem(LS_KEY, idbValue)
    return idbValue
  }

  return null
}

export async function recoverFromEtag(): Promise<string | null> {
  try {
    const resp = await fetch('/api/v1/auth/device-ping', { credentials: 'same-origin' })
    const data = await resp.json()
    if (data.device_id) {
      await writeDeviceId(data.device_id)
      return data.device_id
    }
    return null
  } catch {
    return null
  }
}

export async function writeDeviceId(deviceId: string): Promise<void> {
  localStorage.setItem(LS_KEY, deviceId)
  await writeToIdb(deviceId)
}

export function clearDeviceId(): void {
  localStorage.removeItem(LS_KEY)
  document.cookie = `${COOKIE_NAME}=; Path=/; Max-Age=0`
  clearIdb()
}

function openIdb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_STORE, 1)
    req.onupgradeneeded = () => {
      req.result.createObjectStore('kv')
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function readFromIdb(): Promise<string | null> {
  try {
    const db = await openIdb()
    return new Promise((resolve) => {
      const tx = db.transaction('kv', 'readonly')
      const req = tx.objectStore('kv').get(IDB_KEY)
      req.onsuccess = () => resolve(req.result ?? null)
      req.onerror = () => resolve(null)
    })
  } catch {
    return null
  }
}

async function writeToIdb(value: string): Promise<void> {
  try {
    const db = await openIdb()
    const tx = db.transaction('kv', 'readwrite')
    tx.objectStore('kv').put(value, IDB_KEY)
  } catch {
    // IndexedDB unavailable — silent fallback
  }
}

async function clearIdb(): Promise<void> {
  try {
    const db = await openIdb()
    const tx = db.transaction('kv', 'readwrite')
    tx.objectStore('kv').delete(IDB_KEY)
  } catch {
    // silent
  }
}
