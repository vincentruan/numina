import { test, expect } from '@playwright/test'
import { loginAsChild } from '../lib/auth'

/**
 * Cluster Knowledge Map E2E (U6)
 *
 * Covers plan Acceptance Examples AE1-AE5:
 *   AE1 — subjects → cluster territories with mastery-colored nodes
 *   AE2 — tapping a learning node starts practice
 *   AE3 — tapping a locked node shows prerequisite guidance
 *   AE4 — cross-subject bridge badge navigates to target subject
 *   AE5 — zero-progress child sees "you are here" marker
 *
 * Requires:
 *   - child app running on BASE_URL (default http://localhost:5174)
 *   - backend reachable through the same origin
 *   - seeded learning data for the test child
 */

const PARENT_USER = process.env.E2E_PARENT_USER ?? 'demouser'
const PARENT_PASS = process.env.E2E_PARENT_PASS ?? 'DemoPass123'
const CHILD_NAME = process.env.E2E_CHILD_NAME ?? '小宝'
const CHILD_PIN = (process.env.E2E_CHILD_PIN ?? '🐱,🐶,🌟,🌈').split(',')

test.describe('Cluster Knowledge Map', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsChild(page, PARENT_USER, PARENT_PASS, CHILD_NAME, CHILD_PIN)
  })

  test('AE1: renders subject tabs and cluster territories with mastery nodes', async ({ page }) => {
    await page.goto('/child/learning')
    await page.waitForLoadState('networkidle')

    // Subject tabs present
    const tabs = page.locator('.subject-tab')
    await expect(tabs.first()).toBeVisible({ timeout: 10_000 })
    expect(await tabs.count()).toBeGreaterThan(0)

    // At least one cluster territory rendered
    const territories = page.locator('.cluster-territory')
    await expect(territories.first()).toBeVisible({ timeout: 10_000 })
    expect(await territories.count()).toBeGreaterThan(0)

    // Each territory has a domain label
    const firstTitle = territories.first().locator('.cluster-territory__title')
    await expect(firstTitle).toBeVisible()
    expect((await firstTitle.textContent())?.trim().length).toBeGreaterThan(0)

    // Topic nodes carry a mastery state class
    const nodes = page.locator('.topic-node')
    expect(await nodes.count()).toBeGreaterThan(0)
    const validStates = ['mastered', 'learning', 'available', 'locked', 'review']
    const firstNodeClass = (await nodes.first().getAttribute('class')) ?? ''
    expect(validStates.some((s) => firstNodeClass.includes(`topic-node--${s}`))).toBe(true)
  })

  test('AE2: tapping a practice-eligible node routes to practice action', async ({ page }) => {
    await page.goto('/child/learning')
    await page.waitForLoadState('networkidle')

    // Find an available/learning node (practice-eligible)
    const practiceNode = page
      .locator('.topic-node--available, .topic-node--learning')
      .first()

    if ((await practiceNode.count()) === 0) {
      test.skip(true, 'No practice-eligible topic in seeded data')
      return
    }

    await practiceNode.click({ force: true })
    // Route should carry the practice action query param
    await page.waitForURL(/\/learning\/topic\/\d+/, { timeout: 10_000 })
    expect(page.url()).toContain('action=practice')
  })

  test('AE3: tapping a locked node opens prerequisite guidance sheet', async ({ page }) => {
    await page.goto('/child/learning')
    await page.waitForLoadState('networkidle')

    const lockedNode = page.locator('.topic-node--locked').first()
    if ((await lockedNode.count()) === 0) {
      test.skip(true, 'No locked topic in seeded data')
      return
    }

    await lockedNode.click({ force: true })

    // Bottom sheet appears with prerequisite list or the all-met message
    const sheet = page.locator('.prereq-guidance')
    await expect(sheet).toBeVisible({ timeout: 10_000 })

    const hasList = (await page.locator('.prereq-item').count()) > 0
    const hasAllMet = await page.locator('.prereq-guidance__all-met').isVisible().catch(() => false)
    expect(hasList || hasAllMet).toBe(true)
  })

  test('AE4: bridge badge switches to target subject', async ({ page }) => {
    await page.goto('/child/learning')
    await page.waitForLoadState('networkidle')

    // Bridges exist only for some subjects — find a subject tab that renders
    // at least one bridge badge before asserting navigation.
    const tabs = page.locator('.subject-tab')
    await expect(tabs.first()).toBeVisible({ timeout: 10_000 })
    const tabCount = await tabs.count()

    let found = false
    for (let i = 0; i < tabCount; i++) {
      await tabs.nth(i).click()
      const badge = page.locator('.bridge-badge').first()
      if (await badge.isVisible({ timeout: 2_000 }).catch(() => false)) {
        found = true
        break
      }
    }
    if (!found) {
      test.skip(true, 'No cross-subject bridge badges rendered for any subject tab')
      return
    }

    const activeBefore = await page
      .locator('.subject-tab.active .subject-tab__label')
      .textContent()

    // The territory list re-renders after the tab switch settles, so wait for
    // a stable frame before clicking the badge.
    await page.waitForLoadState('networkidle')
    const badge = page.locator('.bridge-badge').first()
    await expect(badge).toBeVisible({ timeout: 10_000 })
    await badge.click({ force: true })

    // Active tab should change to the bridge's target subject
    await expect
      .poll(
        async () => page.locator('.subject-tab.active .subject-tab__label').textContent(),
        { timeout: 10_000 },
      )
      .not.toBe(activeBefore)
  })

  test('AE5: progress bar and frontier marker render', async ({ page }) => {
    await page.goto('/child/learning')
    await page.waitForLoadState('networkidle')

    // Progress bar present with mastered/total text
    const progressText = page.locator('.cluster-map__progress-text')
    await expect(progressText).toBeVisible({ timeout: 10_000 })
    expect(await progressText.textContent()).toMatch(/\d+\s*\/\s*\d+/)

    // A frontier marker exists when not all topics are mastered
    const hereMarker = page.locator('.topic-node__here')
    const celebration = page.locator('.cluster-map__celebration')
    const allMastered = await celebration.isVisible().catch(() => false)
    if (allMastered) {
      // Fully mastered subjects have no "here" marker — that's the specified behavior
      expect(await hereMarker.count()).toBe(0)
    } else {
      expect(await hereMarker.count()).toBeGreaterThan(0)
    }
  })

  test('responsive: map is usable at 375px width', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto('/child/learning')
    await page.waitForLoadState('networkidle')

    const territories = page.locator('.cluster-territory')
    await expect(territories.first()).toBeVisible({ timeout: 10_000 })

    // No horizontal overflow
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
    )
    expect(overflow).toBe(false)

    // Touch targets meet the 44px minimum
    const nodeBox = await page.locator('.topic-node-wrapper').first().boundingBox()
    expect(nodeBox).not.toBeNull()
    expect(nodeBox!.width).toBeGreaterThanOrEqual(44)
    expect(nodeBox!.height).toBeGreaterThanOrEqual(44)
  })
})
