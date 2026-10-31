/**
 * Balance challenges — algebraic thinking and equivalence.
 */
import type { BalanceChallenge } from '@/types/learning-challenge'

/** Balance an addition equation. */
export const balanceEquationChallenge: BalanceChallenge = {
  id: 'balance-equation-simple',
  topicId: 'math.addition.equations',
  type: 'balance',
  difficulty: 2,
  ageGroup: 'mid',
  scenario:
    'The left side has 3 + 2. What do you put on the right side to make it balance?',
  scenarioZh: '左边有 3 + 2。右边放什么才能平衡呢？',
  discoveryMessage:
    'Both sides equal 5! That\'s what an equation means — both sides are the same.',
  discoveryMessageZh:
    '两边都等于5！这就是等式的意思——两边一样大。',
  leftFixed: [
    { id: 'lf-3', label: '3', icon: '🔵' },
    { id: 'lf-2', label: '2', icon: '🔵' },
  ],
  rightSlots: 2,
  objects: [
    { id: 'r-1', label: '1', icon: '🔴' },
    { id: 'r-2', label: '2', icon: '🔴' },
    { id: 'r-3', label: '3', icon: '🔴' },
    { id: 'r-4', label: '4', icon: '🔴' },
    { id: 'r-5', label: '5', icon: '🔴' },
  ],
  objectValues: {
    'lf-3': 3,
    'lf-2': 2,
    'r-1': 1,
    'r-2': 2,
    'r-3': 3,
    'r-4': 4,
    'r-5': 5,
  },
}

/** Balance with fruit weights. */
export const balanceWeightsChallenge: BalanceChallenge = {
  id: 'balance-fruit-weights',
  topicId: 'math.measurement.weight',
  type: 'balance',
  difficulty: 3,
  ageGroup: 'mid',
  scenario:
    'Three apples weigh 9 units. Which fruits can you put on the right to balance the scale?',
  scenarioZh: '三个苹果重9个单位。哪些水果放在右边能平衡呢？',
  discoveryMessage:
    'The fruits on the right also weigh 9! Different items can have the same total weight.',
  discoveryMessageZh:
    '右边的水果也重9！不同的东西可以有一样的总重量。',
  leftFixed: [
    { id: 'apple-1', label: 'Apple', labelZh: '苹果', icon: '🍎' },
    { id: 'apple-2', label: 'Apple', labelZh: '苹果', icon: '🍎' },
    { id: 'apple-3', label: 'Apple', labelZh: '苹果', icon: '🍎' },
  ],
  rightSlots: 3,
  objects: [
    { id: 'orange', label: 'Orange', labelZh: '橙子', icon: '🍊' },
    { id: 'lemon', label: 'Lemon', labelZh: '柠檬', icon: '🍋' },
    { id: 'grape-bunch', label: 'Grapes', labelZh: '葡萄', icon: '🍇' },
    { id: 'banana', label: 'Banana', labelZh: '香蕉', icon: '🍌' },
    { id: 'pear', label: 'Pear', labelZh: '梨', icon: '🍐' },
  ],
  objectValues: {
    'apple-1': 3,
    'apple-2': 3,
    'apple-3': 3,
    'orange': 3,
    'lemon': 1,
    'grape-bunch': 4,
    'banana': 2,
    'pear': 3,
  },
}
