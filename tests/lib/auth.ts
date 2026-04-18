import type { Page, BrowserContext } from '@playwright/test'

/**
 * Log in as a user and establish a full browser session.
 *
 * The app uses httpOnly cookies (Phase 2 security model) — JS cannot read the
 * auth token. This helper:
 *   1. POSTs to /api/v1/auth/login via context.request so cookies are set
 *   2. Copies cookies from APIRequestContext to BrowserContext (they may not sync automatically)
 *   3. GETs /api/v1/auth/me to retrieve the user object.
 *   4. Navigates to / so localStorage is accessible.
 *   5. Injects localStorage['numina_user'] with the user object so the Vue
 *      router guard's getUser() check passes.
 *
 * Returns the access token for tests that need to make authenticated API calls
 * via page.request (which may not reliably send cookies in some environments).
 *
 * After this call, Axios sends the cookie automatically on all requests
 * (withCredentials: true is set in the frontend API client).
 */
export async function loginAs(page: Page, username: string, password: string): Promise<string> {
  const context = page.context()

  // 1. Login via context.request — cookies stored in APIRequestContext
  const loginResp = await context.request.post('/api/v1/auth/login', {
    data: { username, password },
  })
  if (!loginResp.ok()) {
    const body = await loginResp.text()
    throw new Error(`loginAs failed for "${username}": HTTP ${loginResp.status()} — ${body}`)
  }
  const loginData = await loginResp.json()
  const accessToken: string = loginData.data?.access_token ?? loginData.access_token

  // 2. Copy cookies from APIRequestContext to BrowserContext
  //    Playwright sometimes doesn't sync these automatically
  const storageState = await context.request.storageState()
  console.log(`[loginAs] StorageState for ${username}:`, JSON.stringify(storageState, null, 2))

  if (storageState.cookies && storageState.cookies.length > 0) {
    // Ensure cookies have correct domain for browser context
    // APIRequestContext may set cookies without explicit domain
    const cookiesWithDomain = storageState.cookies.map(cookie => ({
      ...cookie,
      domain: cookie.domain || 'localhost',
    }))
    console.log(`[loginAs] Adding cookies to BrowserContext:`, JSON.stringify(cookiesWithDomain, null, 2))
    await context.addCookies(cookiesWithDomain)
  }

  // Verify cookies are now in BrowserContext
  const browserCookies = await context.cookies()
  console.log(`[loginAs] BrowserContext cookies after addCookies:`, JSON.stringify(browserCookies, null, 2))

  // 3. Fetch user object using Bearer token (avoids cookie-based rate limit issues)
  //    Retry once on 429 with a short backoff.
  let meResp = await context.request.get('/api/v1/auth/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  })
  if (meResp.status() === 429) {
    await page.waitForTimeout(2000)
    meResp = await context.request.get('/api/v1/auth/me', {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
  }
  if (!meResp.ok()) {
    throw new Error(`GET /auth/me failed: HTTP ${meResp.status()}`)
  }
  const meBody = await meResp.json()
  const user = meBody.data ?? meBody

  // 4. Navigate to root so localStorage is accessible in this origin
  await page.goto('/')

  // 5. Inject numina_user — satisfies router guard isLoggedIn check
  await page.evaluate((u) => {
    localStorage.setItem('numina_user', JSON.stringify(u))
  }, user)

  return accessToken
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
  const context = page.context()

  // 1. Parent login to get token for family/children lookup
  const parentLoginResp = await context.request.post('/api/v1/auth/login', {
    data: { username: parentUsername, password: parentPassword },
  })
  if (!parentLoginResp.ok()) {
    const body = await parentLoginResp.text()
    throw new Error(`loginAsChild: parent login failed for "${parentUsername}": HTTP ${parentLoginResp.status()} — ${body}`)
  }
  const parentLoginData = await parentLoginResp.json()
  const parentToken: string = parentLoginData.data?.access_token ?? parentLoginData.access_token

  // 2. Find child by display_name
  const childrenResp = await context.request.get('/api/v1/family/children', {
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

  // 3. Child PIN login via context.request
  const childLoginResp = await context.request.post('/api/v1/auth/child/login', {
    data: { child_id: childId, pin_sequence: pin },
  })
  if (!childLoginResp.ok()) {
    const body = await childLoginResp.text()
    throw new Error(`loginAsChild: child PIN login failed: HTTP ${childLoginResp.status()} — ${body}`)
  }
  const childLoginData = await childLoginResp.json()
  const childToken: string = childLoginData.data?.access_token ?? childLoginData.access_token

  // 4. Sync cookies from APIRequestContext to BrowserContext
  const cookies = await context.request.storageState()
  if (cookies.cookies && cookies.cookies.length > 0) {
    await context.addCookies(cookies.cookies)
  }

  // 5. Fetch child user object
  let meResp = await context.request.get('/api/v1/auth/me', {
    headers: { Authorization: `Bearer ${childToken}` },
  })
  if (meResp.status() === 429) {
    await page.waitForTimeout(2000)
    meResp = await context.request.get('/api/v1/auth/me', {
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