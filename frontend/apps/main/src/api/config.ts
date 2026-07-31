import http from './index'

export interface FamilyConfigValues {
  ai_cache_ttl_report: number
  ai_cache_ttl_finance_coach: number
  ai_cache_ttl_dashboard_narrative: number
  dashboard_min_asset_count: number
  dashboard_min_history_months: number
  dashboard_expiring_days_threshold: number
  scheduled_monthly_report_day: number
  scheduled_monthly_report_hour: number
  scheduled_weekly_scan_day: number
  scheduled_weekly_scan_hour: number
  literacy_report_day: number
  literacy_report_hour: number
  ai_cache_ttl_literacy_weekly_report: number
}

export interface UserConfigValues {
  dashboard_trend_period: string
  activity_feed_page_size: number
  onboarding_guide_version: number
  onboarding_attempts: number
  onboarding_completions: number
}

export interface SettingDefinition {
  type: 'int' | 'float' | 'string' | 'bool'
  default: number | string | boolean
  min: number | null
  max: number | null
  step: number | null
  allowed_values: string[] | null
  label_key: string
  description_key: string | null
}

export function getFamilyConfig() {
  return http.get<FamilyConfigValues>('/family/config')
}

export function updateFamilyConfig(settings: Partial<FamilyConfigValues>) {
  return http.patch<FamilyConfigValues>('/family/config', { settings })
}

export function getFamilyConfigDefinitions() {
  return http.get<Record<string, SettingDefinition>>('/family/config/definitions')
}

export function getUserConfig() {
  return http.get<UserConfigValues>('/user/config')
}

export function updateUserConfig(settings: Partial<UserConfigValues>) {
  return http.patch<UserConfigValues>('/user/config', { settings })
}
