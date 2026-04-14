#!/usr/bin/env node
/**
 * 更新 openapi.json 快照
 *
 * 用法：
 *   node tests/scripts/update-openapi-snapshot.js
 *   或：cd tests && npm run update-snapshot
 *
 * 需要后端正在运行（docker compose up 或本地 uvicorn）。
 */

const fs = require('fs')
const path = require('path')
const http = require('http')

const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000'
const SNAPSHOT_PATH = path.resolve(__dirname, '../fixtures/openapi.snapshot.json')

function fetchJson(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = ''
      res.on('data', (chunk) => (data += chunk))
      res.on('end', () => {
        try {
          resolve(JSON.parse(data))
        } catch (e) {
          reject(new Error(`JSON parse error: ${e.message}`))
        }
      })
    }).on('error', reject)
  })
}

async function main() {
  console.log(`从 ${BACKEND_URL}/openapi.json 获取最新 API 规范...`)

  let spec
  try {
    spec = await fetchJson(`${BACKEND_URL}/openapi.json`)
  } catch (e) {
    console.error(`✗ 无法连接后端: ${e.message}`)
    console.error('  请确认后端已启动：docker compose up -d 或 uvicorn app.main:app')
    process.exit(1)
  }

  fs.mkdirSync(path.dirname(SNAPSHOT_PATH), { recursive: true })
  fs.writeFileSync(SNAPSHOT_PATH, JSON.stringify(spec, null, 2) + '\n', 'utf-8')

  const endpointCount = Object.keys(spec.paths || {}).length
  console.log(`✓ 快照已更新: ${SNAPSHOT_PATH}`)
  console.log(`  版本: ${spec.info?.version || '未知'}`)
  console.log(`  端点数: ${endpointCount}`)
  console.log('')
  console.log('请将更新后的快照文件提交到 git:')
  console.log('  git add tests/fixtures/openapi.snapshot.json')
  console.log('  git commit -m "chore(tests): update openapi snapshot"')
}

main()
