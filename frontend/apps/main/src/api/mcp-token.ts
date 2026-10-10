import http from './index'

// ── Backend MCP External API Token ─────────────────────────────────────────

export interface MCPTokenData {
  token_prefix: string
  token_last4: string
  allow_external: boolean
  allow_write: boolean
  /** null = all tools available; list = exact enabled set */
  allowed_tools: string[] | null
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
  /** null resets to all-available; list sets the exact whitelist */
  allowed_tools?: string[] | null
  expires_at?: string | null
}

export interface MCPToolCatalogItem {
  name: string
  description: string
  requires_write: boolean
}

export const getMCPToken = () =>
  http.get<MCPTokenData>('/ai/mcp-token')
export const generateMCPToken = () =>
  http.post<MCPTokenGenerateData>('/ai/mcp-token')
export const updateMCPToken = (data: MCPTokenUpdate) =>
  http.patch<MCPTokenData>('/ai/mcp-token', data)
export const deleteMCPToken = () =>
  http.delete('/ai/mcp-token')

/** Tool catalogue for the per-tool whitelist checkboxes. */
export const getMCPTools = () =>
  http.get<{ tools: MCPToolCatalogItem[] }>('/ai/mcp-token/tools')

// ── MCP usage statistics ───────────────────────────────────────────────────

export interface MCPHourlyBucket {
  hour: string
  count: number
}

export interface MCPToolBreakdown {
  tool_name: string
  count: number
}

export interface MCPIPBreakdown {
  client_ip: string
  count: number
  user_agent: string | null
}

export interface MCPStatsData {
  total_calls: number
  success_count: number
  failure_count: number
  error_count: number
  permission_denied_count: number
  success_rate: number
  hourly_buckets: MCPHourlyBucket[]
  tool_breakdown: MCPToolBreakdown[]
  ip_breakdown: MCPIPBreakdown[]
}

export interface MCPAccessLogEntry {
  id: string
  family_id: string
  token_id: string | null
  session_id: string | null
  event_type: string
  tool_name: string | null
  status: string
  duration_ms: number | null
  client_ip: string
  user_agent: string | null
  args_digest: string | null
  error_code: string | null
  created_at: string
}

export interface MCPAccessLogListData {
  items: MCPAccessLogEntry[]
  total: number
  page: number
  page_size: number
}

export const getMCPStats = (params?: { date_from?: string; date_to?: string }) =>
  http.get<MCPStatsData>('/ai/mcp-token/stats', { params })

export const getMCPAccessLogs = (params?: {
  event_type?: string
  tool_name?: string
  date_from?: string
  date_to?: string
  page?: number
  page_size?: number
}) => http.get<MCPAccessLogListData>('/ai/mcp-token/access-logs', { params })
