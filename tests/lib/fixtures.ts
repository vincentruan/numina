import type { Page } from '@playwright/test'
import { loginAs } from './auth'

export interface Credentials {
  username: string
  password: string
  accessToken?: string
}

/**
 * Empty family fixture — no assets, liabilities, or wishes.
 * Use for tests that need an authenticated session with zero data
 * (e.g. route guard tests, empty-state tests).
 */
export async function emptyFamily(page: Page): Promise<Credentials> {
  const accessToken = await loginAs(page, 'test_empty', 'TestEmpty123!')
  return { username: 'test_empty', password: 'TestEmpty123!', accessToken }
}

/**
 * Rich family fixture — full seed data (assets + liabilities + wishes).
 * Use for tests that need realistic data (e.g. dashboard, stats, AI features).
 *
 * NOTE: Tests using this fixture must be read-only. Do not mutate shared
 * state (delete assets, change settings, etc.) — the account is shared
 * across all tests in the suite.
 */
export async function richFamily(page: Page): Promise<Credentials> {
  const accessToken = await loginAs(page, 'test_rich', 'TestRich123!')
  return { username: 'test_rich', password: 'TestRich123!', accessToken }
}

/**
 * Single asset fixture — one physical asset (房产, ¥1,000,000).
 * Use for asset detail page tests and smoke tests.
 *
 * NOTE: Tests using this fixture must be read-only.
 */
export async function singleAsset(page: Page): Promise<Credentials> {
  const accessToken = await loginAs(page, 'test_asset', 'TestAsset123!')
  return { username: 'test_asset', password: 'TestAsset123!', accessToken }
}
