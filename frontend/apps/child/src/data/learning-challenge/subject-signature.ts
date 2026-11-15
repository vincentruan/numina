/**
 * Signature challenge per subject.
 *
 * Keyed by `LearningTopic.subject` slug. This is static data only: runtime
 * dispatch still goes through TOPIC_CHALLENGE_MAP by topic_key, so this map
 * never selects a component. It records which type represents each subject so
 * content authors and the static validation test can hold the mapping stable.
 */
import type { ChallengeType } from '@/types/learning-challenge'

export const SUBJECT_SIGNATURE: Record<string, ChallengeType> = {
  mathematics: 'pattern',
  science: 'estimate',
  english: 'spot-the-mistake',
  history: 'order',
  personal_social: 'connect',
  life_skills: 'estimate',
  computing: 'puzzle',
  learning_to_learn: 'spot-the-mistake',
}

/** Valid subject slugs, mirroring SUBJECT_MAP in the topic seed script. */
export const SUBJECT_SLUGS: readonly string[] = [
  'mathematics',
  'science',
  'english',
  'history',
  'personal_social',
  'life_skills',
  'computing',
  'learning_to_learn',
]
