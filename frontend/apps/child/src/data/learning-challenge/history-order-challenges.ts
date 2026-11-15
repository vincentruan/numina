import type { OrderChallenge } from '@/types/learning-challenge'

export const orderHistoricalEvents: OrderChallenge = {
  id: 'order-historical-events',
  topicId: 'mt_IR8kIjZn_V',
  type: 'order',
  difficulty: 2,
  ageGroup: 'mid',
  scenario: 'Put these events in the order they happened.',
  scenarioZh: '把这几个历史事件按发生顺序排一排。',
  discoveryMessage: 'You read time well.',
  discoveryMessageZh: '你把时间读得清清楚楚。',
  conceptName: 'chronology',
  conceptNameZh: '年表',
  objects: [
    { id: 'e1', label: 'Invention of writing', labelZh: '文字发明', icon: '📜' },
    { id: 'e2', label: 'Great Wall built', labelZh: '修建长城', icon: '🧱' },
    { id: 'e3', label: 'Moon landing', labelZh: '登月', icon: '🌕' },
  ],
  correctOrder: ['e1', 'e2', 'e3'],
}
