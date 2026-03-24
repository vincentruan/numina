import http from './index'
import type { Currency, RatesResponse, RateResponse } from '@/types'

export function getCurrencies() {
  return http.get<Currency[]>('/currencies')
}

export function getRates() {
  return http.get<RatesResponse>('/currencies/rates')
}

export function getRate(code: string) {
  return http.get<RateResponse>(`/currencies/rates/${code}`)
}