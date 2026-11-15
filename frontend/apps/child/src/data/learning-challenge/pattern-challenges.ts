/**
 * Pattern challenge demo configs — mathematics signature.
 *
 * Each topic key below exists in the taxonomy; the topics that already have
 * approved questions (mathematics) work end-to-end. Topics for the other
 * subjects rely on the template seed run before their signature can be reached.
 */
import type { PatternChallenge } from '@/types/learning-challenge'

export const patternFractionNext: PatternChallenge = {
  id: 'pattern-fraction-next',
  topicId: 'math.fractions.understanding',
  type: 'pattern',
  difficulty: 2,
  ageGroup: 'mid',
  scenario: 'Look at the sequence. What comes next?',
  scenarioZh: '看看这串分数，下一个是什么？',
  discoveryMessage: 'You found the pattern!',
  discoveryMessageZh: '你找到规律啦！',
  conceptName: 'sequence',
  conceptNameZh: '序列',
  sequence: [
    { id: 's1', label: '½', icon: '½' },
    { id: 's2', label: '¾', icon: '¾' },
    { id: 's3', label: '1', icon: '1' },
  ],
  options: [
    { id: 'o1', label: '1¼', icon: '1¼' },
    { id: 'o2', label: '2', icon: '2' },
    { id: 'o3', label: '1½', icon: '1½' },
  ],
  correctAnswer: 'o1',
}

export const patternEmoji: PatternChallenge = {
  id: 'pattern-emoji',
  topicId: 'math.patterns.sequence',
  type: 'pattern',
  difficulty: 1,
  ageGroup: 'early',
  scenario: '🔵 🔴 🔵 🔴 🔵 ? — what comes next?',
  scenarioZh: '🔵 🔴 🔵 🔴 🔵 ? — 下一个是什么？',
  discoveryMessage: 'It repeats in twos!',
  discoveryMessageZh: '它每两个重复一次！',
  conceptName: 'repeating pattern',
  conceptNameZh: '重复规律',
  sequence: [
    { id: 's1', label: '🔵', icon: '🔵' },
    { id: 's2', label: '🔴', icon: '🔴' },
    { id: 's3', label: '🔵', icon: '🔵' },
    { id: 's4', label: '🔴', icon: '🔴' },
    { id: 's5', label: '🔵', icon: '🔵' },
  ],
  options: [
    { id: 'o1', label: '🔴', icon: '🔴' },
    { id: 'o2', label: '🔵', icon: '🔵' },
    { id: 'o3', label: '🟢', icon: '🟢' },
  ],
  correctAnswer: 'o1',
}
