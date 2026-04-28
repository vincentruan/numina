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
  }
  localStorage.setItem(USER_KEY, JSON.stringify(safeUser))
}

export function removeUser(): void {
  localStorage.removeItem(USER_KEY)
}

export function clearAuth(): void {
  removeUser()
}

const CHILD_FAMILY_ID_KEY = 'numina_child_family_id'

export function getChildFamilyId(): string | null {
  return localStorage.getItem(CHILD_FAMILY_ID_KEY)
}

export function setChildFamilyId(familyId: string): void {
  localStorage.setItem(CHILD_FAMILY_ID_KEY, familyId)
}

export function clearChildFamilyId(): void {
  localStorage.removeItem(CHILD_FAMILY_ID_KEY)
}
