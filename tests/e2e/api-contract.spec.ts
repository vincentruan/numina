import { test, expect } from '@playwright/test'
import * as fs from 'fs'
import * as path from 'path'

/**
 * API 契约快照测试
 *
 * 从后端直接获取 /openapi.json，与提交的快照做 diff。
 * 任何字段增删改都会让测试失败，强制开发者有意识地更新快照。
 *
 * 更新快照：
 *   cd tests && npm run update-snapshot
 *   或直接运行：node scripts/update-openapi-snapshot.js
 *
 * 注意：直接访问后端端口 8000（nginx 不代理 /openapi.json）。
 */

const SNAPSHOT_PATH = path.resolve(__dirname, '../fixtures/openapi.snapshot.json')
const BACKEND_OPENAPI_URL = 'http://localhost/openapi.json'

test('API 契约未发生变化 (openapi.json snapshot)', async ({ request }) => {
  // 获取当前 openapi.json
  const resp = await request.get(BACKEND_OPENAPI_URL)
  expect(resp.ok(), `无法访问 ${BACKEND_OPENAPI_URL}，请确认后端已启动`).toBeTruthy()

  const current = await resp.json()

  // 快照不存在时自动创建（首次运行）
  if (!fs.existsSync(SNAPSHOT_PATH)) {
    fs.mkdirSync(path.dirname(SNAPSHOT_PATH), { recursive: true })
    fs.writeFileSync(SNAPSHOT_PATH, JSON.stringify(current, null, 2) + '\n', 'utf-8')
    console.log(`✓ 首次运行：已创建快照 ${SNAPSHOT_PATH}`)
    return
  }

  const snapshot = JSON.parse(fs.readFileSync(SNAPSHOT_PATH, 'utf-8'))

  // 深度比较，输出有意义的 diff
  const currentStr = JSON.stringify(sortKeys(current), null, 2)
  const snapshotStr = JSON.stringify(sortKeys(snapshot), null, 2)

  if (currentStr !== snapshotStr) {
    const diff = computeDiff(snapshot, current)
    throw new Error(
      `API 契约已变化！请检查是否为有意的变更。\n\n` +
      `如果是有意变更，运行以下命令更新快照：\n` +
      `  cd tests && node scripts/update-openapi-snapshot.js\n\n` +
      `变更摘要：\n${diff}`
    )
  }
})

/**
 * 递归对对象的 key 排序，确保 diff 不受 key 顺序影响。
 */
function sortKeys(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(sortKeys)
  if (obj !== null && typeof obj === 'object') {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([k, v]) => [k, sortKeys(v)])
    )
  }
  return obj
}

/**
 * 生成简洁的变更摘要（路径级别，不输出完整 JSON）。
 */
function computeDiff(snapshot: Record<string, unknown>, current: Record<string, unknown>): string {
  const lines: string[] = []

  // 检查顶层字段变化
  const snapshotPaths = collectPaths(snapshot)
  const currentPaths = collectPaths(current)

  const added = currentPaths.filter((p) => !snapshotPaths.includes(p))
  const removed = snapshotPaths.filter((p) => !currentPaths.includes(p))

  if (added.length > 0) {
    lines.push(`新增 (${added.length} 项):`)
    added.slice(0, 20).forEach((p) => lines.push(`  + ${p}`))
    if (added.length > 20) lines.push(`  ... 还有 ${added.length - 20} 项`)
  }

  if (removed.length > 0) {
    lines.push(`删除 (${removed.length} 项):`)
    removed.slice(0, 20).forEach((p) => lines.push(`  - ${p}`))
    if (removed.length > 20) lines.push(`  ... 还有 ${removed.length - 20} 项`)
  }

  // 检查 paths 端点变化（最重要的契约变更）
  const snapshotPaths2 = Object.keys((snapshot.paths as Record<string, unknown>) ?? {})
  const currentPaths2 = Object.keys((current.paths as Record<string, unknown>) ?? {})
  const addedEndpoints = currentPaths2.filter((p) => !snapshotPaths2.includes(p))
  const removedEndpoints = snapshotPaths2.filter((p) => !currentPaths2.includes(p))

  if (addedEndpoints.length > 0) {
    lines.push(`\n新增端点:`)
    addedEndpoints.forEach((p) => lines.push(`  + ${p}`))
  }
  if (removedEndpoints.length > 0) {
    lines.push(`\n删除端点:`)
    removedEndpoints.forEach((p) => lines.push(`  - ${p}`))
  }

  return lines.join('\n') || '（字段值变化，请对比快照文件）'
}

/**
 * 收集对象中所有叶子节点的路径（用于粗粒度 diff）。
 * 限制深度避免输出过多。
 */
function collectPaths(obj: unknown, prefix = '', depth = 0): string[] {
  if (depth > 4) return []
  if (obj === null || typeof obj !== 'object') return [prefix]
  if (Array.isArray(obj)) return [`${prefix}[]`]
  return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
    collectPaths(v, prefix ? `${prefix}.${k}` : k, depth + 1)
  )
}
