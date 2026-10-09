import http from './index'

// ── Backend MCP External API Token ─────────────────────────────────────────

export interface MCPTokenData {
  token_prefix: string
  token_last4: string
  allow_external: boolean
  allow_write: boolean
  expires_at: string | null
  last_used_at: string | null
  is_active: boolean
  created_at: string
}

export interface MCPTokenGenerateData extends MCPTokenData {
  /** Plaintext token — returned exactly once, cannot be retrieved again. */
  token: string
}

export interface MCPTokenUpdate {
  allow_external?: boolean
  allow_write?: boolean
  expires_at?: string | null
}

export const getMCPToken = () =>
  http.get<MCPTokenData>('/ai/mcp-token')
export const generateMCPToken = () =>
  http.post<MCPTokenGenerateData>('/ai/mcp-token')
export const updateMCPToken = (data: MCPTokenUpdate) =>
  http.patch<MCPTokenData>('/ai/mcp-token', data)
export const deleteMCPToken = () =>
  http.delete('/ai/mcp-token')
