/**
 * Classify challenges — sorting items into categories.
 */
import type { ClassifyChallenge } from '@/types/learning-challenge'

/** Sort items into living vs. non-living. */
export const classifyLivingChallenge: ClassifyChallenge = {
  id: 'classify-living-nonliving',
  topicId: 'science.classification.living',
  type: 'classify',
  difficulty: 1,
  ageGroup: 'early',
  scenario:
    'Sort these into living things and non-living things!',
  scenarioZh: '把这些分成有生命的和没有生命的！',
  discoveryMessage:
    'You sorted them! Living things grow and change. Non-living things do not.',
  discoveryMessageZh:
    '你分对了！有生命的东西会生长和变化，没有生命的不会。',
  objects: [
    { id: 'dog', label: 'Dog', labelZh: '狗', icon: '🐕' },
    { id: 'tree', label: 'Tree', labelZh: '树', icon: '🌳' },
    { id: 'rock', label: 'Rock', labelZh: '石头', icon: '🪨' },
    { id: 'fish', label: 'Fish', labelZh: '鱼', icon: '🐟' },
    { id: 'flower', label: 'Flower', labelZh: '花', icon: '🌸' },
    { id: 'car', label: 'Car', labelZh: '汽车', icon: '🚗' },
  ],
  zones: [
    { id: 'living', label: 'Living', labelZh: '有生命' },
    { id: 'nonliving', label: 'Non-living', labelZh: '没有生命' },
  ],
  correctMapping: {
    dog: 'living',
    tree: 'living',
    rock: 'nonliving',
    fish: 'living',
    flower: 'living',
    car: 'nonliving',
  },
}

/** Sort shapes by number of sides. */
export const classifyShapesChallenge: ClassifyChallenge = {
  id: 'classify-shapes-sides',
  topicId: 'math.geometry.shapes',
  type: 'classify',
  difficulty: 2,
  ageGroup: 'early',
  scenario:
    'Sort these shapes by how many sides they have!',
  scenarioZh: '按边数给这些图形分分类！',
  discoveryMessage:
    'You sorted them by sides! Triangles have 3, squares have 4, and pentagons have 5.',
  discoveryMessageZh:
    '你按边数分对了！三角形有3条边，正方形有4条，五边形有5条。',
  objects: [
    { id: 'triangle', label: 'Triangle', labelZh: '三角形', icon: '🔺' },
    { id: 'square', label: 'Square', labelZh: '正方形', icon: '🟦' },
    { id: 'diamond', label: 'Triangle', labelZh: '三角形', icon: '🔷' },
    { id: 'pentagon', label: 'Pentagon', labelZh: '五边形', icon: '⬠' },
    { id: 'rect', label: 'Rectangle', labelZh: '长方形', icon: '▬' },
  ],
  zones: [
    { id: 'sides-3', label: '3 sides', labelZh: '3条边' },
    { id: 'sides-4', label: '4 sides', labelZh: '4条边' },
    { id: 'sides-5', label: '5 sides', labelZh: '5条边' },
  ],
  correctMapping: {
    triangle: 'sides-3',
    square: 'sides-4',
    diamond: 'sides-3',
    pentagon: 'sides-5',
    rect: 'sides-4',
  },
}
