import http from './index'

export const createWsTicket = () =>
  http.post<{ ticket: string }>('/notifications/ws-ticket')
