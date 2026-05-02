import http from './index'

export interface NotificationChannelResponse {
  id: number
  family_id: number
  channel_type: 'telegram' | 'email'
  name: string
  is_enabled: boolean
  subscriptions: string[]
  created_at: string
  updated_at: string
}

export interface NotificationChannelCreate {
  channel_type: 'telegram' | 'email'
  name: string
  config: Record<string, string | number>
  is_enabled: boolean
  subscriptions?: string[]
}

export interface NotificationChannelUpdate {
  name?: string
  config?: Record<string, string | number>
  is_enabled?: boolean
  subscriptions?: string[]
}

export interface NotificationConfig {
  id: number
  family_id: number
  large_purchase_threshold_fixed: number | null
  large_purchase_threshold_multiplier: number | null
  updated_at: string
}

export const notificationChannelsApi = {
  list(): Promise<NotificationChannelResponse[]> {
    return http.get<NotificationChannelResponse[]>('/notification-channels').then((r) => r.data)
  },
  create(data: NotificationChannelCreate): Promise<NotificationChannelResponse> {
    return http.post<NotificationChannelResponse>('/notification-channels', data).then((r) => r.data)
  },
  update(id: number, data: NotificationChannelUpdate): Promise<NotificationChannelResponse> {
    return http
      .put<NotificationChannelResponse>(`/notification-channels/${id}`, data)
      .then((r) => r.data)
  },
  remove(id: number): Promise<void> {
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
}
