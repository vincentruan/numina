export interface WebSearchProviderTemplate {
  provider_name: string
  provider_class: string
  display_name: string
  requires_api_key: boolean
  config_fields: ConfigField[]
  docs_url: string
  note: string
}

export interface ConfigField {
  key: string
  label: string
  type: 'secret' | 'number' | 'string'
  required?: boolean
  default?: number | string
}

export interface WebSearchProvider {
  id: string
  family_id: string
  provider_name: string
  display_name: string | null
  is_enabled: boolean
  display_order: number
  max_results: number
  circuit_state: 'closed' | 'open' | 'half_open'
  circuit_reason: string | null
  has_api_key: boolean
  created_at: string
  updated_at: string
}

export interface WebSearchProviderCreate {
  provider_name: string
  display_name?: string
  api_key?: string
  max_results?: number
}

export interface WebSearchProviderUpdate {
  display_name?: string
  api_key?: string
  max_results?: number
  display_order?: number
}

export interface WebSearchStatus {
  has_web_search: boolean
  enabled_count: number
}
