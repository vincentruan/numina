import type { Page } from '@playwright/test'

/**
 * Log in as a user and establish a full browser session.
 *
 * The app uses httpOnly cookies (Phase 2 security model) — JS cannot read the
 * auth token. This helper:
 *   1. POSTs to /api/v1/auth/login via page.request so the browser context
 *      receives the httpOnly Set-Cookie from the server response.
 *   2. GETs /api/v1/auth/me to retrieve the user object.
 *   3. Navigates to / so localStorage is accessible.
 *   4. Injects localStorage['numina_user'] with the user object so the Vue
 *      router guard's getUser() check passes.
 *
 * After this call, Axios sends the cookie automatically on all requests
 * (withCredentials: true is set in the frontend API client).
 */
export async function loginAs(page: Page, username: string, password: string): Promise<void> {
  // 1. Login — browser context receives httpOnly auth cookie
  const loginResp = await page.request.post('/api/v1/auth/login', {
    data: { username, password },
  })
  if (!loginResp.ok()) {
    const body = await loginResp.text()
    throw new Error(`loginAs failed for "${username}": HTTP ${loginResp.status()} — ${body}`)
  }

  // 2. Fetch user object (login response is TokenResponse, does not include user fields)
  const meResp = await page.request.get('/api/v1/auth/me')
  if (!meResp.ok()) {
    throw new Error(`GET /auth/me failed: HTTP ${meResp.status()}`)
  }
  const user = await meResp.json()

  // 3. Navigate to root so localStorage is accessible in this origin
  await page.goto('/')

  // 4. Inject numina_user — satisfies router guard isLoggedIn check
  await page.evaluate((u) => {
    localStorage.setItem('numina_user', JSON.stringify(u))
  }, user)
}

/**
 * Clear the browser session (localStorage only — the httpOnly cookie is
 * cleared server-side on logout, but for test teardown clearing localStorage
 * is sufficient to reset the router guard state).
 */
export async function logoutAs(page: Page): Promise<void> {
  await page.evaluate(() => {
    localStorage.removeItem('numina_user')
  })
}
