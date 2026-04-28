/**
 * Storage utilities for authentication.
 *
 * Security Strategy (Phase 2):
 * - Tokens stored in httpOnly Cookie (server-set, XSS-resistant)
 * - Only non-sensitive user info stored in localStorage
 * - Cookie is automatically sent with requests (no manual Authorization header)
 *
 * Legacy localStorage token storage removed for security.
 */

const USER_KEY = 'numina_user'

// User info stored in localStorage (non-sensitive)
// Only: id, display_name, avatar_color, role, theme, language, default_currency
// NOT: email, family_id, or any sensitive data

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

export function getUser<T extends StoredUser = StoredUser>(): T | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}

export function setUser<T extends StoredUser = StoredUser>(user: T): void {
  // Store only non-sensitive fields
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
  // Only clear user info (tokens are in httpOnly Cookie, managed by server)
  removeUser()
}

// Legacy functions removed (tokens now in httpOnly Cookie):
// - getToken, setToken, removeToken
// - getRefreshToken, setRefreshToken, removeRefreshToken
//
// For backward compatibility during migration, these are stubs:
export function getToken(): string | null {
  // Tokens are now in httpOnly Cookie, not accessible to JS
  return null
}

export function getRefreshToken(): string | null {
  // Tokens are now in httpOnly Cookie, not accessible to JS
  return null
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