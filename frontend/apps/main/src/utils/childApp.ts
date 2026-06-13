/**
 * Child app URL utilities.
 *
 * In production: nginx routes /child/* to frontend-child container.
 * In development: use current hostname + port 5174 (supports LAN access).
 */

export function getChildBaseUrl(): string {
  // Production: relative path handled by nginx
  if (import.meta.env.PROD) {
    return '/child/'
  }
  // Dev mode: preserve hostname (supports LAN IP like 100.72.41.99)
  // Only change port to 5174 where child dev server runs
  return `http://${window.location.hostname}:5174`
}