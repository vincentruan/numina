import type { ConnectChallenge } from '@/types/learning-challenge'

export const connectEmotions: ConnectChallenge = {
  id: 'connect-emotions',
  topicId: 'mt_kvrvpQris4',
  type: 'connect',
  difficulty: 1,
  ageGroup: 'early',
  scenario: 'Match each situation to the feeling it brings.',
  scenarioZh: '把每种情境和它带来的感觉连起来。',
  discoveryMessage: 'Feelings make sense.',
  discoveryMessageZh: '感觉都有道理。',
  conceptName: 'empathy',
  conceptNameZh: '同理心',
  leftItems: [
    { id: 'l1', label: 'You won a prize.' },
    { id: 'l2', label: 'A friend lost a pet.' },
    { id: 'l3', label: 'A new classmate joined.' },
  ],
  rightItems: [
    { id: 'r1', label: 'Excited' },
    { id: 'r2', label: 'Sad for them' },
    { id: 'r3', label: 'Curious' },
  ],
  correctPairs: { l1: 'r1', l2: 'r2', l3: 'r3' },
}

export const connectLifeSkills: ConnectChallenge = {
  id: 'connect-life-skills',
  topicId: 'mt_SbEaQnMQoD',
  type: 'connect',
  difficulty: 2,
  ageGroup: 'mid',
  scenario: 'Match each choice to its consequence.',
  scenarioZh: '把每种选择和它的结果连起来。',
  discoveryMessage: 'Choices lead to outcomes.',
  discoveryMessageZh: '每个选择都有结果。',
  leftItems: [
    { id: 'l1', label: 'Save $5 each week.' },
    { id: 'l2', label: 'Spend it all at once.' },
    { id: 'l3', label: 'Share some with a friend.' },
  ],
  rightItems: [
    { id: 'r1', label: 'Build up a small pot' },
    { id: 'r2', label: 'Nothing left later' },
    { id: 'r3', label: 'A friend remembers the gift' },
  ],
  correctPairs: { l1: 'r1', l2: 'r2', l3: 'r3' },
}
