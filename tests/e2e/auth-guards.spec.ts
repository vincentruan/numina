import { test, expect } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'
import { emptyFamily } from '../lib/fixtures'
import {
  PROTECTED_ROUTES,
  GUEST_ROUTES,
  PUBLIC_ROUTES,
  extractRouteNamesFromSource,
} from '../lib/routes'

// ─────────────────────────────────────────────────────────────────────────────
// Sync-check: verify routes.ts stays in sync with frontend/src/router/index.ts
// ─────────────────────────────────────────────────────────────────────────────
test('routes.ts covers all route names in frontend/src/router/index.ts', () => {
  const routerPath = path.resolve(
    __dirname,
    '../../frontend/apps/main/src/router/index.ts'
  )
  const source = fs.readFileSync(routerPath, 'utf-8')
  const routerNames = extractRouteNamesFromSource(source)

  const knownNames = new Set([
    ...PROTECTED_ROUTES.map((r) => r.name),
    ...GUEST_ROUTES.map((r) => r.name),
    ...PUBLIC_ROUTES.map((r) => r.name),
  ])

  const missing = routerNames.filter((name) => !knownNames.has(name))

  expect(
    missing,
    `routes.ts is missing these route names from the router:\n  ${missing.join('\n  ')}\n\nAdd them to PROTECTED_ROUTES or GUEST_ROUTES in tests/lib/routes.ts`
  ).toHaveLength(0)
})

// ─────────────────────────────────────────────────────────────────────────────
// Unauthenticated access → protected routes must redirect to /login
// ─────────────────────────────────────────────────────────────────────────────
for (const route of PROTECTED_ROUTES) {
  test(`unauthenticated: ${route.name} (${route.path}) → redirects to /login`, async ({ page }) => {
    // Each test gets a fresh page but shares the browser context (and its localStorage).
    // Navigate to the app origin first so we can clear localStorage via evaluate,
    // then navigate to the target route.
    await page.goto('/')
    await page.evaluate(() => localStorage.removeItem('numina_user'))
    await page.goto(route.path)
    await expect(page).toHaveURL(/\/login/)
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// Authenticated access → guest-only routes must redirect to /
// ─────────────────────────────────────────────────────────────────────────────
test.describe('authenticated: guest routes redirect to /', () => {
  test.beforeAll(async ({ browser }) => {
    // Warm up — the actual login happens per-page in each test via the fixture
    // We just verify the fixture works once here
    const page = await browser.newPage()
    await emptyFamily(page)
    await page.close()
  })

  for (const route of GUEST_ROUTES) {
    test(`authenticated: ${route.name} (${route.path}) → redirects to /`, async ({ page }) => {
      await emptyFamily(page)
      await page.goto(route.path)
      // Should redirect to dashboard (root path) — match full URL ending with /
      await expect(page).toHaveURL(/\/$/)
    })
  }
})
