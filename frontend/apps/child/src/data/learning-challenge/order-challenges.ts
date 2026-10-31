/**
 * Order challenges — seriation and ordinal reasoning.
 */
import type { OrderChallenge } from '@/types/learning-challenge'

/** Order fractions from smallest to largest. */
export const orderFractionsChallenge: OrderChallenge = {
  id: 'order-fractions',
  topicId: 'math.fractions.ordering',
  type: 'order',
  difficulty: 2,
  ageGroup: 'mid',
  scenario:
    'Put these pieces of cake in order from the smallest piece to the biggest piece!',
  scenarioZh: '把这些蛋糕从小到大排一排！',
  discoveryMessage:
    'You put them in the right order! ¼ is the smallest, then ½, then ¾, and 1 whole is the biggest.',
  discoveryMessageZh:
    '你排对了！¼最小，然后是½，再是¾，一整个最大。',
  objects: [
    { id: 'frac-1', label: '¼', icon: '🍰' },
    { id: 'frac-2', label: '½', icon: '🍰' },
    { id: 'frac-3', label: '¾', icon: '🍰' },
    { id: 'frac-4', label: '1', icon: '🎂' },
  ],
  correctOrder: ['frac-1', 'frac-2', 'frac-3', 'frac-4'],
}

/** Order numbers from smallest to largest. */
export const orderNumbersChallenge: OrderChallenge = {
  id: 'order-numbers-small',
  topicId: 'math.numbers.ordering',
  type: 'order',
  difficulty: 1,
  ageGroup: 'early',
  scenario:
    'Put these numbers in order from the smallest to the biggest!',
  scenarioZh: '把这些数字从小到大排一排！',
  discoveryMessage:
    'Great job! You know that 2 < 5 < 8 < 10.',
  discoveryMessageZh:
    '太棒了！你知道 2 < 5 < 8 < 10。',
  objects: [
    { id: 'n-5', label: '5', icon: '5️⃣' },
    { id: 'n-2', label: '2', icon: '2️⃣' },
    { id: 'n-10', label: '10', icon: '🔟' },
    { id: 'n-8', label: '8', icon: '8️⃣' },
  ],
  correctOrder: ['n-2', 'n-5', 'n-8', 'n-10'],
}
