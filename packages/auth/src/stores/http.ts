/**
 * Shared HTTP client accessor for @numina/auth stores.
 * The app injects its configured axios instance via configureAuthHttp().
 */

import type { AxiosInstance } from 'axios'

let _http: AxiosInstance | null = null

export function configureAuthHttp(http: AxiosInstance) {
  _http = http
}

export function getHttp(): AxiosInstance {
  if (!_http) {
    throw new Error(
      '[numina/auth] HTTP client not configured. Call configureAuthHttp(http) in main.ts before using auth stores.',
    )
  }
  return _http
}
