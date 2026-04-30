import http from './index'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface CalendarChoreEvent {
  id: string
  chore_name: string
  chore_emoji: string | null
  coin_reward: number
  streak_bonus: number
  status: 'approved' | 'pending_approval'
}

export interface CalendarWishEvent {
  id: string
  name: string
  emoji: string | null
  star_coin_cost: number | null
}

export interface CalendarMilestoneEvent {
  id: string
  milestone_type: string
}

export interface CalendarDaySummary {
  date: string // YYYY-MM-DD
  chore_count: number
  wish_count: number
  milestone_count: number
}

export interface CalendarMonthResponse {
  year: number
  month: number
  days: CalendarDaySummary[]
}

export interface CalendarDayDetail {
  date: string
  chores: CalendarChoreEvent[]
  wishes: CalendarWishEvent[]
  milestones: CalendarMilestoneEvent[]
}

// ---------------------------------------------------------------------------
// Child API
// ---------------------------------------------------------------------------

export async function getChildCalendar(year: number, month: number): Promise<CalendarMonthResponse> {
  const res = await http.get('/child/calendar', { params: { year, month } })
  return res.data
}

export async function getChildDayDetail(date: string): Promise<CalendarDayDetail> {
  const res = await http.get('/child/calendar/day', { params: { date } })
  return res.data
}

// ---------------------------------------------------------------------------
// Parent API
// ---------------------------------------------------------------------------

export async function getFamilyChildCalendar(
  childId: string,
  year: number,
  month: number,
): Promise<CalendarMonthResponse> {
  const res = await http.get('/family/child-calendar', { params: { child_id: childId, year, month } })
  return res.data
}

export async function getFamilyChildDayDetail(childId: string, date: string): Promise<CalendarDayDetail> {
  const res = await http.get('/family/child-calendar/day', { params: { child_id: childId, date } })
  return res.data
}
