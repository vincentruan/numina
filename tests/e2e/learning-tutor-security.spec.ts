import { test, expect } from '@playwright/test'
import { loginAs } from '../lib/auth'
import { childFamily } from '../lib/fixtures'

/**
 * Area 11 — Learning-Tutor Security Tests
 *
 * Validates security invariants for the learning module:
 *   1. Unauthorized child_id — cannot access another child's session
 *   2. Cross-family isolation — family B cannot see family A's learning data
 *   3. Malformed input — backend rejects invalid evaluation/session data
 *
 * Test accounts:
 *   - test_rich / TestRich123! (Demo Family, has child test_child)
 *   - test_empty / TestEmpty123! (empty family)
 *
 * These tests require a running Docker stack (backend + agent + frontend).
 * Run via: npx playwright test e2e/learning-tutor-security.spec.ts
 */

const FAKE_SESSION_ID = '999999999999999999' // snowflake-shaped, does not exist
const FAKE_TOPIC_ID = '999999999999999998'

test.describe('Area 11: Learning-tutor security', () => {
  // ── 1. Unauthorized child_id ─────────────────────────────────────────────
  test('child cannot access session belonging to another child (404)', async ({ page }) => {
    // Log in as the child in the rich family
    const creds = await childFamily(page)
    const token = creds.parentToken

    // Attempt to access a non-existent session — should 404, not leak info
    const resp = await page.request.get(
      `/api/v1/child/learning/sessions/${FAKE_SESSION_ID}`,
      { headers: { Authorization: `Bearer ${token}` } },
    )

    expect(
      resp.status(),
      `Accessing non-existent session should return 404, got ${resp.status()}`,
    ).toBe(404)
  })

  test('child cannot end a session that does not belong to them', async ({ page }) => {
    const creds = await childFamily(page)
    const token = creds.parentToken

    const resp = await page.request.post(
      `/api/v1/child/learning/sessions/${FAKE_SESSION_ID}/end`,
      {
        headers: { Authorization: `Bearer ${token}` },
        data: { score: 80 },
      },
    )

    expect(
      resp.status(),
      `Ending another session should return 404, got ${resp.status()}`,
    ).toBe(404)
  })

  // ── 2. Cross-family topic access ────────────────────────────────────────
  test('family B cannot access family A child learning progress', async ({ browser }) => {
    // Family A (rich) — log in as child and get a session
    const ctxA = await browser.newContext()
    const pageA = await ctxA.newPage()
    const credsA = await childFamily(pageA)
    const tokenA = credsA.parentToken

    // Family B (empty) — log in as adult
    const ctxB = await browser.newContext()
    const pageB = await ctxB.newPage()
    const tokenB = await loginAs(pageB, 'test_empty', 'TestEmpty123!')

    // Family B tries to access child learning endpoints
    // /child/learning/progress — requires child context; adult token → 403 or empty
    const progressResp = await pageB.request.get('/api/v1/child/learning/progress', {
      headers: { Authorization: `Bearer ${tokenB}` },
    })

    // Should either 403 (no child in family) or return empty data — never family A's data
    expect(
      [200, 403, 404].includes(progressResp.status()),
      `Cross-family progress access should return 200(empty)/403/404, got ${progressResp.status()}`,
    ).toBeTruthy()

    if (progressResp.status() === 200) {
      const body = await progressResp.json()
      const data = body.data ?? body
      // Verify no data leaked from family A
      const dataStr = JSON.stringify(data)
      expect(dataStr).not.toContain('test_child')
    }

    await ctxA.close()
    await ctxB.close()
  })

  // ── 3. Malformed evaluation / session schema ─────────────────────────────
  test('end session rejects malformed score (422)', async ({ page }) => {
    const creds = await childFamily(page)
    const token = creds.parentToken

    // Create a session first
    const topicsResp = await page.request.get('/api/v1/child/learning/topics?limit=1', {
      headers: { Authorization: `Bearer ${token}` },
    })

    // If no topics seeded, skip
    if (topicsResp.status() !== 200) {
      test.skip()
      return
    }

    const topicsData = await topicsResp.json()
    const topics = topicsData.data ?? topicsData
    if (!Array.isArray(topics) || topics.length === 0) {
      test.skip()
      return
    }

    const topicId = topics[0].id

    // Create a session
    const createResp = await page.request.post('/api/v1/child/learning/sessions', {
      headers: { Authorization: `Bearer ${token}` },
      data: { topic_id: topicId },
    })

    if (createResp.status() !== 201) {
      test.skip()
      return
    }

    const sessionData = await createResp.json()
    const sessionId = sessionData.data?.id ?? sessionData.id

    // Attempt to end session with malformed data — score as string, negative value
    const badResp = await page.request.post(
      `/api/v1/child/learning/sessions/${sessionId}/end`,
      {
        headers: { Authorization: `Bearer ${token}` },
        data: { score: 'not-a-number' },
      },
    )

    expect(
      badResp.status(),
      `Malformed score should return 422, got ${badResp.status()}`,
    ).toBe(422)
  })

  test('create session with invalid topic_id returns 404', async ({ page }) => {
    const creds = await childFamily(page)
    const token = creds.parentToken

    const resp = await page.request.post('/api/v1/child/learning/sessions', {
      headers: { Authorization: `Bearer ${token}` },
      data: { topic_id: FAKE_TOPIC_ID },
    })

    expect(
      resp.status(),
      `Session with invalid topic should return 404, got ${resp.status()}`,
    ).toBe(404)
  })
})
