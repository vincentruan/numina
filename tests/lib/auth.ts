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
 * Returns the access token for tests that need to make authenticated API calls
 * via page.request (which may not reliably send cookies in some environments).
 *
 * After this call, Axios sends the cookie automatically on all requests
 * (withCredentials: true is set in the frontend API client).
 */
export async function loginAs(page: Page, username: string, password: string): Promise<string> {
  // 1. Login — browser context receives httpOnly auth cookie
  const loginResp = await page.request.post('/api/v1/auth/login', {
    data: { username, password },
  })
  if (!loginResp.ok()) {
    const body = await loginResp.text()
    throw new Error(`loginAs failed for "${username}": HTTP ${loginResp.status()} — ${body}`)
  }
  const loginData = await loginResp.json()
  const accessToken: string = loginData.data?.access_token ?? loginData.access_token

  // 2. Fetch user object using Bearer token (avoids cookie-based rate limit issues)
  //    Retry once on 429 with a short backoff.
  let meResp = await page.request.get('/api/v1/auth/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (meResp.status() === 429) {
    await page.waitForTimeout(2000)
    meResp = await page.request.get('/api/v1/auth/me', {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
  }
  if (!meResp.ok()) {
    throw new Error(`GET /auth/me failed: HTTP ${meResp.status()}`)
  }
  const meBody = await meResp.json()
  const user = meBody.data ?? meBody

  // 3. Navigate to root so localStorage is accessible in this origin
  await page.goto('/')

  // 4. Inject numina_user — satisfies router guard isLoggedIn check
  await page.evaluate((u) => {
    localStorage.setItem('numina_user', JSON.stringify(u))
  }, user)

  return accessToken
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
