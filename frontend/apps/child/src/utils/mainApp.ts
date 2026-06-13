/**
 * Main app URL utilities for child app.
 *
 * In production: empty string (same origin, nginx routes /login to main container).
 * In development: use current hostname + port 5173 (supports LAN access).
 */

export function getMainBaseUrl(): string {
  // Production: same origin, relative path works
  if (import.meta.env.PROD) {
    return ''
  }
  // Dev mode: preserve hostname (supports LAN IP like 100.72.41.99)
  // Main app dev server runs on port 5173
  return `http://${window.location.hostname}:5173`
}