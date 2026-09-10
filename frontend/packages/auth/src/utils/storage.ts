/**
 * Storage utilities for authentication.
 * Copied from frontend/src/utils/storage.ts — pure localStorage, no framework deps.
 */

const USER_KEY = 'numina_user'

export interface StoredUser {
  id: string
  username?: string | null
  display_name: string
  avatar_color: string
  role: string
  theme?: string
  language?: string
  default_currency?: string
  view_mode?: string
}

export function getUser(): StoredUser | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as StoredUser
  } catch {
    return null
  }
}

export function setUser<T extends StoredUser = StoredUser>(user: T): void {
  const safeUser: StoredUser = {
    id: user.id,
    username: user.username,
    display_name: user.display_name,
    avatar_color: user.avatar_color,
    role: user.role,
    theme: user.theme,
    language: user.language,
    default_currency: user.default_currency,
    view_mode: user.view_mode,
  }
  localStorage.setItem(USER_KEY, JSON.stringify(safeUser))
}

export function removeUser(): void {
  localStorage.removeItem(USER_KEY)
}

// Generation counter: incremented on every clearAuth() (local or cross-module).
// fetchMe() snapshots this before its HTTP call and checks after — if the
// counter changed, the response is stale and must NOT call setUser().
let authGeneration = 0

export function getAuthGeneration(): number {
  return authGeneration
}

// Cross-module bridge: the app-level clearAuth() (which manages the same
// localStorage key) calls notifyAuthCleared() so the auth package's
// generation counter stays in sync even when clearAuth() fires from the
// axios interceptor layer.
export function notifyAuthCleared(): void {
  authGeneration++
}

export function clearAuth(): void {
  removeUser()
  notifyAuthCleared()
}
