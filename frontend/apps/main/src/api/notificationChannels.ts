import http from './index'

export interface NotificationEvent {
  type: string
  label_key: string
  severity: string
}

export interface NotificationEventCategory {
  category: string
  label_key: string
  icon: string
  events: NotificationEvent[]
}

export type NotificationChannelType = 'telegram' | 'email' | 'feishu' | 'webpush'

export interface NotificationChannelResponse {
  id: string
  family_id: string
  channel_type: NotificationChannelType
  name: string
  is_enabled: boolean
  config: Record<string, string | number | Record<string, string>>
  subscriptions: string[]
  digest_mode: 'immediate' | 'daily'
  digest_time: string
  created_at: string
  updated_at: string
  last_delivery_status: 'sent' | 'failed' | null
  last_delivery_at: string | null
}

export interface NotificationChannelCreate {
  channel_type: NotificationChannelType
  name: string
  config: Record<string, string | number | Record<string, string>>
  is_enabled: boolean
  subscriptions?: string[]
  digest_mode?: 'immediate' | 'daily'
  digest_time?: string
}

export interface NotificationChannelUpdate {
  name?: string
  config?: Record<string, string | number | Record<string, string>>
  is_enabled?: boolean
  subscriptions?: string[]
  digest_mode?: 'immediate' | 'daily'
  digest_time?: string
}

export interface NotificationConfig {
  id: string
  family_id: string
  large_purchase_threshold_fixed: number | null
  large_purchase_threshold_multiplier: number | null
  updated_at: string
}

export interface LargePurchaseStatus {
  threshold_configured: boolean
  subscribing_channel_count: number
  subscribing_channel_names: string[]
}

export interface NotificationFeatureStatus {
  large_purchase: LargePurchaseStatus
}

export interface ChannelTestResult {
  success: boolean
  error: string | null
}

export interface DeliveryRecord {
  id: string
  reminder_id: string
  reminder_type: string
  reminder_title: string
  status: 'sent' | 'failed'
  created_at: string
}

export const notificationChannelsApi = {
  list(): Promise<NotificationChannelResponse[]> {
    return http.get<NotificationChannelResponse[]>('/notification-channels').then((r) => r.data)
  },
  create(data: NotificationChannelCreate): Promise<NotificationChannelResponse> {
    return http.post<NotificationChannelResponse>('/notification-channels', data).then((r) => r.data)
  },
  update(id: string, data: NotificationChannelUpdate): Promise<NotificationChannelResponse> {
    return http
      .put<NotificationChannelResponse>(`/notification-channels/${id}`, data)
      .then((r) => r.data)
  },
  remove(id: string): Promise<void> {
    return http.delete(`/notification-channels/${id}`).then(() => undefined)
  },
  getConfig(): Promise<NotificationConfig> {
    return http.get<NotificationConfig>('/notification-config').then((r) => r.data)
  },
  updateConfig(data: {
    large_purchase_threshold_fixed?: number | null
    large_purchase_threshold_multiplier?: number | null
  }): Promise<NotificationConfig> {
    return http.put<NotificationConfig>('/notification-config', data).then((r) => r.data)
  },
  getEvents(): Promise<NotificationEventCategory[]> {
    return http.get<NotificationEventCategory[]>('/notification-channels/events').then((r) => r.data)
  },
  getFeatureStatus(): Promise<NotificationFeatureStatus> {
    return http.get<NotificationFeatureStatus>('/notification-config/status').then((r) => r.data)
  },
  testChannel(id: string): Promise<ChannelTestResult> {
    return http.post<ChannelTestResult>(`/notification-channels/${id}/test`).then((r) => r.data)
  },
  getDeliveryHistory(id: string, limit = 20): Promise<DeliveryRecord[]> {
    return http
      .get<DeliveryRecord[]>(`/notification-channels/${id}/delivery-history`, { params: { limit } })
      .then((r) => r.data)
  },
}
