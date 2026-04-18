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
}

/**
 * Log in as a child user via PIN auth and establish a child browser session.
 *
 * Child auth uses a different flow from adult auth:
 *   1. POST /api/v1/auth/login as parent → get parentToken
 *   2. GET /api/v1/family/children → find child by display_name, extract child_id
 *   3. POST /api/v1/auth/child/login with { child_id, pin_sequence } → get child token
 *   4. GET /api/v1/auth/me with child Bearer token → get child user object
 *   5. Navigate to / and inject localStorage['numina_user'] with child user object
 *
 * Returns { childId, parentToken } for specs that need both contexts.
 */
export async function loginAsChild(
  page: Page,
  parentUsername: string,
  parentPassword: string,
  childDisplayName: string,
  pin: string[]
): Promise<{ childId: string; parentToken: string }> {
  // 1. Parent login to get token for family/children lookup
  const parentLoginResp = await page.request.post('/api/v1/auth/login', {
    data: { username: parentUsername, password: parentPassword },
  })
  if (!parentLoginResp.ok()) {
    const body = await parentLoginResp.text()
    throw new Error(`loginAsChild: parent login failed for "${parentUsername}": HTTP ${parentLoginResp.status()} — ${body}`)
  }
  const parentLoginData = await parentLoginResp.json()
  const parentToken: string = parentLoginData.data?.access_token ?? parentLoginData.access_token

  // 2. Find child by display_name
  const childrenResp = await page.request.get('/api/v1/family/children', {
    headers: { Authorization: `Bearer ${parentToken}` },
  })
  if (!childrenResp.ok()) {
    throw new Error(`loginAsChild: GET /family/children failed: HTTP ${childrenResp.status()}`)
  }
  const childrenData = await childrenResp.json()
  const children: Array<{ id: string; display_name: string }> = Array.isArray(childrenData)
    ? childrenData
    : (childrenData.data ?? [])
  const child = children.find((c) => c.display_name === childDisplayName)
  if (!child) {
    throw new Error(
      `loginAsChild: child "${childDisplayName}" not found. Available: ${children.map((c) => c.display_name).join(', ')}`
    )
  }
  const childId = child.id

  // 3. Child PIN login — browser context receives httpOnly child_access_token cookie
  const childLoginResp = await page.request.post('/api/v1/auth/child/login', {
    data: { child_id: childId, pin_sequence: pin },
  })
  if (!childLoginResp.ok()) {
    const body = await childLoginResp.text()
    throw new Error(`loginAsChild: child PIN login failed: HTTP ${childLoginResp.status()} — ${body}`)
  }
  const childLoginData = await childLoginResp.json()
  const childToken: string = childLoginData.data?.access_token ?? childLoginData.access_token

  // 4. Fetch child user object
  let meResp = await page.request.get('/api/v1/auth/me', {
    headers: { Authorization: `Bearer ${childToken}` },
  })
  if (meResp.status() === 429) {
    await page.waitForTimeout(2000)
    meResp = await page.request.get('/api/v1/auth/me', {
      headers: { Authorization: `Bearer ${childToken}` },
    })
  }
  if (!meResp.ok()) {
    throw new Error(`loginAsChild: GET /auth/me failed: HTTP ${meResp.status()}`)
  }
  const meBody = await meResp.json()
  const childUser = meBody.data ?? meBody

  // 5. Navigate to root and inject child session into localStorage
  await page.goto('/')
  await page.evaluate((u) => {
    localStorage.setItem('numina_user', JSON.stringify(u))
  }, childUser)

  return { childId, parentToken }
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
