import type { DrawGridChallenge } from '@/types/learning-challenge'

export const drawGridLetter: DrawGridChallenge = {
  id: 'draw-grid-letter-L',
  topicId: 'mt_yJmvUCCym7',
  type: 'draw-grid',
  difficulty: 1,
  ageGroup: 'early',
  scenario:
    'Draw an L: fill the whole left column and the two bottom-right cells.',
  scenarioZh: '画一个 L：涂满最左一列，再涂底部右边两格。',
  discoveryMessage: 'That is a neat letter L!',
  discoveryMessageZh: '好漂亮的字母 L！',
  conceptName: 'grid area',
  conceptNameZh: '网格面积',
  gridRows: 3,
  gridCols: 3,
  targetCells: ['0-0', '1-0', '2-0', '2-1', '2-2'],
}
