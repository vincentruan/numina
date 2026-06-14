/**
 * Artifact URL 生成 Helper
 *
 * 参考: frontend/src/core/artifacts/utils.ts urlOfArtifact()
 *
 * 重要差异：filepath 必须编码！
 *
 * 后端路由结构:
 * - sessions_router prefix: /ai (ai_chat.py line 31)
 * - mounted at: /api/v1 (main.py line 431)
 * - 最终路径: /api/v1/ai/sessions/{session_id}/artifacts/{filepath}
 */

import http from '@/api'

const BACKEND_BASE_URL = http.defaults.baseURL || ''

/**
 * 生成 Artifact API URL
 *
 * 格式: /api/v1/ai/sessions/{sessionId}/artifacts/{encodedPath}
 *
 * @param filepath - 文件路径（将被 encodeURIComponent）
 * @param sessionId - Session ID
 * @param download - 是否添加 ?download=true 参数
 * @returns 完整 URL
 */
export function urlOfArtifact(filepath: string, sessionId: string, download: boolean = false): string {
  const encodedPath = encodeURIComponent(filepath)
  const url = `${BACKEND_BASE_URL}/ai/sessions/${sessionId}/artifacts/${encodedPath}`
  return download ? `${url}?download=true` : url
}

/**
 * 生成 Artifact 内容加载 URL（用于 fetch）
 *
 * 注意：前端 fetch 需要带 X-Family-Id header
 */
export function artifactContentUrl(filepath: string, sessionId: string): string {
  return urlOfArtifact(filepath, sessionId, false)
}

/**
 * 生成 Artifact 下载 URL
 */
export function artifactDownloadUrl(filepath: string, sessionId: string): string {
  return urlOfArtifact(filepath, sessionId, true)
}

/**
 * 生成在新窗口打开 Artifact 的 URL
 */
export function artifactOpenUrl(filepath: string, sessionId: string): string {
  return urlOfArtifact(filepath, sessionId, false)
}