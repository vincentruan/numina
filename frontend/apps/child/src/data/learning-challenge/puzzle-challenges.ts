import type { PuzzleChallenge } from '@/types/learning-challenge'

export const puzzleAreaTiles: PuzzleChallenge = {
  id: 'puzzle-area-tiles',
  topicId: 'mt_AzTrT5ySCx',
  type: 'puzzle',
  difficulty: 2,
  ageGroup: 'mid',
  scenario: 'Each piece fits into a specific slot. Put them where they belong.',
  scenarioZh: '每块要放到合适的位置，拼起来吧。',
  discoveryMessage: 'The picture is complete!',
  discoveryMessageZh: '拼图完成啦！',
  slots: [
    { id: 's1', label: 'Slot 1' },
    { id: 's2', label: 'Slot 2' },
    { id: 's3', label: 'Slot 3' },
    { id: 's4', label: 'Slot 4' },
  ],
  objects: [
    { id: 'p1', label: 'Corner', icon: '◤' },
    { id: 'p2', label: 'Edge', icon: '▬' },
    { id: 'p3', label: 'Centre', icon: '■' },
    { id: 'p4', label: 'Corner', icon: '◥' },
  ],
  correctPlacement: { s1: 'p1', s2: 'p2', s3: 'p3', s4: 'p4' },
}
