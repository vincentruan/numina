import http from './index'
import type {
  BlindBoxGift,
  BlindBoxGiftCreate,
  BlindBoxGiftUpdate,
  BlindBoxDraw,
  DrawRequest,
  BlindBoxConfig,
  BlindBoxConfigUpdate,
  BonusDraw,
} from '@/types/blindBox'

// ── 父母端 API ────────────────────────────────────────────────────────────────

export const blindBoxApi = {
  // 礼物池
  listGifts: () => http.get<BlindBoxGift[]>('/blind-box/gifts'),
  createGift: (data: BlindBoxGiftCreate) => http.post<BlindBoxGift>('/blind-box/gifts', data),
  updateGift: (id: number, data: BlindBoxGiftUpdate) =>
    http.put<BlindBoxGift>(`/blind-box/gifts/${id}`, data),
  deleteGift: (id: number) => http.delete(`/blind-box/gifts/${id}`),
  createGiftFromWish: (wishId: number) =>
    http.post<BlindBoxGift>(`/blind-box/gifts/from-wish/${wishId}`),

  // 抽奖记录
  listDraws: () => http.get<BlindBoxDraw[]>('/blind-box/draws'),
  fulfillDraw: (id: number) => http.put<BlindBoxDraw>(`/blind-box/draws/${id}/fulfill`),

  // 配置
  getConfig: () => http.get<BlindBoxConfig>('/blind-box/config'),
  updateConfig: (data: BlindBoxConfigUpdate) =>
    http.put<BlindBoxConfig>('/blind-box/config', data),

  // Bonus draws (父母查看)
  listBonusDraws: () => http.get<BonusDraw[]>('/blind-box/bonus-draws'),
}

// ── 孩子端 API ────────────────────────────────────────────────────────────────

export const childBlindBoxApi = {
  // 抽奖
  draw: (data: DrawRequest) => http.post<BlindBoxDraw>('/child/blind-box/draw', data),
  listDraws: () => http.get<BlindBoxDraw[]>('/child/blind-box/draws'),

  // Bonus draws
  listBonusDraws: () => http.get<BonusDraw[]>('/child/blind-box/bonus-draws'),
  useBonusDraw: (bonusId: number) =>
    http.post<BlindBoxDraw>(`/child/blind-box/bonus-draws/${bonusId}/use`),
}
